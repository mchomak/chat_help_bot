"""Handler for the "Reply to message" scenario."""

from __future__ import annotations

import logging
import uuid

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.common import ensure_access, ensure_consent
from app.bot.keyboards.scenarios import error_with_retry_keyboard, reply_result_keyboard
from app.bot.states.scenarios import ReplyMessageStates
from app.db.repositories import user_repo
from app.services import ai_service
from app.services.image_service import download_telegram_photo, photo_bytes_to_base64

router = Router(name="reply_message")
logger = logging.getLogger(__name__)


def _settings_kwargs(settings) -> dict:
    """Extract AI-relevant fields from UserSettings."""
    if settings is None:
        return {}
    return {
        "gender": settings.gender,
        "communication_style": settings.communication_style,
        "ai_identity_text": settings.ai_identity_text,
    }


@router.callback_query(F.data == "menu:reply_message")
async def start_reply_scenario(
    callback: types.CallbackQuery,
    state: FSMContext,
    db_session: AsyncSession,
) -> None:
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])

    if not await ensure_consent(callback, db_session, user_id, state, "reply_message"):
        return
    if not await ensure_access(callback, db_session, user_id):
        return

    await callback.answer()
    await state.set_state(ReplyMessageStates.waiting_input)
    await callback.message.edit_text(
        "Отправьте скриншот переписки или текст в формате:\n"
        "Я: ...\nОна: ...\nЯ: ...\nОна: ..."
    )


@router.message(ReplyMessageStates.waiting_input, F.photo)
async def on_reply_photo(
    message: types.Message, state: FSMContext, db_session: AsyncSession,
) -> None:
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])

    if not await ensure_access(message, db_session, user_id):
        await state.set_state(None)
        return

    photo = message.photo[-1]  # best quality
    caption_text = message.caption

    processing_msg = await message.answer("Анализирую переписку...")

    try:
        settings = await user_repo.get_user_settings(db_session, user_id)
        async with download_telegram_photo(message.bot, photo.file_id) as data:
            b64 = photo_bytes_to_base64(data)

        result = await ai_service.generate(
            db_session,
            user_id=user_id,
            scenario="reply_message",
            input_text=caption_text,
            image_base64=b64,
            image_file_id=photo.file_id,
            image_mime_type="image/jpeg",
            image_size=photo.file_size,
            **_settings_kwargs(settings),
        )

        await _send_reply_result(processing_msg, result, state)
    except Exception:
        logger.exception("reply_message photo failed")
        # Save retry context: scenario + file_id so we can re-download
        await state.update_data(
            retry_scenario="reply_message",
            retry_photo_file_id=photo.file_id,
            retry_caption=caption_text,
        )
        await processing_msg.edit_text(
            "Произошла ошибка при обработке.",
            reply_markup=error_with_retry_keyboard(),
        )
        await state.set_state(None)


@router.message(ReplyMessageStates.waiting_input, F.text)
async def on_reply_text(
    message: types.Message, state: FSMContext, db_session: AsyncSession,
) -> None:
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])

    if not await ensure_access(message, db_session, user_id):
        await state.set_state(None)
        return

    processing_msg = await message.answer("Анализирую переписку...")

    try:
        settings = await user_repo.get_user_settings(db_session, user_id)
        result = await ai_service.generate(
            db_session,
            user_id=user_id,
            scenario="reply_message",
            input_text=message.text,
            **_settings_kwargs(settings),
        )

        await _send_reply_result(processing_msg, result, state)
    except Exception:
        logger.exception("reply_message text failed")
        await state.update_data(
            retry_scenario="reply_message",
            retry_text=message.text,
            retry_photo_file_id=None,
            retry_caption=None,
        )
        await processing_msg.edit_text(
            "Произошла ошибка при обработке.",
            reply_markup=error_with_retry_keyboard(),
        )
        await state.set_state(None)


async def _send_reply_result(
    msg: types.Message, result: dict, state: FSMContext,
) -> None:
    items = result.get("items", [])
    request_id = result.get("request_id", "")
    if not items:
        await msg.edit_text(
            "Не удалось сгенерировать варианты.",
            reply_markup=error_with_retry_keyboard(),
        )
        await state.set_state(None)
        return

    text_parts = ["Варианты ответа:\n"]
    for i, item in enumerate(items, 1):
        text_parts.append(f"{i}. {item}\n")

    await state.set_state(None)
    await state.update_data(last_request_id=request_id)
    await msg.edit_text(
        "\n".join(text_parts),
        reply_markup=reply_result_keyboard(request_id),
    )
