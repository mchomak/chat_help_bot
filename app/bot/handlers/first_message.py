"""Handler for the "First message" scenario."""

from __future__ import annotations

import logging
import uuid

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.common import ensure_access, ensure_consent
from app.bot.keyboards.scenarios import error_with_retry_keyboard, first_msg_result_keyboard
from app.bot.states.scenarios import FirstMessageStates
from app.db.repositories import user_repo
from app.services import ai_service
from app.services.image_service import download_telegram_photo, photo_bytes_to_base64

router = Router(name="first_message")
logger = logging.getLogger(__name__)


def _settings_kwargs(settings) -> dict:
    if settings is None:
        return {}
    return {
        "gender": settings.gender,
        "communication_style": settings.communication_style,
        "ai_identity_text": settings.ai_identity_text,
    }


@router.callback_query(F.data == "menu:first_message")
async def start_first_msg_scenario(
    callback: types.CallbackQuery,
    state: FSMContext,
    db_session: AsyncSession,
) -> None:
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])

    if not await ensure_consent(callback, db_session, user_id, state, "first_message"):
        return
    if not await ensure_access(callback, db_session, user_id):
        return

    await callback.answer()
    await state.set_state(FirstMessageStates.waiting_input)
    await callback.message.edit_text(
        "Отправьте скриншот профиля, описание профиля или оба варианта."
    )


@router.message(FirstMessageStates.waiting_input, F.photo)
async def on_first_msg_photo(
    message: types.Message, state: FSMContext, db_session: AsyncSession,
) -> None:
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])

    if not await ensure_access(message, db_session, user_id):
        await state.set_state(None)
        return

    photo = message.photo[-1]
    caption_text = message.caption
    processing_msg = await message.answer("Анализирую профиль...")

    try:
        settings = await user_repo.get_user_settings(db_session, user_id)
        async with download_telegram_photo(message.bot, photo.file_id) as data:
            b64 = photo_bytes_to_base64(data)

        result = await ai_service.generate(
            db_session,
            user_id=user_id,
            scenario="first_message",
            input_text=caption_text,
            image_base64=b64,
            image_file_id=photo.file_id,
            image_mime_type="image/jpeg",
            image_size=photo.file_size,
            **_settings_kwargs(settings),
        )
        await _send_first_msg_result(processing_msg, result, state)
    except Exception:
        logger.exception("first_message photo failed")
        await state.update_data(
            retry_scenario="first_message",
            retry_photo_file_id=photo.file_id,
            retry_caption=caption_text,
        )
        await processing_msg.edit_text(
            "Произошла ошибка при обработке.",
            reply_markup=error_with_retry_keyboard(),
        )
        await state.set_state(None)


@router.message(FirstMessageStates.waiting_input, F.text)
async def on_first_msg_text(
    message: types.Message, state: FSMContext, db_session: AsyncSession,
) -> None:
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])

    if not await ensure_access(message, db_session, user_id):
        await state.set_state(None)
        return

    processing_msg = await message.answer("Анализирую профиль...")

    try:
        settings = await user_repo.get_user_settings(db_session, user_id)
        result = await ai_service.generate(
            db_session,
            user_id=user_id,
            scenario="first_message",
            input_text=message.text,
            **_settings_kwargs(settings),
        )
        await _send_first_msg_result(processing_msg, result, state)
    except Exception:
        logger.exception("first_message text failed")
        await state.update_data(
            retry_scenario="first_message",
            retry_text=message.text,
            retry_photo_file_id=None,
            retry_caption=None,
        )
        await processing_msg.edit_text(
            "Произошла ошибка при обработке.",
            reply_markup=error_with_retry_keyboard(),
        )
        await state.set_state(None)


async def _send_first_msg_result(
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

    text_parts = ["Варианты первого сообщения:\n"]
    for i, item in enumerate(items, 1):
        text_parts.append(f"{i}. {item}\n")

    await state.set_state(None)
    await state.update_data(last_request_id=request_id)
    await msg.edit_text(
        "\n".join(text_parts),
        reply_markup=first_msg_result_keyboard(request_id),
    )
