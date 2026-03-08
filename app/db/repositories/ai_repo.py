"""Repository for AI requests and results."""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ai_request import AIRequest, AIResult


async def create_ai_request(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    scenario_type: str,
    input_type: str,
    model_name: str,
    input_text: str | None = None,
    image_file_id: str | None = None,
    image_mime_type: str | None = None,
    image_size: int | None = None,
    image_width: int | None = None,
    image_height: int | None = None,
    modifier: str | None = None,
    parent_request_id: uuid.UUID | None = None,
) -> AIRequest:
    req = AIRequest(
        user_id=user_id,
        scenario_type=scenario_type,
        input_type=input_type,
        input_text=input_text,
        image_file_id=image_file_id,
        image_mime_type=image_mime_type,
        image_size=image_size,
        image_width=image_width,
        image_height=image_height,
        model_name=model_name,
        modifier=modifier,
        parent_request_id=parent_request_id,
    )
    session.add(req)
    await session.flush()
    return req


async def finish_ai_request(
    session: AsyncSession,
    request_id: uuid.UUID,
    status: str,
) -> None:
    stmt = select(AIRequest).where(AIRequest.id == request_id)
    result = await session.execute(stmt)
    req = result.scalar_one()
    req.status = status
    req.finished_at = datetime.datetime.now(datetime.UTC)
    await session.flush()


async def save_ai_result(
    session: AsyncSession,
    *,
    request_id: uuid.UUID,
    raw_response: str | None = None,
    normalized_response: dict | None = None,
    error_text: str | None = None,
) -> AIResult:
    res = AIResult(
        request_id=request_id,
        raw_response=raw_response,
        normalized_response=normalized_response,
        error_text=error_text,
    )
    session.add(res)
    await session.flush()
    return res


async def get_ai_request(session: AsyncSession, request_id: uuid.UUID) -> AIRequest | None:
    stmt = select(AIRequest).where(AIRequest.id == request_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
