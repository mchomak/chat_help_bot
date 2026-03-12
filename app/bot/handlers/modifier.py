"""Post-generation handlers: change style, more variants, retry, back navigation."""

from __future__ import annotations

import logging
import uuid

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.common import ensure_access, generate_and_send, send_menu
from app.bot.keyboards.scenarios import (
    back_to_menu_keyboard,
    error_with_retry_keyboard,
    post_generation_style_keyboard,
)
from app.db.repositories import user_repo
from app.services.image_service import download_telegram_photo, photo_bytes_to_base64

router = Router(name="modifier")
logger = logging.getLogger(__name__)

RESULT_HEADERS = {
    "first_message": "Варианты первого сообщения:",
    "analyzer": "Варианты ответа:",
    "anti_ignor": "Варианты для возобновления диалога:",
    "photo_pickup": "Варианты подкатов:",
}


# --- "Изменить стиль" button ---
@router.callback_query(F.data.startswith("postgen:chstyle:"))
async def on_change_style(callback: types.CallbackQuery, state: FSMContext) -> None:
    scenario = callback.data.split(":")[-1]
    await callback.answer()
    await callback.message.edit_text(
        "Выберите новый стиль:",
        reply_markup=post_generation_style_keyboard(scenario),
    )


# --- Style chosen for re-generation ---
@router.callback_query(F.data.startswith("restyle:"))
async def on_restyle(
    callback: types.CallbackQuery,
    state: FSMContext,
    db_session: AsyncSession,
) -> None:
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Неверный формат.")
        return

    _, scenario, new_style = parts
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])

    if not await ensure_access(callback, db_session, user_id):
        return

    # Retrieve saved context
    input_text = data.get("gen_input_text")
    image_file_id = data.get("gen_image_file_id")
    extra_context = data.get("gen_extra_context")

    if not input_text and not image_file_id:
        await callback.answer("Данные предыдущего запроса не найдены.")
        await callback.message.edit_text(
            "Контекст предыдущей генерации не найден. Начните заново через меню.",
            reply_markup=back_to_menu_keyboard(),
        )
        return

    await callback.answer("Генерирую...")

    # Re-download image if needed
    image_b64 = None
    if image_file_id:
        try:
            async with download_telegram_photo(callback.bot, image_file_id) as photo_data:
                image_b64 = photo_bytes_to_base64(photo_data)
        except Exception:
            logger.warning("Failed to re-download image %s", image_file_id)

    await generate_and_send(
        callback, state, db_session,
        user_id=user_id,
        scenario=scenario,
        style=new_style,
        input_text=input_text,
        image_base64=image_b64,
        image_file_id=image_file_id,
        image_mime_type="image/jpeg" if image_file_id else None,
        extra_context=extra_context,
        processing_text="Генерирую в новом стиле...",
        result_header=RESULT_HEADERS.get(scenario, "Варианты:"),
    )


# --- "Еще варианты" button ---
@router.callback_query(F.data.startswith("postgen:more:"))
async def on_more_variants(
    callback: types.CallbackQuery,
    state: FSMContext,
    db_session: AsyncSession,
) -> None:
    scenario = callback.data.split(":")[-1]
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])

    if not await ensure_access(callback, db_session, user_id):
        return

    input_text = data.get("gen_input_text")
    image_file_id = data.get("gen_image_file_id")
    style = data.get("gen_style")
    extra_context = data.get("gen_extra_context")

    if not input_text and not image_file_id:
        await callback.answer("Данные предыдущего запроса не найдены.")
        await callback.message.edit_text(
            "Контекст предыдущей генерации не найден. Начните заново через меню.",
            reply_markup=back_to_menu_keyboard(),
        )
        return

    await callback.answer("Генерирую...")

    image_b64 = None
    if image_file_id:
        try:
            async with download_telegram_photo(callback.bot, image_file_id) as photo_data:
                image_b64 = photo_bytes_to_base64(photo_data)
        except Exception:
            logger.warning("Failed to re-download image %s", image_file_id)

    await generate_and_send(
        callback, state, db_session,
        user_id=user_id,
        scenario=scenario,
        style=style,
        input_text=input_text,
        image_base64=image_b64,
        image_file_id=image_file_id,
        image_mime_type="image/jpeg" if image_file_id else None,
        extra_context=extra_context,
        processing_text="Генерирую новые варианты...",
        result_header=RESULT_HEADERS.get(scenario, "Варианты:"),
    )


# --- "Назад" buttons for scenarios ---
@router.callback_query(F.data.startswith("back:"))
async def on_back(callback: types.CallbackQuery, state: FSMContext) -> None:
    target = callback.data.split(":", 1)[-1]
    await callback.answer()
    await state.set_state(None)
    # All "back" targets go to main menu for simplicity
    await send_menu(callback)


# --- Retry last action ---
@router.callback_query(F.data == "retry:last")
async def on_retry(
    callback: types.CallbackQuery,
    state: FSMContext,
    db_session: AsyncSession,
) -> None:
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])

    scenario = data.get("retry_scenario") or data.get("gen_scenario")
    if not scenario:
        await callback.answer("Нет данных для повтора.")
        await callback.message.edit_text(
            "Данные предыдущего запроса не найдены.",
            reply_markup=back_to_menu_keyboard(),
        )
        return

    if not await ensure_access(callback, db_session, user_id):
        return

    input_text = data.get("retry_text") or data.get("gen_input_text")
    image_file_id = data.get("retry_photo_file_id") or data.get("gen_image_file_id")
    style = data.get("retry_style") or data.get("gen_style")
    extra_context = data.get("retry_extra_context") or data.get("gen_extra_context")

    await callback.answer("Повторяю запрос...")

    image_b64 = None
    if image_file_id:
        try:
            async with download_telegram_photo(callback.bot, image_file_id) as photo_data:
                image_b64 = photo_bytes_to_base64(photo_data)
        except Exception:
            logger.warning("Failed to re-download image %s", image_file_id)

    await generate_and_send(
        callback, state, db_session,
        user_id=user_id,
        scenario=scenario,
        style=style,
        input_text=input_text,
        image_base64=image_b64,
        image_file_id=image_file_id,
        image_mime_type="image/jpeg" if image_file_id else None,
        extra_context=extra_context,
        processing_text="Повторяю запрос...",
        result_header=RESULT_HEADERS.get(scenario, "Варианты:"),
    )
