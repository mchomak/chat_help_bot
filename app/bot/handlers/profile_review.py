"""Handler for the "Profile review" scenario."""

from __future__ import annotations

import logging
import uuid

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.common import ensure_access, ensure_consent, ensure_image_limit
from app.bot.keyboards.scenarios import error_with_retry_keyboard, profile_result_keyboard
from app.bot.states.scenarios import ProfileReviewStates
from app.db.repositories import user_repo
from app.services import ai_service
from app.services.access_service import decrement_screenshot_balance
from app.services.image_service import download_telegram_photo, photo_bytes_to_base64

router = Router(name="profile_review")
logger = logging.getLogger(__name__)

_SCENARIO = "profile_review"


def _settings_kwargs(settings) -> dict:
    if settings is None:
        return {}
    return {
        "gender": settings.gender,
        "communication_style": settings.communication_style,
        "ai_identity_text": settings.ai_identity_text,
    }


@router.callback_query(F.data == "menu:profile_review")
async def start_profile_review(
    callback: types.CallbackQuery,
    state: FSMContext,
    db_session: AsyncSession,
) -> None:
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])

    if not await ensure_consent(callback, db_session, user_id, state, _SCENARIO):
        return
    if not await ensure_access(callback, db_session, user_id):
        return

    await callback.answer()
    await state.set_state(ProfileReviewStates.waiting_input)
    await callback.message.edit_text(
        "Опишите свой профиль текстом — или добавьте скриншот. "
        "Можно отправить и то, и другое."
    )


# ── Photo (compressed) ───────────────────────────────────────────────────────

@router.message(ProfileReviewStates.waiting_input, F.photo)
async def on_profile_photo(
    message: types.Message, state: FSMContext, db_session: AsyncSession,
) -> None:
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])

    if not await ensure_access(message, db_session, user_id):
        await state.set_state(None)
        return

    if not await ensure_image_limit(message, db_session, user_id):
        await state.set_state(None)
        return

    photo = message.photo[-1]
    caption_text = message.caption
    processing_msg = await message.answer("🔍 Анализирую ваш профиль...")

    try:
        settings = await user_repo.get_user_settings(db_session, user_id)
        async with download_telegram_photo(message.bot, photo.file_id) as photo_data:
            b64 = photo_bytes_to_base64(photo_data)

        result = await ai_service.generate(
            db_session,
            user_id=user_id,
            scenario=_SCENARIO,
            input_text=caption_text,
            image_base64=b64,
            image_file_id=photo.file_id,
            image_mime_type="image/jpeg",
            image_size=photo.file_size,
            **_settings_kwargs(settings),
        )

        # Decrement only on successful AI call
        await decrement_screenshot_balance(db_session, user_id, mode=_SCENARIO, file_type="photo")
        await _send_profile_result(processing_msg, result, state)

    except Exception:
        logger.exception("[%s] photo processing failed for user_id=%s", _SCENARIO, user_id)
        await state.update_data(
            retry_scenario=_SCENARIO,
            retry_photo_file_id=photo.file_id,
            retry_caption=caption_text,
        )
        await processing_msg.edit_text(
            "Что-то пошло не так. Попробуйте ещё раз.",
            reply_markup=error_with_retry_keyboard(),
        )
        await state.set_state(None)


# ── Document (image sent without compression) ────────────────────────────────

