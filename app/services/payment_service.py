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
from app.services.access_service import add_screenshot_pack, grant_paid_access

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
        "Initiating payment: user_id=%s type=%s key=%s amount=%.2f email=%s payment_db_id=%s",
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
        return InitiateResult(payment_id=payment.id, payment_url=result.confirmation_url, error=None)

    except RuntimeError as exc:
        payment.status = PaymentStatus.API_ERROR
        payment.error_message = str(exc)
        await session.commit()
        logger.error("YooKassa API error for payment %s: %s", payment.id, exc)
        return InitiateResult(payment_id=payment.id, payment_url=None, error=str(exc))


async def poll_and_process_payment(
    session: AsyncSession,
    bot: Bot,
    payment_id: uuid.UUID,
) -> str:
    """Fetch current YooKassa status, process if succeeded/canceled. Returns new status."""
    payment = await payment_repo.get_payment(session, payment_id)
    if payment is None:
        return "not_found"

    # Terminal states — nothing to poll
    if payment.status in (PaymentStatus.SUCCEEDED, PaymentStatus.CANCELED, PaymentStatus.FAILED):
        return payment.status

    if payment.yookassa_payment_id is None:
        return payment.status  # api_error — no yookassa id yet

    try:
        yk_status = await yookassa_service.fetch_payment_status(
            shop_id=app_settings.yookassa.shop_id,
            api_key=app_settings.yookassa.api_key,
            yookassa_payment_id=payment.yookassa_payment_id,
        )
    except RuntimeError as exc:
        logger.warning("Failed to poll YooKassa status for %s: %s", payment.id, exc)
        return payment.status

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
    payment = await payment_repo.get_by_yookassa_id(session, yookassa_payment_id)
    if payment is None:
        logger.warning("Webhook for unknown yookassa_payment_id=%s", yookassa_payment_id)
        return

    # Re-verify status directly from YooKassa (don't blindly trust webhook body)
    try:
        yk_status = await yookassa_service.fetch_payment_status(
            shop_id=app_settings.yookassa.shop_id,
            api_key=app_settings.yookassa.api_key,
            yookassa_payment_id=yookassa_payment_id,
        )
    except RuntimeError as exc:
        logger.error("Cannot verify webhook status for %s: %s", yookassa_payment_id, exc)
        return

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
        return  # Already processed — idempotent skip

    payment.status = new_status

    if new_status == PaymentStatus.SUCCEEDED and not payment.goods_granted:
        grant_result = await _grant_goods(session, payment)
        payment.goods_granted = True
        await session.flush()
        await _send_success_notification(bot, payment, grant_result)

    elif new_status in (PaymentStatus.CANCELED, PaymentStatus.FAILED):
        await session.flush()
        await _send_cancel_notification(bot, payment)

    else:
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
        if access and access.paid_until:
            current_until = access.paid_until
            if current_until.tzinfo is None:
                current_until = current_until.replace(tzinfo=datetime.UTC)
            base = current_until if current_until > now else now
        else:
            base = now

        paid_until = base + datetime.timedelta(days=plan.days)
        await grant_paid_access(
            session, user_id, paid_until, payment.id,
            base_screenshots=plan.base_screenshots,
        )
        return GrantResult(**await _maybe_grant_referral_bonus(session, user_id, payment.id))

    else:  # pack
        pack = tariffs_config.get_pack(payment.purchase_key)
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
    """
    payer = await user_repo.get_user_by_id(session, payer_user_id)
    if payer is None or payer.referred_by_telegram_id is None:
        return {"referrer_telegram_id": None, "referral_bonus_days": 0, "referral_bonus_screenshots": 0}

    referrer = await user_repo.get_user_by_telegram_id(session, payer.referred_by_telegram_id)
    if referrer is None:
        return {"referrer_telegram_id": None, "referral_bonus_days": 0, "referral_bonus_screenshots": 0}

    referrer_access = (
        await session.execute(select(UserAccess).where(UserAccess.user_id == referrer.id))
    ).scalar_one_or_none()
    if referrer_access is None:
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
    await grant_paid_access(
        session, referrer.id, new_paid_until, payment_id,
        base_screenshots=referrer_access.screenshots_balance + bonus_screenshots,
    )
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
        logger.warning("Could not send success notification for payment %s", payment.id)

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
            logger.warning("Could not send referral notification to %s", grant_result.referrer_telegram_id)


async def _send_cancel_notification(bot: Bot, payment: Payment) -> None:
    try:
        user = await _get_telegram_id_for_user(bot, payment.user_id)
        if user:
            await bot.send_message(
                chat_id=user,
                text="❌ Оплата отменена или не прошла. Если это ошибка — попробуйте ещё раз.",
            )
    except Exception:
        logger.warning("Could not send cancel notification for payment %s", payment.id)


async def _get_telegram_id_for_user(bot: Bot, user_id: uuid.UUID) -> int | None:
    """Resolve Telegram chat_id from our user_id via a quick DB lookup."""
    # We need a session here but don't have one — use the bot's session factory
    from app.db.session import get_session_factory
    factory = get_session_factory()
    async with factory() as session:
        user = await user_repo.get_user_by_id(session, user_id)
        return user.telegram_id if user else None
