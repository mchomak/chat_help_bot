"""Post-generation handlers: change style, more variants, retry, back navigation."""

from __future__ import annotations

import logging
import uuid

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.common import ensure_access, generate_and_send, get_image_usage_text, send_menu
from app.bot.keyboards.scenarios import (
    back_to_menu_keyboard,
    error_with_retry_keyboard,
    post_generation_keyboard,
    post_generation_style_keyboard,
    waiting_input_keyboard,
)
from app.db.repositories import user_repo
from app.services.image_service import download_telegram_photo, photo_bytes_to_base64

router = Router(name="modifier")
logger = logging.getLogger(__name__)

RESULT_HEADERS = {
    "first_message": "✉️ Варианты первого сообщения:",
    "analyzer": "💬 Варианты ответа:",
    "anti_ignor": "🔄 Варианты для возобновления диалога:",
    "photo_pickup": "📸 Варианты подкатов:",
    "flirt": "💬 Варианты флирта:",
}


# --- "Изменить стиль" button ---
@router.callback_query(F.data.startswith("postgen:chstyle:"))
async def on_change_style(callback: types.CallbackQuery, state: FSMContext) -> None:
    scenario = callback.data.split(":")[-1]
    await callback.answer()
    await callback.message.edit_text(
        "Выберите другой стиль — и я перегенерирую:",
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
            "Контекст предыдущего запроса не сохранился. Начните заново через меню.",
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
        processing_text="🎨 Генерирую в новом стиле...",
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
            "Контекст предыдущего запроса не сохранился. Начните заново через меню.",
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
        processing_text="✨ Генерирую ещё варианты...",
        result_header=RESULT_HEADERS.get(scenario, "Варианты:"),
    )


# Mapping of scenario targets to their waiting-input prompts and states
_SCENARIO_INPUT_PROMPTS = {
    "first_message": "Отправьте скриншот профиля или опишите человека текстом.",
    "analyzer": "Отправьте скриншот переписки или вставьте текст диалога.",
    "anti_ignor": "Отправьте текст или скриншот последнего сообщения.",
    "photo_pickup": "Отправьте фото человека, которому хотите написать.",
    "flirt": "Отправьте скриншот переписки, фото или опишите ситуацию текстом.",
    "reply_message": (
        "Отправьте скриншот переписки или текст в формате:\n"
        "Я: ...\nОна: ...\nЯ: ...\nОна: ..."
    ),
    "profile_review": "Опишите свой профиль текстом — или добавьте скриншот.",
}

# Scenario -> menu callback for restart
_SCENARIO_MENU_CALLBACKS = {
    "first_message": "menu:first_message",
    "analyzer": "menu:analyzer",
    "anti_ignor": "menu:anti_ignor",
    "photo_pickup": "menu:photo_pickup",
    "flirt": "menu:flirt",
}


# --- "Назад к результатам" from style picker ---
@router.callback_query(F.data.startswith("backto:results:"))
async def on_back_to_results(
    callback: types.CallbackQuery, state: FSMContext,
) -> None:
    """Return from style picker back to the generated results."""
    scenario = callback.data.split(":")[-1]
    await callback.answer()

    data = await state.get_data()
    gen_text = data.get("gen_result_text")

    if gen_text:
        await callback.message.edit_text(
            gen_text,
            reply_markup=post_generation_keyboard(scenario),
        )
    else:
        # Fallback: can't restore results, go to menu
        await send_menu(callback)


# --- "Restart scenario" button ---
@router.callback_query(F.data.startswith("restart:"))
async def on_restart_scenario(
    callback: types.CallbackQuery, state: FSMContext,
) -> None:
    """Restart the current scenario from scratch."""
    scenario = callback.data.split(":", 1)[-1]
    await callback.answer()
    await state.set_state(None)

    from app.bot.keyboards.styles import style_keyboard as build_style_kb
    from app.bot.states.scenarios import (
        AnalyzerStates,
        AntiIgnorStates,
        FirstMessageStates,
        FlirtStates,
        PhotoPickupStates,
    )

    _STYLE_PREFIX = {
        "first_message": ("fmstyle", FirstMessageStates.choosing_style),
        "analyzer": ("azstyle", AnalyzerStates.choosing_style),
        "anti_ignor": ("aistyle", AntiIgnorStates.choosing_style),
        "photo_pickup": ("ppstyle", PhotoPickupStates.choosing_style),
    }

    if scenario == "flirt":
        await state.set_state(FlirtStates.waiting_input)
        await callback.message.edit_text(
            _SCENARIO_INPUT_PROMPTS["flirt"],
            reply_markup=waiting_input_keyboard("menu"),
        )
    elif scenario in _STYLE_PREFIX:
        prefix, fst_state = _STYLE_PREFIX[scenario]
        await state.set_state(fst_state)
        await callback.message.edit_text(
            "Выберите стиль ответа:",
            reply_markup=build_style_kb(prefix),
        )
    else:
        await send_menu(callback)


# --- "Назад" buttons for scenarios ---
@router.callback_query(F.data.startswith("back:"))
async def on_back(callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession) -> None:
    target = callback.data.split(":", 1)[-1]
    await callback.answer()
    await state.set_state(None)

    # If target is a known scenario, go back to that scenario's input prompt
    if target in _SCENARIO_INPUT_PROMPTS:
        from app.bot.states.scenarios import (
            AnalyzerStates,
            AntiIgnorStates,
            FirstMessageStates,
            FlirtStates,
            PhotoPickupStates,
            ProfileReviewStates,
            ReplyMessageStates,
        )

        prompt = _SCENARIO_INPUT_PROMPTS[target]

        # Set the appropriate waiting state
        state_map = {
            "first_message": FirstMessageStates.waiting_input,
            "analyzer": AnalyzerStates.waiting_input,
            "anti_ignor": AntiIgnorStates.waiting_last_message,
            "photo_pickup": PhotoPickupStates.waiting_photo,
            "flirt": FlirtStates.waiting_input,
            "reply_message": ReplyMessageStates.waiting_input,
            "profile_review": ProfileReviewStates.waiting_input,
        }
        waiting_state = state_map.get(target)
        if waiting_state:
            await state.set_state(waiting_state)

        # Add image usage info to the prompt
        data = await state.get_data()
        user_id_str = data.get("user_id")
        if user_id_str:
            user_id = uuid.UUID(user_id_str)
            usage_text = await get_image_usage_text(db_session, user_id)
            prompt = f"{prompt}\n\n📊 {usage_text}"

        await callback.message.edit_text(
            prompt,
            reply_markup=waiting_input_keyboard("menu"),
        )
        return

    # Default: go to main menu
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
            "Не удалось найти данные предыдущего запроса. Начните заново через меню.",
            reply_markup=back_to_menu_keyboard(),
        )
        return

    if not await ensure_access(callback, db_session, user_id):
        return

    input_text = data.get("retry_text") or data.get("gen_input_text")
    image_file_id = data.get("retry_photo_file_id") or data.get("gen_image_file_id")
    style = data.get("retry_style") or data.get("gen_style")
    extra_context = data.get("retry_extra_context") or data.get("gen_extra_context")

    await callback.answer("Повторяю...")

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
        processing_text="🔄 Повторяю запрос...",
        result_header=RESULT_HEADERS.get(scenario, "Варианты:"),
    )
