"""Shared test fixtures using in-memory SQLite for speed."""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.models.base import Base
from app.db.models.user import User, UserAccess, UserConsent, UserSettings


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine):
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s


@pytest_asyncio.fixture
async def sample_user(session: AsyncSession) -> User:
    """Create and return a sample user with related rows."""
    user = User(telegram_id=123456789, username="testuser", first_name="Test")
    session.add(user)
    await session.flush()

    settings = UserSettings(user_id=str(user.id))
    consent = UserConsent(user_id=str(user.id))
    access = UserAccess(user_id=str(user.id))
    session.add_all([settings, consent, access])
    await session.flush()
    return user
