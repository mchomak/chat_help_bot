"""Consent management service."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import user_repo


async def has_consent(session: AsyncSession, user_id: uuid.UUID) -> bool:
    consent = await user_repo.get_consent(session, user_id)
    return consent is not None and consent.consent_given


async def give_consent(session: AsyncSession, user_id: uuid.UUID) -> None:
    await user_repo.set_consent(session, user_id)
