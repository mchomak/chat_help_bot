"""Onboarding flow handler (FSM-based).

Steps: 1) Gender  2) Age  3) City  4) Goals  5) Interests
       6) Situation  7) Role  8) About me (identity)
"""

from __future__ import annotations

import uuid

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.common import send_menu
from app.bot.keyboards.onboarding import (
    goals_keyboard,
    role_keyboard,
    situation_keyboard,
    skip_keyboard,
)
from app.bot.states.onboarding import OnboardingStates
from app.db.repositories import user_repo

router = Router(name="onboarding")

TOTAL_STEPS = 8

IDENTITY_PROMPT = (
    f"Шаг {TOTAL_STEPS}/{TOTAL_STEPS} · Расскажите немного о себе (до 300 символов).\n\n"
    "Например: «Мне 28 лет, работаю дизайнером, люблю путешествия "
    "и чёрный юмор. Общаюсь легко, но иногда стесняюсь писать первым».\n\n"
    "Бот учтёт это при генерации — чтобы сообщения звучали естественно "
    "и подходили именно вам.\n\n"
    "Можно пропустить, если не хотите заполнять."
)

CHAR_LIMIT = 300
INTERESTS_CHAR_LIMIT = 500


# --- Step 1: Gender ---
@router.callback_query(OnboardingStates.gender, F.data.startswith("onb:gender:"))
async def on_gender(callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession) -> None:
    value = callback.data.split(":")[-1]
    data = await state.get_data()
    await user_repo.update_settings(db_session, uuid.UUID(data["user_id"]), gender=value)
    await db_session.commit()
    await callback.answer()
    await callback.message.edit_text(
        "Шаг 2/8 · Сколько вам лет?\n\nВведите число или нажмите «Пропустить».",
        reply_markup=skip_keyboard(),
    )
    await state.set_state(OnboardingStates.age)


