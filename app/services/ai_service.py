"""High-level AI service orchestrating prompt building, API calls, and result persistence."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import chat_completion
from app.ai.prompt_builder import build_messages
from app.ai.response_parser import (
    parse_first_message_response,
    parse_profile_review_response,
    parse_reply_response,
)
from app.config import settings
from app.db.repositories import ai_repo

logger = logging.getLogger(__name__)

SCENARIO_PARSERS = {
    "reply_message": parse_reply_response,
    "first_message": parse_first_message_response,
    "profile_review": parse_profile_review_response,
}


async def generate(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    scenario: str,
    input_text: str | None = None,
    image_base64: str | None = None,
    image_file_id: str | None = None,
    image_mime_type: str | None = None,
    image_size: int | None = None,
    modifier: str | None = None,
    parent_request_id: uuid.UUID | None = None,
    gender: str | None = None,
    communication_style: str | None = None,
    ai_identity_text: str | None = None,
    count: int = 4,
) -> dict:
    """Run full AI generation pipeline. Returns parsed result dict.

    Result shape depends on scenario:
    - reply_message / first_message: {"items": [...]}
    - profile_review: {"strengths": [...], "weaknesses": [...], ...}
    """
    has_image = image_base64 is not None
    input_type = "text"
    if has_image and input_text:
        input_type = "text_image"
    elif has_image:
        input_type = "image"

    model_name = settings.ai.vision_model if has_image else settings.ai.default_model

    # Persist request
    ai_req = await ai_repo.create_ai_request(
        session,
        user_id=user_id,
        scenario_type=scenario,
        input_type=input_type,
        model_name=model_name,
        input_text=input_text,
        image_file_id=image_file_id,
        image_mime_type=image_mime_type,
        image_size=image_size,
        modifier=modifier,
        parent_request_id=parent_request_id,
    )
    await session.commit()

    try:
        messages = build_messages(
            scenario=scenario,
            input_text=input_text,
            has_image=has_image,
            image_base64=image_base64,
            modifier=modifier,
            count=count,
            gender=gender,
            communication_style=communication_style,
            ai_identity_text=ai_identity_text,
        )

        raw_response = await chat_completion(messages, model=model_name, has_image=has_image)

        parser = SCENARIO_PARSERS.get(scenario)
        if parser:
            parsed = parser(raw_response)
        else:
            parsed = {"raw": raw_response}

        # Normalise to a consistent shape
        if isinstance(parsed, list):
            normalized = {"items": parsed}
        else:
            normalized = parsed

        await ai_repo.save_ai_result(
            session,
            request_id=ai_req.id,
            raw_response=raw_response,
            normalized_response=normalized,
        )
        await ai_repo.finish_ai_request(session, ai_req.id, status="completed")
        await session.commit()

        # Attach request_id so callers can reference it
        normalized["request_id"] = str(ai_req.id)
        return normalized

    except Exception as exc:
        logger.exception("AI generation failed for request %s", ai_req.id)
        await ai_repo.save_ai_result(
            session,
            request_id=ai_req.id,
            error_text=str(exc),
        )
        await ai_repo.finish_ai_request(session, ai_req.id, status="failed")
        await session.commit()
        raise
