"""Tests for onboarding — user creation and settings update."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import user_repo


@pytest.mark.asyncio
async def test_get_or_create_user_creates_new(session: AsyncSession) -> None:
    user, created = await user_repo.get_or_create_user(
        session, telegram_id=111111,
        defaults={"username": "newuser", "first_name": "New"},
    )
    assert created is True
    assert user.telegram_id == 111111
    assert user.username == "newuser"


@pytest.mark.asyncio
async def test_get_or_create_user_returns_existing(session: AsyncSession) -> None:
    user1, _ = await user_repo.get_or_create_user(session, telegram_id=222222)
    user2, created = await user_repo.get_or_create_user(session, telegram_id=222222)
    assert created is False
    assert user1.id == user2.id


@pytest.mark.asyncio
async def test_update_settings(session: AsyncSession, sample_user) -> None:
    s = await user_repo.update_settings(
        session, sample_user.id,
        gender="male", situation_type="dating_site",
        onboarding_completed=True,
    )
    assert s.gender == "male"
    assert s.situation_type == "dating_site"
    assert s.onboarding_completed is True
