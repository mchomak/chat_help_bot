"""Tests for AI request/result persistence."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import ai_repo


@pytest.mark.asyncio
async def test_create_and_finish_ai_request(session: AsyncSession, sample_user) -> None:
    req = await ai_repo.create_ai_request(
        session,
        user_id=sample_user.id,
        scenario_type="reply_message",
        input_type="text",
        model_name="gpt-4o",
        input_text="Привет, как дела?",
    )
    assert req.status == "pending"
    assert req.scenario_type == "reply_message"

    await ai_repo.finish_ai_request(session, req.id, status="completed")
    updated = await ai_repo.get_ai_request(session, req.id)
    assert updated.status == "completed"
    assert updated.finished_at is not None


@pytest.mark.asyncio
async def test_save_ai_result(session: AsyncSession, sample_user) -> None:
    req = await ai_repo.create_ai_request(
        session,
        user_id=sample_user.id,
        scenario_type="first_message",
        input_type="text",
        model_name="gpt-4o",
    )
    res = await ai_repo.save_ai_result(
        session,
        request_id=req.id,
        raw_response='{"messages": ["Hi!"]}',
        normalized_response={"items": ["Hi!"]},
    )
    assert res.request_id == req.id
    assert res.normalized_response == {"items": ["Hi!"]}
