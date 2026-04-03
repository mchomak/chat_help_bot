"""Access / trial management service with race-condition protection."""

from __future__ import annotations

import datetime
import logging
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models.user import UserAccess

logger = logging.getLogger(__name__)


class AccessStatus:
    NONE = "none"
    TRIAL = "trial"
    EXPIRED = "expired"
    PAID = "paid"


async def check_access(session: AsyncSession, user_id: uuid.UUID) -> str:
    """Return current access status string for the user.

    Performs expiration check and updates status + screenshots_balance if needed.
    """
    stmt = select(UserAccess).where(UserAccess.user_id == user_id)
    result = await session.execute(stmt)
    access = result.scalar_one_or_none()
    if access is None:
        logger.debug("[ACCESS] check_access: no UserAccess record for user_id=%s", user_id)
        return AccessStatus.NONE

    now = datetime.datetime.now(datetime.UTC)

    def _is_expired(dt: datetime.datetime) -> bool:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.UTC)
        return dt < now

    if access.access_status == AccessStatus.PAID:
        if access.paid_until and _is_expired(access.paid_until):
            logger.info(
                "[ACCESS] paid subscription expired: user_id=%s paid_until=%s screenshots_before=%d",
                user_id, access.paid_until.isoformat(), access.screenshots_balance,
            )
            access.access_status = AccessStatus.EXPIRED
            access.screenshots_balance = 0  # unused screenshots burn on expiry
            await session.flush()
            return AccessStatus.EXPIRED
        return AccessStatus.PAID

    if access.access_status == AccessStatus.TRIAL:
        if access.trial_expires_at and _is_expired(access.trial_expires_at):
            logger.info(
                "[ACCESS] trial expired: user_id=%s trial_expires_at=%s screenshots_before=%d",
                user_id, access.trial_expires_at.isoformat(), access.screenshots_balance,
            )
            access.access_status = AccessStatus.EXPIRED
            access.screenshots_balance = 0  # trial screenshots burn on expiry
            await session.flush()
            return AccessStatus.EXPIRED
        return AccessStatus.TRIAL

    if access.trial_used:
        return AccessStatus.EXPIRED

    return AccessStatus.NONE


async def activate_trial(session: AsyncSession, user_id: uuid.UUID) -> UserAccess | None:
    """Atomically activate trial for user. Returns None if trial was already used.

    Sets screenshots_balance to the configured trial limit (trial_image_limit).
    Trial gives fewer screenshots than a paid subscription to keep them distinct.
    """
    now = datetime.datetime.now(datetime.UTC)
    expires = now + datetime.timedelta(hours=settings.trial.duration_hours)

    stmt = select(UserAccess).where(
        UserAccess.user_id == user_id,
        UserAccess.trial_used.is_(False),
    )
    result = await session.execute(stmt)
    access = result.scalar_one_or_none()
    if access is None:
        logger.debug("[ACCESS] activate_trial: trial already used or no record for user_id=%s", user_id)
        return None

    trial_screenshots = settings.trial_image_limit  # default 100, NOT monthly_image_limit (300)
    access.trial_used = True
    access.trial_started_at = now
    access.trial_expires_at = expires
    access.access_status = AccessStatus.TRIAL
    access.screenshots_balance = trial_screenshots
    await session.flush()

    logger.info(
        "[ACCESS] trial activated: user_id=%s expires=%s screenshots=%d",
        user_id, expires.isoformat(), trial_screenshots,
    )
    return access


async def grant_paid_access(
    session: AsyncSession,
    user_id: uuid.UUID,
    paid_until: datetime.datetime,
    payment_id: uuid.UUID,
    base_screenshots: int = 0,
    replace_screenshots: bool = False,
) -> None:
    """Grant paid access to user after successful transaction.

    IMPORTANT: screenshots_balance is ADDED to (not replaced) so that previously
    purchased screenshot packs are not lost when renewing a subscription.
    Screenshots only burn to zero when the subscription period actually expires
    (handled in check_access).

    replace_screenshots=True is used when transitioning from trial to a paid
    subscription so that trial screenshots are not summed with the paid plan.
    """
    # Read current balance for before/after logging
    current_result = await session.execute(
        select(UserAccess.screenshots_balance).where(UserAccess.user_id == user_id)
    )
    balance_before = current_result.scalar_one_or_none() or 0

    logger.info(
        "[ACCESS] grant_paid_access: user_id=%s paid_until=%s +screenshots=%d "
        "replace_screenshots=%s balance_before=%d payment_id=%s",
        user_id, paid_until.isoformat(), base_screenshots,
        replace_screenshots, balance_before, payment_id,
    )

    new_balance = base_screenshots if replace_screenshots else UserAccess.screenshots_balance + base_screenshots

    stmt = (
        update(UserAccess)
        .where(UserAccess.user_id == user_id)
        .values(
            access_status=AccessStatus.PAID,
            paid_until=paid_until,
            last_successful_payment_id=str(payment_id),
            screenshots_balance=new_balance,
        )
    )
    result = await session.execute(stmt)
    await session.flush()

    balance_after = base_screenshots if replace_screenshots else balance_before + base_screenshots
    logger.info(
        "[ACCESS] grant_paid_access done: user_id=%s rows_updated=%d "
        "screenshots_balance: %d → %d paid_until=%s",
        user_id, result.rowcount, balance_before, balance_after, paid_until.isoformat(),
    )


async def add_screenshot_pack(
    session: AsyncSession,
    user_id: uuid.UUID,
    screenshots: int,
) -> None:
    """Add screenshots to user's balance (screenshot pack purchase)."""
    # Read current balance for logging
    current_result = await session.execute(
        select(UserAccess.screenshots_balance).where(UserAccess.user_id == user_id)
    )
    balance_before = current_result.scalar_one_or_none() or 0

    logger.info(
        "[ACCESS] add_screenshot_pack: user_id=%s +screenshots=%d balance_before=%d",
        user_id, screenshots, balance_before,
    )

    stmt = (
        update(UserAccess)
        .where(UserAccess.user_id == user_id)
        .values(screenshots_balance=UserAccess.screenshots_balance + screenshots)
    )
    result = await session.execute(stmt)
    await session.flush()

    logger.info(
        "[ACCESS] add_screenshot_pack done: user_id=%s rows_updated=%d "
        "screenshots_balance: %d → %d",
        user_id, result.rowcount, balance_before, balance_before + screenshots,
    )


async def decrement_screenshot_balance(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    mode: str = "unknown",
    file_type: str = "unknown",
) -> None:
    """Decrement screenshots_balance by 1 (clamped at 0). Called after a successful image generation.

    Args:
        mode: scenario name (e.g. "profile_review", "first_message")
        file_type: "photo" or "document"
    """
    # Read current balance for before/after logging
    current_result = await session.execute(
        select(UserAccess.screenshots_balance).where(UserAccess.user_id == user_id)
    )
    balance_before = current_result.scalar_one_or_none() or 0

    stmt = (
        update(UserAccess)
        .where(UserAccess.user_id == user_id, UserAccess.screenshots_balance > 0)
        .values(screenshots_balance=UserAccess.screenshots_balance - 1)
    )
    result = await session.execute(stmt)
    await session.flush()

    if result.rowcount > 0:
        logger.info(
            "[SCREENSHOT] deducted: user_id=%s mode=%s file_type=%s balance: %d → %d",
            user_id, mode, file_type, balance_before, balance_before - 1,
        )
    else:
        logger.warning(
            "[SCREENSHOT] deduct skipped (balance already 0): user_id=%s mode=%s file_type=%s",
            user_id, mode, file_type,
        )
