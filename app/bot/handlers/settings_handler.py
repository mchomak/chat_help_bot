"""Settings view and edit handlers."""

from __future__ import annotations

import uuid

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.common import send_menu
from app.bot.keyboards.onboarding import (
    gender_keyboard,
    role_keyboard,
    situation_keyboard,
    skip_keyboard,
)
from app.bot.keyboards.scenarios import back_to_menu_keyboard
from app.bot.keyboards.settings import settings_menu_keyboard
from app.bot.states.settings import SettingsEditStates
from app.db.repositories import user_repo
from app.services.access_service import check_access

router = Router(name="settings")

GENDER_LABELS = {"male": "Мужчина", "female": "Женщина"}
SITUATION_LABELS = {
    "dating_site": "Сайт знакомств",
    "real_life": "Реальное общение",
    "after_meeting": "Переписка после знакомства",
    "other": "Другое",
}
ROLE_LABELS = {
    "initiator": "Инициатор общения",
    "continuing": "Продолжаю диалог",
    "meeting": "Хочу перейти к встрече",
    "other": "Другое",
}
ACCESS_LABELS = {
    "none": "Нет доступа",
    "trial": "Пробный период",
    "expired": "Пробный период закончился",
    "paid": "Оплачен",
}


def _format_settings(s) -> str:
    lines = [
        "Текущие настройки:\n",
        f"Пол: {GENDER_LABELS.get(s.gender, s.gender or 'не указан')}",
        f"Тип ситуации: {SITUATION_LABELS.get(s.situation_type, s.situation_type or 'не указан')}",
        f"Роль: {ROLE_LABELS.get(s.communication_role, s.communication_role or 'не указана')}",
        f"Стиль общения: {s.communication_style or 'не указан'}",
        f"Кто я для ИИ: {s.ai_identity_text or 'не указано'}",
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


# --- Edit situation ---
@router.callback_query(F.data == "set:edit:situation")
async def edit_situation(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(SettingsEditStates.editing_situation)
    await callback.message.edit_text("Выберите тип ситуации:", reply_markup=situation_keyboard())


@router.callback_query(SettingsEditStates.editing_situation, F.data.startswith("onb:sit:"))
async def save_situation(callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession) -> None:
    value = callback.data.split(":")[-1]
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])
    v = None if value == "skip" else value
    await user_repo.update_settings(db_session, user_id, situation_type=v)
    await db_session.commit()
    await callback.answer("Сохранено!")
    await state.set_state(None)
    s = await user_repo.get_user_settings(db_session, user_id)
    await callback.message.edit_text(_format_settings(s), reply_markup=settings_menu_keyboard())


# --- Edit role ---
@router.callback_query(F.data == "set:edit:role")
async def edit_role(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(SettingsEditStates.editing_role)
    await callback.message.edit_text("Выберите вашу роль:", reply_markup=role_keyboard())


@router.callback_query(SettingsEditStates.editing_role, F.data.startswith("onb:role:"))
async def save_role(callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession) -> None:
    value = callback.data.split(":")[-1]
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])
    v = None if value == "skip" else value
    await user_repo.update_settings(db_session, user_id, communication_role=v)
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
    await callback.message.edit_text(
        "Введите «Кто я для ИИ» (до 300 символов) или нажмите «Пропустить» для сброса:",
        reply_markup=skip_keyboard(),
    )


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
        situation_type=None,
        communication_role=None,
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
