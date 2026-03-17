"""Handler for the 'Anti-ignor' scenario.

Flow: style → time without answer → last message → AI generation.
"""

from __future__ import annotations

import logging
import uuid

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.common import ensure_access, generate_and_send, get_image_usage_text
from app.bot.keyboards.scenarios import anti_ignor_time_keyboard, waiting_input_keyboard
from app.bot.keyboards.styles import get_style_label, style_keyboard
from app.bot.states.scenarios import AntiIgnorStates
from app.services.image_service import download_telegram_photo, photo_bytes_to_base64

router = Router(name="anti_ignor")
logger = logging.getLogger(__name__)

TIME_LABELS = {
    "1day": "1 день",
    "2-3days": "2-3 дня",
    "week": "неделя",
    "other": "другое",
}


@router.callback_query(F.data == "menu:anti_ignor")
async def start_anti_ignor(
    callback: types.CallbackQuery,
    state: FSMContext,
    db_session: AsyncSession,
) -> None:
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])

    if not await ensure_access(callback, db_session, user_id):
        return

    await callback.answer()

    # Always show style selection
    await callback.message.edit_text(
        "Выберите стиль сообщения:",
        reply_markup=style_keyboard("aistyle"),
    )
    await state.set_state(AntiIgnorStates.choosing_style)


@router.callback_query(AntiIgnorStates.choosing_style, F.data.startswith("aistyle:"))
async def on_style_chosen(
    callback: types.CallbackQuery, state: FSMContext,
) -> None:
    style = callback.data.split(":")[-1]
    await state.update_data(chosen_style=style)
    await callback.answer()
    await callback.message.edit_text(
        "Сколько времени нет ответа? ⏳",
        reply_markup=anti_ignor_time_keyboard(),
    )
    await state.set_state(AntiIgnorStates.choosing_time)


@router.callback_query(AntiIgnorStates.choosing_time, F.data.startswith("aitime:"))
async def on_time_chosen(
    callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession,
) -> None:
    time_key = callback.data.split(":")[-1]
    time_label = TIME_LABELS.get(time_key, time_key)
    await state.update_data(time_no_answer=time_label)
    await callback.answer()

    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])
    usage = await get_image_usage_text(db_session, user_id)

    await callback.message.edit_text(
        "Что было вашим последним сообщением?\n\n"
        f"Отправьте текст или скриншот переписки.\n\n📊 {usage}",
        reply_markup=waiting_input_keyboard("menu"),
    )
    await state.set_state(AntiIgnorStates.waiting_last_message)


@router.message(AntiIgnorStates.waiting_last_message, F.photo)
async def on_last_msg_photo(
    message: types.Message, state: FSMContext, db_session: AsyncSession,
) -> None:
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])

    if not await ensure_access(message, db_session, user_id):
        await state.set_state(None)
        return

    photo = message.photo[-1]
    caption_text = message.caption
    style = data.get("chosen_style")
    time_no_answer = data.get("time_no_answer", "")

    async with download_telegram_photo(message.bot, photo.file_id) as photo_data:
        b64 = photo_bytes_to_base64(photo_data)

    await generate_and_send(
        message, state, db_session,
        user_id=user_id,
        scenario="anti_ignor",
        style=style,
        input_text=caption_text,
        image_base64=b64,
        image_file_id=photo.file_id,
        image_mime_type="image/jpeg",
        image_size=photo.file_size,
        extra_context=f"Время без ответа: {time_no_answer}",
        processing_text="💬 Подбираю варианты...",
        result_header="🔄 Варианты для возобновления диалога:",
    )


@router.message(AntiIgnorStates.waiting_last_message, F.text)
async def on_last_msg_text(
    message: types.Message, state: FSMContext, db_session: AsyncSession,
) -> None:
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])

    if not await ensure_access(message, db_session, user_id):
        await state.set_state(None)
        return

    style = data.get("chosen_style")
    time_no_answer = data.get("time_no_answer", "")

    await generate_and_send(
        message, state, db_session,
        user_id=user_id,
        scenario="anti_ignor",
        style=style,
        input_text=message.text,
        extra_context=f"Время без ответа: {time_no_answer}",
        processing_text="💬 Подбираю варианты...",
        result_header="🔄 Варианты для возобновления диалога:",
    )
