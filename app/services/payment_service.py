"""Payment service — stub implementation for MVP."""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User, UserAccess
from app.db.repositories import transaction_repo, user_repo
from app.services.access_service import grant_paid_access


@dataclass
class PaymentResult:
    success: bool
    # If a referral bonus was credited, this is the referrer's Telegram ID
    referrer_telegram_id: int | None = None
    referral_bonus_days: int = 0


async def create_stub_payment(
    session: AsyncSession,
    user_id: uuid.UUID,
    amount: float = 299.0,
) -> uuid.UUID:
    """Create a pending stub transaction. Returns transaction ID."""
    tx = await transaction_repo.create_transaction(
        session,
        user_id=user_id,
        amount=amount,
        provider="stub",
        comment="Stub payment for testing",
    )
    return tx.id


async def confirm_stub_payment(
    session: AsyncSession,
    tx_id: uuid.UUID,
    user_id: uuid.UUID,
    days: int = 30,
) -> PaymentResult:
    """Confirm stub payment and grant access.

    Also credits referral bonus to the referrer (once per user, guarded by
    ``referral_bonus_granted`` flag). Returns a ``PaymentResult`` with details.
    Prevents double granting via access_granted flag on the transaction.
    """
    tx = await transaction_repo.complete_transaction(session, tx_id, status="success")
    if tx is None:
        return PaymentResult(success=False)
    if tx.access_granted:
        return PaymentResult(success=False)

    tx.access_granted = True
    paid_until = datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=days)
    await grant_paid_access(session, user_id, paid_until, tx.id)

    # --- Referral bonus ---
    referrer_telegram_id: int | None = None
    referral_bonus_days: int = 0

    # Fetch the payer's user record to check if they were referred
    payer = await user_repo.get_user_by_id(session, user_id)
    if payer is not None and payer.referred_by_telegram_id is not None:
        # Check that we haven't already credited the bonus for this user
        payer_access_stmt = select(UserAccess).where(UserAccess.user_id == user_id)
        payer_access_result = await session.execute(payer_access_stmt)
        payer_access = payer_access_result.scalar_one_or_none()

        if payer_access is not None and not payer_access.referral_bonus_granted:
            # Locate the referrer
            referrer = await user_repo.get_user_by_telegram_id(
                session, payer.referred_by_telegram_id,
            )
            if referrer is not None:
                from app.config import settings as app_settings
                bonus_days = app_settings.referral_reward_days

                # Extend / grant paid access to the referrer
                referrer_access_stmt = select(UserAccess).where(
                    UserAccess.user_id == referrer.id,
                )
                referrer_access_result = await session.execute(referrer_access_stmt)
                referrer_access = referrer_access_result.scalar_one_or_none()

                if referrer_access is not None:
                    now = datetime.datetime.now(datetime.UTC)
                    # Base: either current paid_until or now
                    base = referrer_access.paid_until
                    if base is None or base < now:
                        base = now
                    new_paid_until = base + datetime.timedelta(days=bonus_days)
                    await grant_paid_access(session, referrer.id, new_paid_until, tx.id)

                    # Mark bonus as granted so we don't double-credit
                    payer_access.referral_bonus_granted = True
                    await session.flush()

                    referrer_telegram_id = payer.referred_by_telegram_id
                    referral_bonus_days = bonus_days

    return PaymentResult(
        success=True,
        referrer_telegram_id=referrer_telegram_id,
        referral_bonus_days=referral_bonus_days,
    )
