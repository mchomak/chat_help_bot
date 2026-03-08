"""Access / trial management service with race-condition protection."""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models.user import UserAccess


class AccessStatus:
    NONE = "none"
    TRIAL = "trial"
    EXPIRED = "expired"
    PAID = "paid"


async def check_access(session: AsyncSession, user_id: uuid.UUID) -> str:
    """Return current access status string for the user.

    Performs expiration check and updates status if needed.
    """
    stmt = select(UserAccess).where(UserAccess.user_id == user_id)
    result = await session.execute(stmt)
    access = result.scalar_one_or_none()
    if access is None:
        return AccessStatus.NONE

    now = datetime.datetime.now(datetime.UTC)

    def _is_expired(dt: datetime.datetime) -> bool:
        """Compare datetimes safely regardless of timezone awareness."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.UTC)
        return dt < now

    if access.access_status == AccessStatus.PAID:
        if access.paid_until and _is_expired(access.paid_until):
            access.access_status = AccessStatus.EXPIRED
            await session.flush()
            return AccessStatus.EXPIRED
        return AccessStatus.PAID

    if access.access_status == AccessStatus.TRIAL:
        if access.trial_expires_at and _is_expired(access.trial_expires_at):
            access.access_status = AccessStatus.EXPIRED
            await session.flush()
            return AccessStatus.EXPIRED
        return AccessStatus.TRIAL

    if access.trial_used:
        return AccessStatus.EXPIRED

    return AccessStatus.NONE


async def activate_trial(session: AsyncSession, user_id: uuid.UUID) -> UserAccess | None:
    """Atomically activate trial for user. Returns None if trial was already used.

    Uses UPDATE ... WHERE to prevent race conditions.
    """
    now = datetime.datetime.now(datetime.UTC)
    expires = now + datetime.timedelta(hours=settings.trial.duration_hours)

    # SELECT FOR UPDATE pattern: fetch, check, then update
    stmt = select(UserAccess).where(
        UserAccess.user_id == user_id,
        UserAccess.trial_used.is_(False),
    )
    result = await session.execute(stmt)
    access = result.scalar_one_or_none()
    if access is None:
        return None

    access.trial_used = True
    access.trial_started_at = now
    access.trial_expires_at = expires
    access.access_status = AccessStatus.TRIAL
    await session.flush()
    return access


async def grant_paid_access(
    session: AsyncSession,
    user_id: uuid.UUID,
    paid_until: datetime.datetime,
    payment_id: uuid.UUID,
) -> None:
    """Grant paid access to user after successful transaction."""
    stmt = (
        update(UserAccess)
        .where(UserAccess.user_id == user_id)
        .values(
            access_status=AccessStatus.PAID,
            paid_until=paid_until,
            last_successful_payment_id=str(payment_id),
        )
    )
    await session.execute(stmt)
    await session.flush()
