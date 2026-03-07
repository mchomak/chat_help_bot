"""User repository — CRUD for User, UserSettings, UserConsent, UserAccess."""

from __future__ import annotations

import datetime
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User, UserAccess, UserConsent, UserSettings


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    defaults: dict[str, Any] | None = None,
) -> tuple[User, bool]:
    """Return (user, created) pair. Atomically insert if absent."""
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if user is not None:
        return user, False

    defaults = defaults or {}
    user = User(telegram_id=telegram_id, **defaults)
    session.add(user)
    await session.flush()

    # create related rows
    settings = UserSettings(user_id=str(user.id))
    consent = UserConsent(user_id=str(user.id))
    access = UserAccess(user_id=str(user.id))
    session.add_all([settings, consent, access])
    await session.flush()
    return user, True


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def update_user_fields(
    session: AsyncSession, user: User, **kwargs: Any,
) -> User:
    for k, v in kwargs.items():
        setattr(user, k, v)
    await session.flush()
    return user


async def get_user_settings(session: AsyncSession, user_id: uuid.UUID) -> UserSettings | None:
    stmt = select(UserSettings).where(UserSettings.user_id == str(user_id))
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def update_settings(
    session: AsyncSession, user_id: uuid.UUID, **kwargs: Any,
) -> UserSettings:
    us = await get_user_settings(session, user_id)
    if us is None:
        us = UserSettings(user_id=str(user_id), **kwargs)
        session.add(us)
    else:
        for k, v in kwargs.items():
            setattr(us, k, v)
    await session.flush()
    return us


async def get_consent(session: AsyncSession, user_id: uuid.UUID) -> UserConsent | None:
    stmt = select(UserConsent).where(UserConsent.user_id == str(user_id))
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def set_consent(session: AsyncSession, user_id: uuid.UUID) -> UserConsent:
    uc = await get_consent(session, user_id)
    if uc is None:
        uc = UserConsent(
            user_id=str(user_id),
            consent_given=True,
            consented_at=datetime.datetime.now(datetime.UTC),
        )
        session.add(uc)
    else:
        uc.consent_given = True
        uc.consented_at = datetime.datetime.now(datetime.UTC)
    await session.flush()
    return uc


async def get_access(session: AsyncSession, user_id: uuid.UUID) -> UserAccess | None:
    stmt = select(UserAccess).where(UserAccess.user_id == str(user_id))
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
