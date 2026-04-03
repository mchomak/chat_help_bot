"""Payment service — orchestrates DB payment lifecycle + YooKassa API calls."""

from __future__ import annotations

import datetime
import logging
import uuid
from dataclasses import dataclass

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import tariffs_config
from app.config import settings as app_settings
from app.db.models.payment import Payment, PaymentStatus
from app.db.models.user import UserAccess
from app.db.repositories import payment_repo, user_repo
from app.services import yookassa_service
from app.services.access_service import AccessStatus, add_screenshot_pack, grant_paid_access

logger = logging.getLogger(__name__)


@dataclass
class InitiateResult:
    """Returned by create_and_initiate_payment."""
    payment_id: uuid.UUID
    payment_url: str | None   # None when api_error
    error: str | None         # None on success


@dataclass
class GrantResult:
    """Returned after goods are credited following a successful payment."""
    referrer_telegram_id: int | None = None
    referral_bonus_days: int = 0
    referral_bonus_screenshots: int = 0


async def create_and_initiate_payment(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    purchase_type: str,
    purchase_key: str,
    customer_email: str,
) -> InitiateResult:
    """Create a DB Payment record then call YooKassa to get a payment URL.

    Lifecycle:
    - Insert Payment(status=pending)  → commit
    - Call YooKassa API
    - On success: update to waiting_for_payment  → commit
    - On failure: update to api_error            → commit
    """
    if purchase_type == "tariff":
        plan = tariffs_config.get_tariff(purchase_key)
        amount = plan.price
        description = f"Подписка «{plan.label}»"
    else:
        pack = tariffs_config.get_pack(purchase_key)
        amount = pack.price
        description = f"Пакет скриншотов «{pack.label}»"

    payment = await payment_repo.create_payment(
        session,
        user_id=user_id,
        purchase_type=purchase_type,
        purchase_key=purchase_key,
        amount=amount,
    )
    # Commit so the record survives even if the API call below crashes the process
    await session.commit()

    logger.info(
        "[PAYMENT CREATE] user_id=%s type=%s key=%s amount=%.2f email=%s payment_db_id=%s",
        user_id,
        purchase_type,
        purchase_key,
        amount,
        customer_email[:3] + "***" if len(customer_email) > 3 else "***",
        payment.id,
    )

    try:
        result = await yookassa_service.create_payment(
            shop_id=app_settings.yookassa.shop_id,
            api_key=app_settings.yookassa.api_key,
            amount=amount,
            description=description,
            return_url=app_settings.yookassa.return_url,
            idempotency_key=str(payment.id),
            metadata={"payment_db_id": str(payment.id), "user_id": str(user_id)},
            customer_email=customer_email,
            vat_code=app_settings.yookassa.vat_code,
        )
        payment.yookassa_payment_id = result.yookassa_id
        payment.payment_url = result.confirmation_url
        payment.status = PaymentStatus.WAITING_FOR_PAYMENT
        await session.commit()
        logger.info(
            "[PAYMENT CREATE] YooKassa payment created: db_id=%s yk_id=%s url=%s",
            payment.id, result.yookassa_id, result.confirmation_url,
        )
        return InitiateResult(payment_id=payment.id, payment_url=result.confirmation_url, error=None)

    except RuntimeError as exc:
        payment.status = PaymentStatus.API_ERROR
        payment.error_message = str(exc)
        await session.commit()
        logger.error(
            "[PAYMENT CREATE] YooKassa API error for db_id=%s: %s", payment.id, exc,
        )
        return InitiateResult(payment_id=payment.id, payment_url=None, error=str(exc))


