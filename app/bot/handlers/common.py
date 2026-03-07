"""Shared handler utilities: access gate, consent gate, send menu."""

from __future__ import annotations

import uuid

from aiogram import types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.consent import consent_keyboard
from app.bot.keyboards.menu import PERSISTENT_MENU, main_menu_inline
from app.bot.keyboards.payment import payment_menu_keyboard
from app.bot.states.scenarios import ConsentStates
from app.services.access_service import AccessStatus, activate_trial, check_access
from app.services.consent_service import has_consent


async def send_menu(target: types.Message | types.CallbackQuery) -> None:
    """Send main menu message."""
    if isinstance(target, types.CallbackQuery):
        await target.message.edit_text("Выберите функцию:", reply_markup=main_menu_inline())
    else:
        await target.answer(
            "Выберите функцию:",
            reply_markup=main_menu_inline(),
        )


async def ensure_consent(
    event: types.Message | types.CallbackQuery,
    session: AsyncSession,
    user_id: uuid.UUID,
    state: FSMContext,
    next_scenario: str,
) -> bool:
    """Check consent; if not given, show consent request. Returns True if consent exists."""
    if await has_consent(session, user_id):
        return True

    await state.update_data(pending_scenario=next_scenario)
    await state.set_state(ConsentStates.waiting_consent)

    text = (
        "Перед использованием AI-функций необходимо ваше согласие.\n\n"
        "• Вы отправляете текст и/или скриншоты для анализа\n"
        "• Данные используются для формирования AI-ответов\n"
        "• Сервис не гарантирует результат общения\n"
        "• Вы подтверждаете согласие на обработку переданных данных\n\n"
        "Подтверждаете?"
    )
    if isinstance(event, types.CallbackQuery):
        await event.message.edit_text(text, reply_markup=consent_keyboard())
    else:
        await event.answer(text, reply_markup=consent_keyboard())
    return False


async def ensure_access(
    event: types.Message | types.CallbackQuery,
    session: AsyncSession,
    user_id: uuid.UUID,
) -> bool:
    """Check access (trial/paid). Auto-activate trial if not yet used. Returns True if access granted."""
    status = await check_access(session, user_id)

    if status in (AccessStatus.TRIAL, AccessStatus.PAID):
        return True

    if status == AccessStatus.NONE:
        # Activate trial
        access = await activate_trial(session, user_id)
        if access is not None:
            await session.commit()
            msg = "Пробный период активирован на 2 часа. Приятного использования!"
            if isinstance(event, types.CallbackQuery):
                await event.answer(msg, show_alert=True)
            else:
                await event.answer(msg)
            return True

    # Trial expired or already used, no paid access
    text = (
        "Пробный период закончился.\n"
        "Для продолжения использования оформите подписку."
    )
    if isinstance(event, types.CallbackQuery):
        await event.message.edit_text(text, reply_markup=payment_menu_keyboard())
    else:
        await event.answer(text, reply_markup=payment_menu_keyboard())
    return False