# --- Step 2: Age ---
@router.callback_query(OnboardingStates.age, F.data == "onb:skip")
async def on_age_skip(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await callback.message.edit_text(
        "Шаг 3/8 · Из какого вы города?\n\nВведите название или нажмите «Пропустить».",
        reply_markup=skip_keyboard(),
    )
    await state.set_state(OnboardingStates.city)


@router.message(OnboardingStates.age)
async def on_age_text(message: types.Message, state: FSMContext, db_session: AsyncSession) -> None:
    text = (message.text or "").strip()
    if not text.isdigit() or not (13 <= int(text) <= 120):
        await message.answer("Введите корректный возраст — число от 13 до 120.")
        return
    data = await state.get_data()
    await user_repo.update_settings(db_session, uuid.UUID(data["user_id"]), age=int(text))
    await db_session.commit()
    await message.answer(
        "Шаг 3/8 · Из какого вы города?\n\nВведите название или нажмите «Пропустить».",
        reply_markup=skip_keyboard(),
    )
    await state.set_state(OnboardingStates.city)


# --- Step 3: City ---
@router.callback_query(OnboardingStates.city, F.data == "onb:skip")
async def on_city_skip(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await callback.message.edit_text(
        "Шаг 4/8 · Какая у вас цель?",
        reply_markup=goals_keyboard(),
    )
    await state.set_state(OnboardingStates.goals)


@router.message(OnboardingStates.city)
async def on_city_text(message: types.Message, state: FSMContext, db_session: AsyncSession) -> None:
    text = (message.text or "").strip()
    if len(text) > 100:
        await message.answer("Название слишком длинное — максимум 100 символов.")
        return
    data = await state.get_data()
    await user_repo.update_settings(db_session, uuid.UUID(data["user_id"]), city=text)
    await db_session.commit()
    await message.answer(
        "Шаг 4/8 · Какая у вас цель?",
        reply_markup=goals_keyboard(),
    )
    await state.set_state(OnboardingStates.goals)


# --- Step 4: Goals ---
@router.callback_query(OnboardingStates.goals, F.data.startswith("onb:goals:"))
async def on_goals(callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession) -> None:
    value = callback.data.split(":")[-1]
    data = await state.get_data()
    await user_repo.update_settings(db_session, uuid.UUID(data["user_id"]), goals=value)
    await db_session.commit()
    await callback.answer()
    await callback.message.edit_text(
        "Шаг 5/8 · Расскажите о своих интересах и хобби (до 500 символов).\n\n"
        "Можно пропустить — нажмите кнопку ниже.",
        reply_markup=skip_keyboard(),
    )
    await state.set_state(OnboardingStates.interests)


@router.callback_query(OnboardingStates.goals, F.data == "onb:skip")
async def on_goals_skip(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await callback.message.edit_text(
        "Шаг 5/8 · Расскажите о своих интересах и хобби (до 500 символов).\n\n"
        "Можно пропустить — нажмите кнопку ниже.",
        reply_markup=skip_keyboard(),
    )
    await state.set_state(OnboardingStates.interests)


# --- Step 5: Interests ---
@router.callback_query(OnboardingStates.interests, F.data == "onb:skip")
async def on_interests_skip(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await callback.message.edit_text(
        "Шаг 6/8 · Выберите вашу ситуацию:",
        reply_markup=situation_keyboard(),
    )
    await state.set_state(OnboardingStates.situation)


@router.message(OnboardingStates.interests)
async def on_interests_text(message: types.Message, state: FSMContext, db_session: AsyncSession) -> None:
    text = (message.text or "").strip()
    if len(text) > INTERESTS_CHAR_LIMIT:
        await message.answer(
            f"Текст слишком длинный ({len(text)}/{INTERESTS_CHAR_LIMIT} симв.). "
            "Попробуйте сократить."
        )
        return
    data = await state.get_data()
    await user_repo.update_settings(db_session, uuid.UUID(data["user_id"]), interests=text)
    await db_session.commit()
    await message.answer(
        "Шаг 6/8 · Выберите вашу ситуацию:",
        reply_markup=situation_keyboard(),
    )
    await state.set_state(OnboardingStates.situation)


# --- Step 6: Situation ---
@router.callback_query(OnboardingStates.situation, F.data.startswith("onb:situation:"))
async def on_situation(callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession) -> None:
    value = callback.data.split(":")[-1]
    data = await state.get_data()
    await user_repo.update_settings(db_session, uuid.UUID(data["user_id"]), situation_type=value)
    await db_session.commit()
    await callback.answer()
    await callback.message.edit_text(
        "Шаг 7/8 · Выберите вашу роль:",
        reply_markup=role_keyboard(),
    )
    await state.set_state(OnboardingStates.role)


# --- Step 7: Role ---
@router.callback_query(OnboardingStates.role, F.data.startswith("onb:role:"))
async def on_role(callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession) -> None:
    value = callback.data.split(":")[-1]
    data = await state.get_data()
    await user_repo.update_settings(db_session, uuid.UUID(data["user_id"]), communication_role=value)
    await db_session.commit()
    await callback.answer()
    await callback.message.edit_text(IDENTITY_PROMPT, reply_markup=skip_keyboard())
    await state.set_state(OnboardingStates.identity)


# --- Step 8: Identity / About me (text input or skip) ---
@router.callback_query(OnboardingStates.identity, F.data == "onb:skip")
async def on_identity_skip(callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession) -> None:
    await _finish_onboarding(callback, state, db_session)


@router.message(OnboardingStates.identity)
async def on_identity_text(message: types.Message, state: FSMContext, db_session: AsyncSession) -> None:
    text = message.text or ""
    if len(text) > CHAR_LIMIT:
        await message.answer(
            f"Текст слишком длинный ({len(text)}/{CHAR_LIMIT} симв.). "
            "Попробуйте сократить."
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
        await event.answer("Настройка завершена ✓")
        await event.message.edit_text("Всё готово! Теперь бот знает о вас чуть больше 🙌")
        await send_menu(event.message)
    else:
        await event.answer("Всё готово! Теперь бот знает о вас чуть больше 🙌")
        await send_menu(event)
