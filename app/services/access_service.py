"""Access / trial management service with race-condition protection."""

from __future__ import annotations

import datetime
import logging
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import tariffs_config
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
                "[ACCESS] check_access: paid subscription EXPIRED user_id=%s "
                "paid_until=%s screenshots_zeroed=%d → 0",
                user_id, access.paid_until.isoformat(), access.screenshots_balance,
            )
            access.access_status = AccessStatus.EXPIRED
            access.screenshots_balance = 0  # all screenshots (plan + packs) burn on expiry
            await session.flush()
            return AccessStatus.EXPIRED
        logger.debug(
            "[ACCESS] check_access: paid active user_id=%s paid_until=%s screenshots=%d",
            user_id, access.paid_until.isoformat() if access.paid_until else None,
            access.screenshots_balance,
        )
        return AccessStatus.PAID

    if access.access_status == AccessStatus.TRIAL:
        if access.trial_expires_at and _is_expired(access.trial_expires_at):
            logger.info(
                "[ACCESS] check_access: trial EXPIRED user_id=%s "
                "trial_expires_at=%s screenshots_zeroed=%d → 0",
                user_id, access.trial_expires_at.isoformat(), access.screenshots_balance,
            )
            access.access_status = AccessStatus.EXPIRED
            access.screenshots_balance = 0  # trial screenshots burn on expiry
            await session.flush()
            return AccessStatus.EXPIRED
        logger.debug(
            "[ACCESS] check_access: trial active user_id=%s trial_expires_at=%s screenshots=%d",
            user_id,
            access.trial_expires_at.isoformat() if access.trial_expires_at else None,
            access.screenshots_balance,
        )
        return AccessStatus.TRIAL

    if access.trial_used:
        return AccessStatus.EXPIRED

    return AccessStatus.NONE


async def activate_trial(session: AsyncSession, user_id: uuid.UUID) -> UserAccess | None:
    """Atomically activate trial for user. Returns None if trial was already used.

    Sets screenshots_balance to TRIAL_SCREENSHOTS (defined in tariffs_config).
    Trial screenshots are intentionally fewer than a paid plan to keep them distinct.
    """
    now = datetime.datetime.now(datetime.UTC)
    expires = now + datetime.timedelta(hours=tariffs_config.TRIAL_DURATION_HOURS)

    stmt = select(UserAccess).where(
        UserAccess.user_id == user_id,
        UserAccess.trial_used.is_(False),
    )
    result = await session.execute(stmt)
    access = result.scalar_one_or_none()
    if access is None:
        logger.debug("[ACCESS] activate_trial: trial already used or no record for user_id=%s", user_id)
        return None

    trial_screenshots = tariffs_config.TRIAL_SCREENSHOTS
    access.trial_used = True
    access.trial_started_at = now
    access.trial_expires_at = expires
    access.access_status = AccessStatus.TRIAL
    access.screenshots_balance = trial_screenshots
    await session.flush()

    logger.info(
        "[ACCESS] trial activated: user_id=%s duration_hours=%d "
        "expires=%s trial_screenshots=%d",
        user_id, tariffs_config.TRIAL_DURATION_HOURS,
        expires.isoformat(), trial_screenshots,
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

    replace_screenshots=False (default): ADD base_screenshots to existing balance.
      Used for active subscription renewals so that previously purchased packs
      are not lost.

    replace_screenshots=True: SET balance to exactly base_screenshots.
      Used for:
        - trial → paid transitions (trial screenshots must not sum with paid plan)
        - expired subscription renewals (stale screenshots must be zeroed first)
        - fresh first-time paid subscriptions
    """
    # Read current balance for before/after logging
    current_result = await session.execute(
        select(UserAccess.screenshots_balance).where(UserAccess.user_id == user_id)
    )
    balance_before = current_result.scalar_one_or_none() or 0
    balance_after = base_screenshots if replace_screenshots else balance_before + base_screenshots

    logger.info(
        "[ACCESS] grant_paid_access: user_id=%s payment_id=%s "
        "paid_until=%s replace_screenshots=%s "
        "screenshots: %d → %d (base_screenshots=%d)",
        user_id, payment_id, paid_until.isoformat(),
        replace_screenshots, balance_before, balance_after, base_screenshots,
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

    logger.info(
        "[ACCESS] grant_paid_access DONE: user_id=%s rows_updated=%d "
        "access_status=paid paid_until=%s screenshots_balance: %d → %d",
        user_id, result.rowcount, paid_until.isoformat(), balance_before, balance_after,
    )
    if result.rowcount == 0:
        logger.error(
            "[ACCESS] grant_paid_access UPDATE affected 0 rows for user_id=%s "
            "— UserAccess record may be missing!",
            user_id,
        )


async def add_screenshot_pack(
    session: AsyncSession,
    user_id: uuid.UUID,
    screenshots: int,
) -> None:
    """Add paid screenshots to user's balance (screenshot pack purchase).

    Pack screenshots are always ADDED to the existing balance, regardless of
    whether the user is on trial or paid subscription. They are zeroed together
    with the subscription balance when the paid subscription expires.
    """
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
        "[ACCESS] add_screenshot_pack DONE: user_id=%s rows_updated=%d "
        "screenshots_balance: %d → %d",
        user_id, result.rowcount, balance_before, balance_before + screenshots,
    )
    if result.rowcount == 0:
        logger.error(
            "[ACCESS] add_screenshot_pack UPDATE affected 0 rows for user_id=%s "
            "— UserAccess record may be missing!",
            user_id,
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
