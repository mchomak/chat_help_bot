"""Handler for the 'Photo pickup lines' scenario.

Flow: style → photo upload → AI generation.
"""

from __future__ import annotations

import logging
import uuid

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.common import ensure_access, generate_and_send
from app.bot.keyboards.styles import get_style_label, style_keyboard
from app.bot.states.scenarios import PhotoPickupStates
from app.db.repositories import user_repo
from app.services.image_service import download_telegram_photo, photo_bytes_to_base64

router = Router(name="photo_pickup")
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "menu:photo_pickup")
async def start_photo_pickup(
    callback: types.CallbackQuery,
    state: FSMContext,
    db_session: AsyncSession,
) -> None:
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])

    if not await ensure_access(callback, db_session, user_id):
        return

    await callback.answer()

    settings = await user_repo.get_user_settings(db_session, user_id)
    if settings and settings.default_style:
        await state.update_data(chosen_style=settings.default_style)
        await callback.message.edit_text(
            f"Стиль: {get_style_label(settings.default_style)}\n\n"
            "Отправьте фото."
        )
        await state.set_state(PhotoPickupStates.waiting_photo)
    else:
        await callback.message.edit_text(
            "Выберите стиль ответа:",
            reply_markup=style_keyboard("ppstyle"),
        )
        await state.set_state(PhotoPickupStates.choosing_style)


@router.callback_query(PhotoPickupStates.choosing_style, F.data.startswith("ppstyle:"))
async def on_style_chosen(
    callback: types.CallbackQuery, state: FSMContext,
) -> None:
    style = callback.data.split(":")[-1]
    await state.update_data(chosen_style=style)
    await callback.answer()
    await callback.message.edit_text("Отправьте фото.")
    await state.set_state(PhotoPickupStates.waiting_photo)


@router.message(PhotoPickupStates.waiting_photo, F.photo)
async def on_photo(
    message: types.Message, state: FSMContext, db_session: AsyncSession,
) -> None:
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])

    if not await ensure_access(message, db_session, user_id):
        await state.set_state(None)
        return

    photo = message.photo[-1]
    style = data.get("chosen_style")

    async with download_telegram_photo(message.bot, photo.file_id) as photo_data:
        b64 = photo_bytes_to_base64(photo_data)

    await generate_and_send(
        message, state, db_session,
        user_id=user_id,
        scenario="photo_pickup",
        style=style,
        input_text=message.caption,
        image_base64=b64,
        image_file_id=photo.file_id,
        image_mime_type="image/jpeg",
        image_size=photo.file_size,
        processing_text="Анализирую фото...",
        result_header="Варианты подкатов:",
    )


@router.message(PhotoPickupStates.waiting_photo)
async def on_not_photo(message: types.Message) -> None:
    await message.answer("Пожалуйста, отправьте фото.")
