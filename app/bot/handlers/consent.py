"""Consent callback handler.

Consent is requested at /start. Without consent the bot does not work.
"""

from __future__ import annotations

import uuid

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.common import start_onboarding
from app.bot.keyboards.menu import PERSISTENT_MENU
from app.bot.states.scenarios import ConsentStates
from app.db.repositories import user_repo
from app.services.consent_service import give_consent

router = Router(name="consent")


@router.callback_query(ConsentStates.waiting_consent, F.data == "consent:agree")
async def on_consent_agree(
    callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession,
) -> None:
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])
    await give_consent(db_session, user_id)
    await db_session.commit()

    await callback.answer("Спасибо! Согласие принято.")

    # Check if user is new (needs onboarding) or returning
    settings = await user_repo.get_user_settings(db_session, user_id)
    if settings and settings.onboarding_completed:
        from app.bot.handlers.common import send_menu

        await callback.message.edit_text("Согласие принято. Добро пожаловать!")
        await callback.message.answer("Выберите функцию:", reply_markup=PERSISTENT_MENU)
        await send_menu(callback.message)
        await state.set_state(None)
    else:
        await callback.message.edit_text("Согласие принято. Давайте настроим бот под вас.")
        await start_onboarding(callback.message, state)


@router.callback_query(ConsentStates.waiting_consent, F.data == "consent:decline")
async def on_consent_decline(
    callback: types.CallbackQuery, state: FSMContext,
) -> None:
    await callback.answer()
    await state.set_state(None)
    await callback.message.edit_text(
        "Без согласия на обработку данных бот не может работать.\n\n"
        "Если передумаете, отправьте /start."
    )
