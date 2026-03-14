"""Handler for the 'Dialog analyzer' scenario.

Flow: style selection → input data (auto-detect photo/text) → AI analysis + suggestions.
"""

from __future__ import annotations

import logging
import uuid

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.common import ensure_access, generate_and_send, get_image_usage_text
from app.bot.keyboards.scenarios import nav_keyboard, suggest_first_message_keyboard
from app.bot.keyboards.styles import get_style_label, style_keyboard
from app.bot.states.scenarios import AnalyzerStates
from app.services.image_service import download_telegram_photo, photo_bytes_to_base64

router = Router(name="analyzer")
logger = logging.getLogger(__name__)

INPUT_PROMPT = "Отправьте скриншот переписки или переписку текстом."


@router.callback_query(F.data == "menu:analyzer")
async def start_analyzer(
    callback: types.CallbackQuery,
    state: FSMContext,
    db_session: AsyncSession,
) -> None:
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])

    if not await ensure_access(callback, db_session, user_id):
        return

    await callback.answer()

    # Always show style selection for analyzer
    await callback.message.edit_text(
        "Выберите стиль ответа:",
        reply_markup=style_keyboard("azstyle"),
    )
    await state.set_state(AnalyzerStates.choosing_style)


@router.callback_query(AnalyzerStates.choosing_style, F.data.startswith("azstyle:"))
async def on_style_chosen(
    callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession,
) -> None:
    style = callback.data.split(":")[-1]
    await state.update_data(chosen_style=style)
    await callback.answer()

    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])
    usage = await get_image_usage_text(db_session, user_id)

    await callback.message.edit_text(
        f"Стиль: {get_style_label(style)}\n\n{INPUT_PROMPT}\n\n📊 {usage}",
        reply_markup=nav_keyboard("menu"),
    )
    await state.set_state(AnalyzerStates.waiting_input)


@router.message(AnalyzerStates.waiting_input, F.photo)
async def on_analyzer_photo(
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

    async with download_telegram_photo(message.bot, photo.file_id) as photo_data:
        b64 = photo_bytes_to_base64(photo_data)

    await generate_and_send(
        message, state, db_session,
        user_id=user_id,
        scenario="analyzer",
        style=style,
        input_text=caption_text,
        image_base64=b64,
        image_file_id=photo.file_id,
        image_mime_type="image/jpeg",
        image_size=photo.file_size,
        processing_text="Анализирую переписку...",
        result_header="Варианты ответа:",
    )


@router.message(AnalyzerStates.waiting_input, F.text)
async def on_analyzer_text(
    message: types.Message, state: FSMContext, db_session: AsyncSession,
) -> None:
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])

    if not await ensure_access(message, db_session, user_id):
        await state.set_state(None)
        return

    style = data.get("chosen_style")
    text = message.text or ""

    # Check if conversation is too short (fewer than 2 exchanges)
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if len(lines) < 2:
        await message.answer(
            "Переписка слишком короткая для анализа.\n"
            "Попробуйте «Генератор первых сообщений».",
            reply_markup=suggest_first_message_keyboard(),
        )
        await state.set_state(None)
        return

    await generate_and_send(
        message, state, db_session,
        user_id=user_id,
        scenario="analyzer",
        style=style,
        input_text=text,
        processing_text="Анализирую переписку...",
        result_header="Варианты ответа:",
    )
