"""Handler for the 'Flirt' scenario.

Flow: input data (screenshot/photo/text) → AI generation with fixed 'flirt' style.
No style selection — flirt style is always used.
"""

from __future__ import annotations

import logging
import uuid

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.common import ensure_access, generate_and_send, get_image_usage_text
from app.bot.keyboards.scenarios import waiting_input_keyboard
from app.bot.states.scenarios import FlirtStates
from app.services.image_service import download_telegram_photo, photo_bytes_to_base64

router = Router(name="flirt")
logger = logging.getLogger(__name__)

INPUT_PROMPT = "Отправьте скриншот переписки, фото или описание текстом."
FIXED_STYLE = "flirt"


@router.callback_query(F.data == "menu:flirt")
async def start_flirt(
    callback: types.CallbackQuery,
    state: FSMContext,
    db_session: AsyncSession,
) -> None:
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])

    if not await ensure_access(callback, db_session, user_id):
        return

    await callback.answer()
    await state.update_data(chosen_style=FIXED_STYLE)

    usage = await get_image_usage_text(db_session, user_id)
    await callback.message.edit_text(
        f"{INPUT_PROMPT}\n\n📊 {usage}",
        reply_markup=waiting_input_keyboard("menu"),
    )
    await state.set_state(FlirtStates.waiting_input)


@router.message(FlirtStates.waiting_input, F.photo)
async def on_flirt_photo(
    message: types.Message, state: FSMContext, db_session: AsyncSession,
) -> None:
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])

    if not await ensure_access(message, db_session, user_id):
        await state.set_state(None)
        return

    photo = message.photo[-1]
    caption_text = message.caption

    async with download_telegram_photo(message.bot, photo.file_id) as photo_data:
        b64 = photo_bytes_to_base64(photo_data)

    await generate_and_send(
        message, state, db_session,
        user_id=user_id,
        scenario="flirt",
        style=FIXED_STYLE,
        input_text=caption_text,
        image_base64=b64,
        image_file_id=photo.file_id,
        image_mime_type="image/jpeg",
        image_size=photo.file_size,
        processing_text="Генерирую варианты...",
        result_header="Варианты флирта:",
    )


@router.message(FlirtStates.waiting_input, F.text)
async def on_flirt_text(
    message: types.Message, state: FSMContext, db_session: AsyncSession,
) -> None:
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])

    if not await ensure_access(message, db_session, user_id):
        await state.set_state(None)
        return

    await generate_and_send(
        message, state, db_session,
        user_id=user_id,
        scenario="flirt",
        style=FIXED_STYLE,
        input_text=message.text,
        processing_text="Генерирую варианты...",
        result_header="Варианты флирта:",
    )
