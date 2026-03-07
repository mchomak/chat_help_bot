"""Handler for /start command and onboarding."""

from __future__ import annotations

from aiogram import F, Router, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.common import send_menu
from app.bot.keyboards.menu import PERSISTENT_MENU
from app.bot.keyboards.onboarding import gender_keyboard, skip_keyboard
from app.bot.states.onboarding import OnboardingStates
from app.db.repositories import user_repo

router = Router(name="start")

WELCOME_TEXT = (
    "Привет! Я — бот-помощник для знакомств.\n\n"
    "Я помогу:\n"
    "• подобрать ответ на сообщение\n"
    "• написать первое сообщение\n"
    "• разобрать ваш профиль\n\n"
    "Все ответы носят рекомендательный характер.\n\n"
    "Хотите пройти быструю настройку?"
)


@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext, db_session: AsyncSession) -> None:
    user, created = await user_repo.get_or_create_user(
        db_session,
        telegram_id=message.from_user.id,
        defaults={
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name,
            "language_code": message.from_user.language_code,
        },
    )
    if not created:
        # Update profile info on re-start
        await user_repo.update_user_fields(
            db_session,
            user,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
        )
    await db_session.commit()

    await state.clear()
    await state.update_data(user_id=str(user.id))

    settings = await user_repo.get_user_settings(db_session, user.id)
    if settings and settings.onboarding_completed:
        await message.answer("С возвращением!", reply_markup=PERSISTENT_MENU)
        await send_menu(message)
        return

    from app.bot.keyboards.onboarding import gender_keyboard

    await message.answer(WELCOME_TEXT, reply_markup=PERSISTENT_MENU)
    await message.answer(
        "Шаг 1/5. Укажите ваш пол:",
        reply_markup=gender_keyboard(),
    )
    await state.set_state(OnboardingStates.gender)