async def poll_and_process_payment(
    session: AsyncSession,
    bot: Bot,
    payment_id: uuid.UUID,
) -> str:
    """Fetch current YooKassa status, process if succeeded/canceled. Returns new status."""
    payment = await payment_repo.get_payment(session, payment_id)
    if payment is None:
        logger.warning("[POLL] payment_id=%s not found in DB", payment_id)
        return "not_found"

    logger.info(
        "[POLL] payment_id=%s user_id=%s type=%s key=%s status=%s "
        "goods_granted=%s yk_id=%s",
        payment.id, payment.user_id, payment.purchase_type, payment.purchase_key,
        payment.status, payment.goods_granted, payment.yookassa_payment_id,
    )

    # Canceled/failed payments can never become successful — skip
    if payment.status in (PaymentStatus.CANCELED, PaymentStatus.FAILED):
        logger.info("[POLL] payment %s is in terminal state %s — nothing to do",
                    payment.id, payment.status)
        return payment.status

    # Succeeded AND goods already granted — truly nothing to do
    if payment.status == PaymentStatus.SUCCEEDED and payment.goods_granted:
        logger.info("[POLL] payment %s already succeeded with goods granted — nothing to do",
                    payment.id)
        return payment.status

    # If payment.status == SUCCEEDED but goods_granted == False:
    # this means a previous attempt failed after writing the status to DB —
    # we MUST continue and re-attempt to grant goods.
    if payment.status == PaymentStatus.SUCCEEDED and not payment.goods_granted:
        logger.warning(
            "[POLL] payment %s has status=succeeded but goods_granted=False — "
            "will re-attempt goods grant",
            payment.id,
        )

    if payment.yookassa_payment_id is None:
        logger.warning("[POLL] payment %s has no yookassa_payment_id — cannot poll YooKassa",
                       payment.id)
        return payment.status

    try:
        yk_status = await yookassa_service.fetch_payment_status(
            shop_id=app_settings.yookassa.shop_id,
            api_key=app_settings.yookassa.api_key,
            yookassa_payment_id=payment.yookassa_payment_id,
        )
    except RuntimeError as exc:
        logger.warning("[POLL] failed to fetch YooKassa status for payment %s: %s",
                       payment.id, exc)
        return payment.status

    logger.info("[POLL] YooKassa returned status=%s for payment %s (DB status=%s)",
                yk_status, payment.id, payment.status)

    await _apply_yookassa_status(session, bot, payment, yk_status)
    return payment.status


async def process_webhook(
    session: AsyncSession,
    bot: Bot,
    yookassa_payment_id: str,
) -> None:
    """Handle an incoming YooKassa webhook. Re-fetches status to avoid trusting payload.

    Idempotent: safe to call multiple times for the same payment.
    """
    logger.info("[WEBHOOK] received for yookassa_payment_id=%s", yookassa_payment_id)

    payment = await payment_repo.get_by_yookassa_id(session, yookassa_payment_id)
    if payment is None:
        logger.warning("[WEBHOOK] no DB payment found for yookassa_payment_id=%s",
                       yookassa_payment_id)
        return

    logger.info(
        "[WEBHOOK] payment found: db_id=%s user_id=%s status=%s goods_granted=%s",
        payment.id, payment.user_id, payment.status, payment.goods_granted,
    )

    # Re-verify status directly from YooKassa (don't blindly trust webhook body)
    try:
        yk_status = await yookassa_service.fetch_payment_status(
            shop_id=app_settings.yookassa.shop_id,
            api_key=app_settings.yookassa.api_key,
            yookassa_payment_id=yookassa_payment_id,
        )
    except RuntimeError as exc:
        logger.error("[WEBHOOK] cannot verify status for yk_id=%s: %s",
                     yookassa_payment_id, exc)
        return

    logger.info("[WEBHOOK] verified YooKassa status=%s for yk_id=%s",
                yk_status, yookassa_payment_id)

    await _apply_yookassa_status(session, bot, payment, yk_status)


# ── Internal helpers ─────────────────────────────────────────────────────────

_YK_TO_INTERNAL = {
    "succeeded": PaymentStatus.SUCCEEDED,
    "canceled": PaymentStatus.CANCELED,
    "waiting_for_capture": PaymentStatus.WAITING_FOR_PAYMENT,
    "pending": PaymentStatus.WAITING_FOR_PAYMENT,
}


async def _apply_yookassa_status(
    session: AsyncSession,
    bot: Bot,
    payment: Payment,
    yk_status: str,
) -> None:
    new_status = _YK_TO_INTERNAL.get(yk_status, PaymentStatus.FAILED)

    if new_status == payment.status and payment.goods_granted:
        logger.debug("[APPLY] payment %s already at status=%s with goods_granted — no-op",
                     payment.id, new_status)
        return  # Already processed — idempotent skip

    logger.info("[APPLY] payment %s: %s → %s (goods_granted=%s)",
                payment.id, payment.status, new_status, payment.goods_granted)

    if new_status == PaymentStatus.SUCCEEDED and not payment.goods_granted:
        # IMPORTANT: do NOT set payment.status = succeeded before _grant_goods.
        #
        # SQLAlchemy has autoflush=True: any session.execute(SELECT) inside
        # _grant_goods would flush the dirty payment object, writing
        # payment.status="succeeded" to the DB transaction. If _grant_goods
        # then raises, ErrorLoggingMiddleware (the outer middleware) catches
        # the exception and calls db_session.commit() — which would commit
        # payment.status="succeeded" while goods_granted remains False.
        # Next poll would then see status=succeeded and return early (Bug #1),
        # making the subscription permanently unactivatable.
        #
        # Solution: set payment.status ONLY after _grant_goods succeeds.
        # If _grant_goods raises, payment.status stays as waiting_for_payment,
        # and the user can safely retry by clicking "Проверить статус" again.
        try:
            grant_result = await _grant_goods(session, payment)
        except Exception:
            logger.exception(
                "[APPLY] _grant_goods failed for payment %s (user_id=%s type=%s key=%s) — "
                "payment.status NOT updated; user can retry",
                payment.id, payment.user_id, payment.purchase_type, payment.purchase_key,
            )
            raise

        payment.goods_granted = True
        payment.status = new_status  # Set AFTER successful grant
        await session.flush()
        logger.info(
            "[APPLY] goods granted, status set to %s for payment %s (user_id=%s)",
            new_status, payment.id, payment.user_id,
        )
        await _send_success_notification(bot, payment, grant_result)

    elif new_status in (PaymentStatus.CANCELED, PaymentStatus.FAILED):
        payment.status = new_status
        await session.flush()
        await _send_cancel_notification(bot, payment)

    else:
        payment.status = new_status
        await session.flush()


