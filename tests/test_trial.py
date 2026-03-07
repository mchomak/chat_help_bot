"""Tests for trial activation and expiration."""

from __future__ import annotations

import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import UserAccess
from app.services.access_service import (
    AccessStatus,
    activate_trial,
    check_access,
)


@pytest.mark.asyncio
async def test_initial_access_is_none(session: AsyncSession, sample_user) -> None:
    status = await check_access(session, sample_user.id)
    assert status == AccessStatus.NONE


@pytest.mark.asyncio
async def test_activate_trial(session: AsyncSession, sample_user) -> None:
    access = await activate_trial(session, sample_user.id)
    assert access is not None
    assert access.trial_used is True
    assert access.access_status == AccessStatus.TRIAL


@pytest.mark.asyncio
async def test_trial_cannot_be_activated_twice(session: AsyncSession, sample_user) -> None:
    await activate_trial(session, sample_user.id)
    second = await activate_trial(session, sample_user.id)
    assert second is None


@pytest.mark.asyncio
async def test_expired_trial(session: AsyncSession, sample_user) -> None:
    await activate_trial(session, sample_user.id)

    # Manually expire the trial
    stmt = select(UserAccess).where(UserAccess.user_id == str(sample_user.id))
    result = await session.execute(stmt)
    access = result.scalar_one()
    access.trial_expires_at = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=1)
    await session.flush()

    status = await check_access(session, sample_user.id)
    assert status == AccessStatus.EXPIRED
