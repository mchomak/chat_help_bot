"""Settings view and edit handlers."""

from __future__ import annotations

import uuid

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.common import send_menu
from app.bot.keyboards.onboarding import gender_keyboard, skip_keyboard
from app.bot.keyboards.scenarios import back_to_menu_keyboard
from app.bot.keyboards.settings import settings_menu_keyboard
from app.bot.states.settings import SettingsEditStates
from app.db.repositories import user_repo
from app.services.access_service import check_access

router = Router(name="settings")

GENDER_LABELS = {"male": "Мужчина", "female": "Женщина"}
ACCESS_LABELS = {
    "none": "Нет доступа",
    "trial": "Пробный период",
    "expired": "Пробный период закончился",
    "paid": "Оплачен",
}

IDENTITY_EDIT_PROMPT = (
    "Расскажите коротко о себе (до 300 символов).\n\n"
    "Например: «Мне 28 лет, работаю дизайнером, люблю путешествия "
    "и чёрный юмор. Общаюсь легко, но иногда стесняюсь писать первым».\n\n"
    "Бот будет учитывать это при генерации, чтобы ответы "
    "звучали естественно и подходили именно вам.\n\n"
    "Нажмите «Пропустить» для сброса."
)


def _format_settings(s) -> str:
    lines = [
        "Текущие настройки:\n",
        f"Пол: {GENDER_LABELS.get(s.gender, s.gender or 'не указан')}",
        f"Стиль общения: {s.communication_style or 'не указан'}",
        f"О себе: {s.ai_identity_text or 'не указано'}",
    ]
    return "\n".join(lines)


@router.message(Command("settings"))
async def cmd_settings(message: types.Message, state: FSMContext, db_session: AsyncSession) -> None:
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])
    s = await user_repo.get_user_settings(db_session, user_id)
    if s is None:
        await message.answer("Настройки не найдены. Начните с /start.")
        return
    await message.answer(_format_settings(s), reply_markup=settings_menu_keyboard())


@router.callback_query(F.data == "menu:settings")
async def cb_settings(callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession) -> None:
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])
    s = await user_repo.get_user_settings(db_session, user_id)
    if s is None:
        await callback.answer("Настройки не найдены.")
        return
    await callback.answer()
    await callback.message.edit_text(_format_settings(s), reply_markup=settings_menu_keyboard())


# --- Edit gender ---
@router.callback_query(F.data == "set:edit:gender")
async def edit_gender(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(SettingsEditStates.editing_gender)
    await callback.message.edit_text("Выберите пол:", reply_markup=gender_keyboard())


@router.callback_query(SettingsEditStates.editing_gender, F.data.startswith("onb:gender:"))
async def save_gender(callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession) -> None:
    value = callback.data.split(":")[-1]
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])
    v = None if value == "skip" else value
    await user_repo.update_settings(db_session, user_id, gender=v)
    await db_session.commit()
    await callback.answer("Сохранено!")
    await state.set_state(None)
    s = await user_repo.get_user_settings(db_session, user_id)
    await callback.message.edit_text(_format_settings(s), reply_markup=settings_menu_keyboard())


# --- Edit style ---
@router.callback_query(F.data == "set:edit:style")
async def edit_style(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(SettingsEditStates.editing_style)
    await callback.message.edit_text(
        "Введите описание стиля общения (или /cancel для отмены):",
        reply_markup=skip_keyboard(),
    )


@router.callback_query(SettingsEditStates.editing_style, F.data == "onb:skip")
async def skip_style(callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession) -> None:
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])
    await user_repo.update_settings(db_session, user_id, communication_style=None)
    await db_session.commit()
    await callback.answer("Сброшено!")
    await state.set_state(None)
    s = await user_repo.get_user_settings(db_session, user_id)
    await callback.message.edit_text(_format_settings(s), reply_markup=settings_menu_keyboard())


@router.message(SettingsEditStates.editing_style)
async def save_style_text(message: types.Message, state: FSMContext, db_session: AsyncSession) -> None:
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])
    await user_repo.update_settings(db_session, user_id, communication_style=message.text[:500])
    await db_session.commit()
    await state.set_state(None)
    s = await user_repo.get_user_settings(db_session, user_id)
    await message.answer(_format_settings(s), reply_markup=settings_menu_keyboard())


# --- Edit identity ---
@router.callback_query(F.data == "set:edit:identity")
async def edit_identity(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(SettingsEditStates.editing_identity)
    await callback.message.edit_text(IDENTITY_EDIT_PROMPT, reply_markup=skip_keyboard())


@router.callback_query(SettingsEditStates.editing_identity, F.data == "onb:skip")
async def skip_identity(callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession) -> None:
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])
    await user_repo.update_settings(db_session, user_id, ai_identity_text=None)
    await db_session.commit()
    await callback.answer("Сброшено!")
    await state.set_state(None)
    s = await user_repo.get_user_settings(db_session, user_id)
    await callback.message.edit_text(_format_settings(s), reply_markup=settings_menu_keyboard())


@router.message(SettingsEditStates.editing_identity)
async def save_identity_text(message: types.Message, state: FSMContext, db_session: AsyncSession) -> None:
    text = message.text or ""
    if len(text) > 300:
        await message.answer("Текст слишком длинный (макс. 300 символов). Пожалуйста, сократите.")
        return
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])
    await user_repo.update_settings(db_session, user_id, ai_identity_text=text)
    await db_session.commit()
    await state.set_state(None)
    s = await user_repo.get_user_settings(db_session, user_id)
    await message.answer(_format_settings(s), reply_markup=settings_menu_keyboard())


# --- Reset all ---
@router.callback_query(F.data == "set:reset_all")
async def reset_all(callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession) -> None:
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])
    await user_repo.update_settings(
        db_session, user_id,
        gender=None,
        communication_style=None,
        ai_identity_text=None,
    )
    await db_session.commit()
    await callback.answer("Все настройки сброшены!")
    s = await user_repo.get_user_settings(db_session, user_id)
    await callback.message.edit_text(_format_settings(s), reply_markup=settings_menu_keyboard())


# --- Access status ---
@router.callback_query(F.data == "set:access_status")
async def show_access_status(callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession) -> None:
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])
    status = await check_access(db_session, user_id)
    label = ACCESS_LABELS.get(status, status)
    await callback.answer(f"Статус доступа: {label}", show_alert=True)
