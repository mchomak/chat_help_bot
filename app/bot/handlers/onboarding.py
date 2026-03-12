"""Onboarding flow handler (FSM-based).

Steps: 1) Gender  2) Situation  3) Role  4) Ideal version (optional)
"""

from __future__ import annotations

import uuid

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.common import send_menu
from app.bot.keyboards.onboarding import role_keyboard, situation_keyboard, skip_keyboard
from app.bot.states.onboarding import OnboardingStates
from app.db.repositories import user_repo

router = Router(name="onboarding")

IDENTITY_PROMPT = (
    "Шаг 4/4. Расскажите коротко о себе — «Идеальная версия» (до 300 символов).\n\n"
    "Например: «Мне 28 лет, работаю дизайнером, люблю путешествия "
    "и чёрный юмор. Общаюсь легко, но иногда стесняюсь писать первым».\n\n"
    "Бот будет учитывать это при генерации ответов, чтобы они звучали "
    "естественно и подходили именно вам.\n\n"
    "Нажмите «Пропустить», если не хотите заполнять."
)

CHAR_LIMIT = 300


# --- Step 1: Gender ---
@router.callback_query(OnboardingStates.gender, F.data.startswith("onb:gender:"))
async def on_gender(callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession) -> None:
    value = callback.data.split(":")[-1]
    data = await state.get_data()
    await user_repo.update_settings(db_session, uuid.UUID(data["user_id"]), gender=value)
    await db_session.commit()
    await callback.answer()
    await callback.message.edit_text(
        "Шаг 2/4. Выберите ситуацию:",
        reply_markup=situation_keyboard(),
    )
    await state.set_state(OnboardingStates.situation)


# --- Step 2: Situation ---
@router.callback_query(OnboardingStates.situation, F.data.startswith("onb:situation:"))
async def on_situation(callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession) -> None:
    value = callback.data.split(":")[-1]
    data = await state.get_data()
    await user_repo.update_settings(db_session, uuid.UUID(data["user_id"]), situation_type=value)
    await db_session.commit()
    await callback.answer()
    await callback.message.edit_text(
        "Шаг 3/4. Выберите вашу роль:",
        reply_markup=role_keyboard(),
    )
    await state.set_state(OnboardingStates.role)


# --- Step 3: Role ---
@router.callback_query(OnboardingStates.role, F.data.startswith("onb:role:"))
async def on_role(callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession) -> None:
    value = callback.data.split(":")[-1]
    data = await state.get_data()
    await user_repo.update_settings(db_session, uuid.UUID(data["user_id"]), communication_role=value)
    await db_session.commit()
    await callback.answer()
    await callback.message.edit_text(IDENTITY_PROMPT, reply_markup=skip_keyboard())
    await state.set_state(OnboardingStates.identity)


# --- Step 4: Identity / Ideal version (text input or skip) ---
@router.callback_query(OnboardingStates.identity, F.data == "onb:skip")
async def on_identity_skip(callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession) -> None:
    await _finish_onboarding(callback, state, db_session)


@router.message(OnboardingStates.identity)
async def on_identity_text(message: types.Message, state: FSMContext, db_session: AsyncSession) -> None:
    text = message.text or ""
    if len(text) > CHAR_LIMIT:
        await message.answer(
            f"Текст слишком длинный ({len(text)}/{CHAR_LIMIT} символов). "
            "Пожалуйста, сократите."
        )
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
