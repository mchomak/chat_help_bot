"""Consent callback handler."""

from __future__ import annotations

import uuid

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.common import send_menu
from app.bot.states.scenarios import (
    ConsentStates,
    FirstMessageStates,
    ProfileReviewStates,
    ReplyMessageStates,
)
from app.services.consent_service import give_consent

router = Router(name="consent")

SCENARIO_STATE_MAP = {
    "reply_message": ReplyMessageStates.waiting_input,
    "first_message": FirstMessageStates.waiting_input,
    "profile_review": ProfileReviewStates.waiting_input,
}

SCENARIO_PROMPT_MAP = {
    "reply_message": (
        "Отправьте скриншот переписки или текст в формате:\n"
        "Я: ...\nОна: ...\nЯ: ...\nОна: ..."
    ),
    "first_message": "Отправьте скриншот профиля, описание профиля или оба варианта.",
    "profile_review": "Отправьте описание своего профиля и при желании добавьте скриншот.",
}


@router.callback_query(ConsentStates.waiting_consent, F.data == "consent:agree")
async def on_consent_agree(
    callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession,
) -> None:
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])
    await give_consent(db_session, user_id)
    await db_session.commit()

    pending = data.get("pending_scenario")
    await callback.answer("Спасибо! Согласие принято.")

    if pending and pending in SCENARIO_STATE_MAP:
        await state.set_state(SCENARIO_STATE_MAP[pending])
        await callback.message.edit_text(SCENARIO_PROMPT_MAP[pending])
    else:
        await state.set_state(None)
        await send_menu(callback)


@router.callback_query(ConsentStates.waiting_consent, F.data == "consent:decline")
async def on_consent_decline(
    callback: types.CallbackQuery, state: FSMContext,
) -> None:
    await callback.answer()
    await state.set_state(None)
    await callback.message.edit_text(
        "Без согласия AI-функции недоступны.\n"
        "Вы можете дать согласие позже при следующем обращении."
    )
    await send_menu(callback.message)
