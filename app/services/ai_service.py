"""High-level AI service orchestrating prompt building, API calls, and result persistence."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import chat_completion
from app.ai.prompt_builder import build_messages
from app.ai.response_parser import (
    parse_analyzer_response,
    parse_first_message_response,
    parse_messages_response,
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
    "analyzer": parse_analyzer_response,
    "anti_ignor": parse_messages_response,
    "photo_pickup": parse_messages_response,
    "flirt": parse_reply_response,
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
    style: str | None = None,
    modifier: str | None = None,
    extra_context: str | None = None,
    parent_request_id: uuid.UUID | None = None,
    gender: str | None = None,
    situation_type: str | None = None,
    communication_role: str | None = None,
    communication_style: str | None = None,
    ai_identity_text: str | None = None,
    count: int = 4,
) -> dict:
    """Run full AI generation pipeline. Returns parsed result dict.

    Result shape: {"items": [...], "analysis": [...] (optional), "request_id": "..."}
    """
    has_image = image_base64 is not None
    input_type = "text"
    if has_image and input_text:
        input_type = "text_image"
    elif has_image:
        input_type = "image"

    model_name = settings.ai.vision_model if has_image else settings.ai.default_model

    logger.info(
        "generate: scenario=%s, input_type=%s, style=%s, model=%s, "
        "has_text=%s, has_image=%s, user_id=%s",
        scenario, input_type, style, model_name,
        bool(input_text), has_image, user_id,
    )

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
        modifier=style or modifier,
        parent_request_id=parent_request_id,
    )
    await session.commit()
    logger.info("generate: created ai_request id=%s", ai_req.id)

    try:
        messages = build_messages(
            scenario=scenario,
            input_text=input_text,
            has_image=has_image,
            image_base64=image_base64,
            style=style,
            modifier=modifier,
            extra_context=extra_context,
            count=count,
            gender=gender,
            situation_type=situation_type,
            communication_role=communication_role,
            ai_identity_text=ai_identity_text,
            communication_style=communication_style,
        )
        logger.info(
            "generate: built %d messages for scenario=%s (system len=%d)",
            len(messages), scenario,
            len(messages[0]["content"]) if messages else 0,
        )

        raw_response = await chat_completion(messages, model=model_name, has_image=has_image)
        logger.info(
            "generate: got raw response, len=%d, preview=%.200s",
            len(raw_response), raw_response[:200],
        )

        parser = SCENARIO_PARSERS.get(scenario)
        if parser is None:
            logger.error(
                "generate: no parser registered for scenario=%s — "
                "response will lack 'items' key; raw response saved",
                scenario,
            )
            parsed = {"raw": raw_response}
        else:
            parsed = parser(raw_response)
            logger.info(
                "generate: parsed result type=%s, keys=%s",
                type(parsed).__name__,
                list(parsed.keys()) if isinstance(parsed, dict) else f"list[{len(parsed)}]",
            )

        # Normalise to a consistent shape
        if isinstance(parsed, list):
            normalized = {"items": parsed}
        else:
            normalized = parsed

        items = normalized.get("items", [])
        if not items:
            logger.warning(
                "generate: parsed result has no items for scenario=%s, "
                "normalized_keys=%s, raw_preview=%.300s",
                scenario, list(normalized.keys()), raw_response[:300],
            )

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
        logger.info(
            "generate: completed request=%s, items_count=%d",
            ai_req.id, len(items),
        )
        return normalized

    except Exception as exc:
        logger.exception(
            "generate: FAILED for request=%s, scenario=%s, error=%s",
            ai_req.id, scenario, exc,
        )
        await ai_repo.save_ai_result(
            session,
            request_id=ai_req.id,
            error_text=str(exc),
        )
        await ai_repo.finish_ai_request(session, ai_req.id, status="failed")
        await session.commit()
        raise
