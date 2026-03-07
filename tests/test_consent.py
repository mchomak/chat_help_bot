"""Tests for consent gating logic."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.consent_service import give_consent, has_consent


@pytest.mark.asyncio
async def test_consent_not_given_by_default(session: AsyncSession, sample_user) -> None:
    assert await has_consent(session, sample_user.id) is False


@pytest.mark.asyncio
async def test_give_consent(session: AsyncSession, sample_user) -> None:
    await give_consent(session, sample_user.id)
    assert await has_consent(session, sample_user.id) is True


@pytest.mark.asyncio
async def test_give_consent_idempotent(session: AsyncSession, sample_user) -> None:
    await give_consent(session, sample_user.id)
    await give_consent(session, sample_user.id)
    assert await has_consent(session, sample_user.id) is True
