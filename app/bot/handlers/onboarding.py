"""Onboarding flow handler (FSM-based)."""

from __future__ import annotations

import uuid

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.common import send_menu
from app.bot.keyboards.onboarding import (
    role_keyboard,
    situation_keyboard,
    skip_keyboard,
)
from app.bot.states.onboarding import OnboardingStates
from app.db.repositories import user_repo

router = Router(name="onboarding")


# --- Step 1: Gender ---
@router.callback_query(OnboardingStates.gender, F.data.startswith("onb:gender:"))
async def on_gender(callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession) -> None:
    value = callback.data.split(":")[-1]
    if value != "skip":
        data = await state.get_data()
        await user_repo.update_settings(db_session, uuid.UUID(data["user_id"]), gender=value)
        await db_session.commit()
    await callback.answer()
    await callback.message.edit_text("Шаг 2/5. Тип ситуации:", reply_markup=situation_keyboard())
    await state.set_state(OnboardingStates.situation)


# --- Step 2: Situation ---
@router.callback_query(OnboardingStates.situation, F.data.startswith("onb:sit:"))
async def on_situation(callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession) -> None:
    value = callback.data.split(":")[-1]
    if value != "skip":
        data = await state.get_data()
        await user_repo.update_settings(db_session, uuid.UUID(data["user_id"]), situation_type=value)
        await db_session.commit()
    await callback.answer()
    await callback.message.edit_text("Шаг 3/5. Ваша роль в общении:", reply_markup=role_keyboard())
    await state.set_state(OnboardingStates.role)


# --- Step 3: Role ---
@router.callback_query(OnboardingStates.role, F.data.startswith("onb:role:"))
async def on_role(callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession) -> None:
    value = callback.data.split(":")[-1]
    if value != "skip":
        data = await state.get_data()
        await user_repo.update_settings(db_session, uuid.UUID(data["user_id"]), communication_role=value)
        await db_session.commit()
    await callback.answer()
    await callback.message.edit_text(
        "Шаг 4/5. Опишите ваш стиль общения (или нажмите «Пропустить»):",
        reply_markup=skip_keyboard(),
    )
    await state.set_state(OnboardingStates.style)


# --- Step 4: Style (text input or skip) ---
@router.callback_query(OnboardingStates.style, F.data == "onb:skip")
async def on_style_skip(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await callback.message.edit_text(
        "Шаг 5/5. «Кто я для ИИ» — краткое описание себя (до 300 символов).\n"
        "Это поможет делать ответы более персонализированными.\n"
        "Нажмите «Пропустить», если не хотите заполнять.",
        reply_markup=skip_keyboard(),
    )
    await state.set_state(OnboardingStates.identity)


@router.message(OnboardingStates.style)
async def on_style_text(message: types.Message, state: FSMContext, db_session: AsyncSession) -> None:
    data = await state.get_data()
    await user_repo.update_settings(
        db_session, uuid.UUID(data["user_id"]),
        communication_style=message.text[:500],
    )
    await db_session.commit()
    await message.answer(
        "Шаг 5/5. «Кто я для ИИ» — краткое описание себя (до 300 символов).\n"
        "Это поможет делать ответы более персонализированными.\n"
        "Нажмите «Пропустить», если не хотите заполнять.",
        reply_markup=skip_keyboard(),
    )
    await state.set_state(OnboardingStates.identity)


# --- Step 5: Identity (text input or skip) ---
@router.callback_query(OnboardingStates.identity, F.data == "onb:skip")
async def on_identity_skip(callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession) -> None:
    await _finish_onboarding(callback, state, db_session)


@router.message(OnboardingStates.identity)
async def on_identity_text(message: types.Message, state: FSMContext, db_session: AsyncSession) -> None:
    text = message.text or ""
    if len(text) > 300:
        await message.answer("Текст слишком длинный (макс. 300 символов). Пожалуйста, сократите.")
        return
    data = await state.get_data()
    await user_repo.update_settings(
        db_session, uuid.UUID(data["user_id"]),
        ai_identity_text=text,
    )
    await db_session.commit()
    await _finish_onboarding(message, state, db_session)


async def _finish_onboarding(
    event: types.Message | types.CallbackQuery,
    state: FSMContext,
    db_session: AsyncSession,
) -> None:
    data = await state.get_data()
    await user_repo.update_settings(
        db_session, uuid.UUID(data["user_id"]),
        onboarding_completed=True,
    )
    await db_session.commit()
    await state.set_state(None)

    if isinstance(event, types.CallbackQuery):
        await event.answer("Настройка завершена!")
        await event.message.edit_text("Настройка завершена! Добро пожаловать.")
        await send_menu(event.message)
    else:
        await event.answer("Настройка завершена! Добро пожаловать.")
        await send_menu(event)