async def _grant_goods(session: AsyncSession, payment: Payment) -> GrantResult:
    """Credit subscription or screenshots to the user. Returns referral info."""
    user_id = payment.user_id

    if payment.purchase_type == "tariff":
        plan = tariffs_config.get_tariff(payment.purchase_key)
        now = datetime.datetime.now(datetime.UTC)

        # Extend from current paid_until if subscription is still active; otherwise start from now
        access = (
            await session.execute(select(UserAccess).where(UserAccess.user_id == user_id))
        ).scalar_one_or_none()

        # Determine if user is currently on trial (not yet a paid subscriber)
        is_trial_transition = access is not None and access.access_status == AccessStatus.TRIAL

        if access and access.paid_until and not is_trial_transition:
            current_until = access.paid_until
            if current_until.tzinfo is None:
                current_until = current_until.replace(tzinfo=datetime.UTC)
            base = current_until if current_until > now else now
            logger.debug(
                "[GRANT] payment %s: extending from %s (active=%s)",
                payment.id, current_until.isoformat(), current_until > now,
            )
        else:
            base = now
            if is_trial_transition:
                logger.debug("[GRANT] payment %s: trial → paid transition, starting from now",
                             payment.id)
            else:
                logger.debug("[GRANT] payment %s: no active subscription — starting from now",
                             payment.id)

        paid_until = base + datetime.timedelta(days=plan.days)
        logger.info(
            "[GRANT] tariff: user_id=%s plan=%s days=%d paid_until=%s screenshots=%d "
            "is_trial_transition=%s payment=%s",
            user_id, plan.key, plan.days, paid_until.isoformat(),
            plan.base_screenshots, is_trial_transition, payment.id,
        )
        await grant_paid_access(
            session, user_id, paid_until, payment.id,
            base_screenshots=plan.base_screenshots,
            replace_screenshots=is_trial_transition,
        )
        referral_result = await _maybe_grant_referral_bonus(session, user_id, payment.id)
        logger.debug("[GRANT] referral result for payment %s: %s", payment.id, referral_result)
        return GrantResult(**referral_result)

    else:  # pack
        pack = tariffs_config.get_pack(payment.purchase_key)
        logger.info(
            "[GRANT] pack: user_id=%s pack=%s screenshots=%d payment=%s",
            user_id, pack.key, pack.screenshots, payment.id,
        )
        await add_screenshot_pack(session, user_id, pack.screenshots)
        await session.flush()
        return GrantResult()


