"""Settings view and edit handlers."""

from __future__ import annotations

import uuid

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.onboarding import (
    gender_keyboard,
    role_keyboard,
    situation_keyboard,
    skip_keyboard,
)
from app.bot.keyboards.settings import settings_menu_keyboard
from app.bot.keyboards.styles import get_style_label
from app.bot.states.settings import SettingsEditStates
from app.db.repositories import user_repo

router = Router(name="settings")

GENDER_LABELS = {"male": "Мужчина", "female": "Женщина"}
SITUATION_LABELS = {
    "dating_app": "Сайт знакомств",
    "real_life": "Реальное общение",
    "other": "Другое",
}
ROLE_LABELS = {
    "initiator": "Инициатор",
    "continuing": "Продолжаю диалог",
    "meeting": "Хочу перейти к встрече",
    "other": "Другое",
}

IDENTITY_EDIT_PROMPT = (
    "Расскажите коротко о себе — «Идеальная версия» (до 300 символов).\n\n"
    "Например: «Мне 28 лет, работаю дизайнером, люблю путешествия "
    "и чёрный юмор. Общаюсь легко, но иногда стесняюсь писать первым».\n\n"
    "Бот будет учитывать это при генерации, чтобы ответы "
    "звучали естественно и подходили именно вам.\n\n"
    "Нажмите «Пропустить» для сброса."
)

CHAR_LIMIT = 300


def _format_settings(s) -> str:
    lines = [
        "Текущие настройки:\n",
        f"Пол: {GENDER_LABELS.get(s.gender, s.gender or 'не указан')}",
        f"Ситуация: {SITUATION_LABELS.get(s.situation_type, s.situation_type or 'не указана')}",
        f"Роль: {ROLE_LABELS.get(s.communication_role, s.communication_role or 'не указана')}",
        f"Идеальная версия: {s.ai_identity_text or 'не указано'}",
        f"Стиль по умолчанию: {get_style_label(s.default_style) if s.default_style else 'не выбран'}",
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
    await user_repo.update_settings(db_session, user_id, gender=value)
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
    await callback.message.edit_text("Выберите ситуацию:", reply_markup=situation_keyboard())


@router.callback_query(SettingsEditStates.editing_situation, F.data.startswith("onb:situation:"))
async def save_situation(callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession) -> None:
    value = callback.data.split(":")[-1]
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])
    await user_repo.update_settings(db_session, user_id, situation_type=value)
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
    await callback.message.edit_text("Выберите роль:", reply_markup=role_keyboard())


@router.callback_query(SettingsEditStates.editing_role, F.data.startswith("onb:role:"))
async def save_role(callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession) -> None:
    value = callback.data.split(":")[-1]
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])
    await user_repo.update_settings(db_session, user_id, communication_role=value)
    await db_session.commit()
    await callback.answer("Сохранено!")
    await state.set_state(None)
    s = await user_repo.get_user_settings(db_session, user_id)
    await callback.message.edit_text(_format_settings(s), reply_markup=settings_menu_keyboard())


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
    if len(text) > CHAR_LIMIT:
        await message.answer(
            f"Текст слишком длинный ({len(text)}/{CHAR_LIMIT} символов). "
            "Пожалуйста, сократите."
        )
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
        default_style=None,
    )
    await db_session.commit()
    await callback.answer("Все настройки сброшены!")
    s = await user_repo.get_user_settings(db_session, user_id)
    await callback.message.edit_text(_format_settings(s), reply_markup=settings_menu_keyboard())
