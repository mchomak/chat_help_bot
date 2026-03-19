"""Payment service — stub implementation for MVP."""

from __future__ import annotations

import datetime
import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as app_settings
from app.db.models.user import User, UserAccess
from app.db.repositories import transaction_repo, user_repo
from app.services.access_service import (
    add_screenshot_pack,
    grant_paid_access,
)

logger = logging.getLogger(__name__)


@dataclass
class PaymentResult:
    success: bool
    # Set if a referral bonus was credited — used by the handler to send a notification
    referrer_telegram_id: int | None = None
    referral_bonus_days: int = 0
    referral_bonus_screenshots: int = 0


async def create_stub_payment(
    session: AsyncSession,
    user_id: uuid.UUID,
    amount: float,
    comment: str = "Stub payment",
) -> uuid.UUID:
    """Create a pending stub transaction. Returns transaction ID."""
    tx = await transaction_repo.create_transaction(
        session,
        user_id=user_id,
        amount=amount,
        provider="stub",
        comment=comment,
    )
    return tx.id


async def confirm_tariff_payment(
    session: AsyncSession,
    tx_id: uuid.UUID,
    user_id: uuid.UUID,
    tariff_key: str,
) -> PaymentResult:
    """Confirm a subscription tariff payment.

    Grants paid access, resets screenshots_balance to tariff base.
    Credits referral bonus (once per user) and returns notification data.
    Prevents double granting via access_granted flag on the transaction.
    """
    tx = await transaction_repo.complete_transaction(session, tx_id, status="success")
    if tx is None or tx.access_granted:
        return PaymentResult(success=False)

    tx.access_granted = True

    price, days, base_screenshots = app_settings.tariffs.get_tariff(tariff_key)
    paid_until = datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=days)
    await grant_paid_access(session, user_id, paid_until, tx.id, base_screenshots=base_screenshots)

    return PaymentResult(
        success=True,
        **await _maybe_grant_referral_bonus(session, user_id, tx.id),
    )


async def confirm_pack_payment(
    session: AsyncSession,
    tx_id: uuid.UUID,
    user_id: uuid.UUID,
    pack_key: str,
) -> PaymentResult:
    """Confirm a screenshot pack payment. Adds screenshots to user's balance.

    Prevents double granting via access_granted flag.
    """
    tx = await transaction_repo.complete_transaction(session, tx_id, status="success")
    if tx is None or tx.access_granted:
        return PaymentResult(success=False)

    tx.access_granted = True

    _price, screenshots = app_settings.tariffs.get_pack(pack_key)
    await add_screenshot_pack(session, user_id, screenshots)
    await session.flush()

    return PaymentResult(success=True)


async def _maybe_grant_referral_bonus(
    session: AsyncSession,
    payer_user_id: uuid.UUID,
    tx_id: uuid.UUID,
) -> dict:
    """Credit referral bonus to referrer if applicable. Returns dict for PaymentResult kwargs."""
    payer = await user_repo.get_user_by_id(session, payer_user_id)
    if payer is None or payer.referred_by_telegram_id is None:
        return {"referrer_telegram_id": None, "referral_bonus_days": 0, "referral_bonus_screenshots": 0}

    # Fetch payer's access to check if bonus was already granted
    payer_access_stmt = select(UserAccess).where(UserAccess.user_id == payer_user_id)
    payer_access = (await session.execute(payer_access_stmt)).scalar_one_or_none()
    if payer_access is None or payer_access.referral_bonus_granted:
        return {"referrer_telegram_id": None, "referral_bonus_days": 0, "referral_bonus_screenshots": 0}

    referrer = await user_repo.get_user_by_telegram_id(session, payer.referred_by_telegram_id)
    if referrer is None:
        return {"referrer_telegram_id": None, "referral_bonus_days": 0, "referral_bonus_screenshots": 0}

    referrer_access_stmt = select(UserAccess).where(UserAccess.user_id == referrer.id)
    referrer_access = (await session.execute(referrer_access_stmt)).scalar_one_or_none()
    if referrer_access is None:
        return {"referrer_telegram_id": None, "referral_bonus_days": 0, "referral_bonus_screenshots": 0}

    bonus_days = app_settings.referral_reward_days
    bonus_screenshots = app_settings.referral_reward_screenshots
    now = datetime.datetime.now(datetime.UTC)

    # Extend referrer's paid_until
    base = referrer_access.paid_until
    if base is None or (base.tzinfo is None and base < now) or (base.tzinfo is not None and base < now):
        base = now
    new_paid_until = base + datetime.timedelta(days=bonus_days)
    await grant_paid_access(session, referrer.id, new_paid_until, tx_id,
                            base_screenshots=referrer_access.screenshots_balance + bonus_screenshots)

    # Mark bonus as granted to prevent double-credit
    payer_access.referral_bonus_granted = True
    await session.flush()

    return {
        "referrer_telegram_id": payer.referred_by_telegram_id,
        "referral_bonus_days": bonus_days,
        "referral_bonus_screenshots": bonus_screenshots,
    }