async def _maybe_grant_referral_bonus(
    session: AsyncSession,
    payer_user_id: uuid.UUID,
    payment_id: uuid.UUID,
) -> dict:
    """Grant bonus days to the referrer on every successful tariff payment by the referred user.

    Idempotency is ensured at the payment level via Payment.goods_granted — this function
    is only ever called once per payment.

    NOTE: grant_paid_access now ADDS screenshots (not replaces), so we pass only
    bonus_screenshots here — the referrer's existing balance is preserved automatically.
    """
    payer = await user_repo.get_user_by_id(session, payer_user_id)
    if payer is None or payer.referred_by_telegram_id is None:
        return {"referrer_telegram_id": None, "referral_bonus_days": 0, "referral_bonus_screenshots": 0}

    referrer = await user_repo.get_user_by_telegram_id(session, payer.referred_by_telegram_id)
    if referrer is None:
        logger.warning("[REFERRAL] referred_by_telegram_id=%s not found in DB",
                       payer.referred_by_telegram_id)
        return {"referrer_telegram_id": None, "referral_bonus_days": 0, "referral_bonus_screenshots": 0}

    referrer_access = (
        await session.execute(select(UserAccess).where(UserAccess.user_id == referrer.id))
    ).scalar_one_or_none()
    if referrer_access is None:
        logger.warning("[REFERRAL] UserAccess not found for referrer id=%s", referrer.id)
        return {"referrer_telegram_id": None, "referral_bonus_days": 0, "referral_bonus_screenshots": 0}

    bonus_days = app_settings.referral_reward_days
    bonus_screenshots = app_settings.referral_reward_screenshots
    now = datetime.datetime.now(datetime.UTC)

    # Extend from current paid_until if referrer's subscription is still active; else from now
    base = referrer_access.paid_until
    if base is not None:
        if base.tzinfo is None:
            base = base.replace(tzinfo=datetime.UTC)
        if base <= now:
            base = now
    else:
        base = now

    new_paid_until = base + datetime.timedelta(days=bonus_days)
    logger.info(
        "[REFERRAL] granting bonus to referrer tg_id=%s (id=%s): +%d days +%d screenshots "
        "new_paid_until=%s referrer_balance_before=%d (payment=%s)",
        payer.referred_by_telegram_id, referrer.id, bonus_days, bonus_screenshots,
        new_paid_until.isoformat(), referrer_access.screenshots_balance, payment_id,
    )
    # Pass only bonus_screenshots — grant_paid_access ADDs to existing balance, not replaces
    await grant_paid_access(
        session, referrer.id, new_paid_until, payment_id,
        base_screenshots=bonus_screenshots,
    )

    # Mark on the payer's access record that their referral bonus was successfully granted
    payer_access = (
        await session.execute(select(UserAccess).where(UserAccess.user_id == payer_user_id))
    ).scalar_one_or_none()
    if payer_access and not payer_access.referral_bonus_granted:
        payer_access.referral_bonus_granted = True
        logger.debug("[REFERRAL] referral_bonus_granted set for payer user_id=%s", payer_user_id)

    await session.flush()

    return {
        "referrer_telegram_id": payer.referred_by_telegram_id,
        "referral_bonus_days": bonus_days,
        "referral_bonus_screenshots": bonus_screenshots,
    }


async def _send_success_notification(bot: Bot, payment: Payment, grant_result: GrantResult) -> None:
    """Send Telegram message to buyer (and referrer if bonus was credited)."""
    try:
        user = await _get_telegram_id_for_user(bot, payment.user_id)
        if user:
            if payment.purchase_type == "tariff":
                plan = tariffs_config.get_tariff(payment.purchase_key)
                text = (
                    f"✅ Оплата прошла успешно!\n"
                    f"Подписка активирована на {plan.days} дн.\n"
                    f"Доступно скриншотов: {plan.base_screenshots} шт."
                )
            else:
                pack = tariffs_config.get_pack(payment.purchase_key)
                text = f"✅ Пакет добавлен! +{pack.screenshots} скриншотов к балансу."
            await bot.send_message(chat_id=user, text=text)
    except Exception:
        logger.warning("Could not send success notification for payment %s", payment.id,
                       exc_info=True)

    if grant_result.referrer_telegram_id:
        try:
            await bot.send_message(
                chat_id=grant_result.referrer_telegram_id,
                text=(
                    "🎉 По вашей реферальной ссылке кто-то оформил подписку!\n\n"
                    f"Вам начислено:\n"
                    f"• +{grant_result.referral_bonus_days} дней доступа\n"
                    f"• +{grant_result.referral_bonus_screenshots} скриншотов"
                ),
            )
        except Exception:
            logger.warning("Could not send referral notification to %s",
                           grant_result.referrer_telegram_id, exc_info=True)


async def _send_cancel_notification(bot: Bot, payment: Payment) -> None:
    try:
        user = await _get_telegram_id_for_user(bot, payment.user_id)
        if user:
            await bot.send_message(
                chat_id=user,
                text="❌ Оплата отменена или не прошла. Если это ошибка — попробуйте ещё раз.",
            )
    except Exception:
        logger.warning("Could not send cancel notification for payment %s", payment.id,
                       exc_info=True)


async def _get_telegram_id_for_user(bot: Bot, user_id: uuid.UUID) -> int | None:
    """Resolve Telegram chat_id from our user_id via a quick DB lookup."""
    # We need a session here but don't have one — use the bot's session factory
    from app.db.session import get_session_factory
    factory = get_session_factory()
    async with factory() as session:
        user = await user_repo.get_user_by_id(session, user_id)
        return user.telegram_id if user else None