@router.message(ProfileReviewStates.waiting_input, F.document & F.document.mime_type.startswith("image/"))
async def on_profile_document(
    message: types.Message, state: FSMContext, db_session: AsyncSession,
) -> None:
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])

    if not await ensure_access(message, db_session, user_id):
        await state.set_state(None)
        return

    if not await ensure_image_limit(message, db_session, user_id):
        await state.set_state(None)
        return

    doc = message.document
    caption_text = message.caption
    processing_msg = await message.answer("🔍 Анализирую ваш профиль...")

    try:
        settings = await user_repo.get_user_settings(db_session, user_id)
        async with download_telegram_photo(message.bot, doc.file_id) as doc_data:
            b64 = photo_bytes_to_base64(doc_data)

        result = await ai_service.generate(
            db_session,
            user_id=user_id,
            scenario=_SCENARIO,
            input_text=caption_text,
            image_base64=b64,
            image_file_id=doc.file_id,
            image_mime_type=doc.mime_type or "image/jpeg",
            image_size=doc.file_size,
            **_settings_kwargs(settings),
        )

        # Decrement only on successful AI call
        await decrement_screenshot_balance(db_session, user_id, mode=_SCENARIO, file_type="document")
        await _send_profile_result(processing_msg, result, state)

    except Exception:
        logger.exception("[%s] document processing failed for user_id=%s", _SCENARIO, user_id)
        await state.update_data(
            retry_scenario=_SCENARIO,
            retry_photo_file_id=doc.file_id,
            retry_caption=caption_text,
        )
        await processing_msg.edit_text(
            "Что-то пошло не так. Попробуйте ещё раз.",
            reply_markup=error_with_retry_keyboard(),
        )
        await state.set_state(None)


# ── Text input ───────────────────────────────────────────────────────────────

@router.message(ProfileReviewStates.waiting_input, F.text)
async def on_profile_text(
    message: types.Message, state: FSMContext, db_session: AsyncSession,
) -> None:
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])

    if not await ensure_access(message, db_session, user_id):
        await state.set_state(None)
        return

    processing_msg = await message.answer("🔍 Анализирую ваш профиль...")

    try:
        settings = await user_repo.get_user_settings(db_session, user_id)
        result = await ai_service.generate(
            db_session,
            user_id=user_id,
            scenario=_SCENARIO,
            input_text=message.text,
            **_settings_kwargs(settings),
        )
        await _send_profile_result(processing_msg, result, state)
    except Exception:
        logger.exception("[%s] text processing failed for user_id=%s", _SCENARIO, user_id)
        await state.update_data(
            retry_scenario=_SCENARIO,
            retry_text=message.text,
            retry_photo_file_id=None,
            retry_caption=None,
        )
        await processing_msg.edit_text(
            "Что-то пошло не так. Попробуйте ещё раз.",
            reply_markup=error_with_retry_keyboard(),
        )
        await state.set_state(None)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _format_profile_review(result: dict) -> str:
    """Format structured profile review into readable text."""
    parts: list[str] = ["📋 Разбор вашего профиля:\n"]

    strengths = result.get("strengths", [])
    if strengths:
        parts.append("✅ Сильные стороны:")
        for s in strengths:
            parts.append(f"  + {s}")
        parts.append("")

    weaknesses = result.get("weaknesses", [])
    if weaknesses:
        parts.append("⚠️ Слабые места:")
        for w in weaknesses:
            parts.append(f"  − {w}")
        parts.append("")

    improvements = result.get("improvements", [])
    if improvements:
        parts.append("🔧 Что улучшить:")
        for imp in improvements:
            parts.append(f"  • {imp}")
        parts.append("")

    recommendations = result.get("recommendations", [])
    if recommendations:
        parts.append("💡 Рекомендации:")
        for r in recommendations:
            parts.append(f"  → {r}")

    return "\n".join(parts)


async def _send_profile_result(
    msg: types.Message, result: dict, state: FSMContext,
) -> None:
    request_id = result.get("request_id", "")

    if not any(result.get(k) for k in ("strengths", "weaknesses", "improvements", "recommendations")):
        await msg.edit_text(
            "Не удалось проанализировать профиль — попробуйте ещё раз.",
            reply_markup=error_with_retry_keyboard(),
        )
        await state.set_state(None)
        return

    text = _format_profile_review(result)
    await state.set_state(None)
    await state.update_data(last_request_id=request_id)
    await msg.edit_text(text, reply_markup=profile_result_keyboard(request_id))
