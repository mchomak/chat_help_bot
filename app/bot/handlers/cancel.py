"""Handler for /cancel command — exits current FSM state and returns to menu."""

from __future__ import annotations

from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from app.bot.handlers.common import send_menu

router = Router(name="cancel")


@router.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current is None:
        await message.answer("Нет активного действия для отмены.")
        await send_menu(message)
        return
    await state.set_state(None)
    await message.answer("Действие отменено.")
    await send_menu(message)
