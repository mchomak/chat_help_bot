"""Onboarding flow handler (FSM-based)."""

from __future__ import annotations

import uuid

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.common import send_menu
from app.bot.keyboards.onboarding import skip_keyboard
from app.bot.states.onboarding import OnboardingStates
from app.db.repositories import user_repo

router = Router(name="onboarding")

IDENTITY_PROMPT = (
    "Шаг 3/3. Расскажите коротко о себе (до 300 символов).\n\n"
    "Например: «Мне 28 лет, работаю дизайнером, люблю путешествия "
    "и чёрный юмор. Общаюсь легко, но иногда стесняюсь писать первым».\n\n"
    "Бот будет учитывать это при генерации ответов, чтобы они звучали "
    "естественно и подходили именно вам.\n\n"
    "Нажмите «Пропустить», если не хотите заполнять."
)


# --- Step 1: Gender ---
@router.callback_query(OnboardingStates.gender, F.data.startswith("onb:gender:"))
async def on_gender(callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession) -> None:
    value = callback.data.split(":")[-1]
    if value != "skip":
        data = await state.get_data()
        await user_repo.update_settings(db_session, uuid.UUID(data["user_id"]), gender=value)
        await db_session.commit()
    await callback.answer()
    await callback.message.edit_text(
        "Шаг 2/3. Опишите ваш стиль общения (или нажмите «Пропустить»):",
        reply_markup=skip_keyboard(),
    )
    await state.set_state(OnboardingStates.style)


# --- Step 2: Style (text input or skip) ---
@router.callback_query(OnboardingStates.style, F.data == "onb:skip")
async def on_style_skip(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await callback.message.edit_text(IDENTITY_PROMPT, reply_markup=skip_keyboard())
    await state.set_state(OnboardingStates.identity)


@router.message(OnboardingStates.style)
async def on_style_text(message: types.Message, state: FSMContext, db_session: AsyncSession) -> None:
    data = await state.get_data()
    await user_repo.update_settings(
        db_session, uuid.UUID(data["user_id"]),
        communication_style=message.text[:500],
    )
    await db_session.commit()
    await message.answer(IDENTITY_PROMPT, reply_markup=skip_keyboard())
    await state.set_state(OnboardingStates.identity)


# --- Step 3: Identity (text input or skip) ---
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
