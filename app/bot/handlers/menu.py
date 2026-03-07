"""Menu handler — responds to "Меню" button and /menu command."""

from __future__ import annotations

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from app.bot.handlers.common import send_menu

router = Router(name="menu")


@router.message(Command("menu"))
@router.message(F.text == "Меню")
async def cmd_menu(message: types.Message, state: FSMContext) -> None:
    await state.set_state(None)
    await send_menu(message)


@router.callback_query(F.data == "back:menu")
async def cb_back_to_menu(callback: types.CallbackQuery, state: FSMContext) -> None:
    await state.set_state(None)
    await callback.answer()
    await send_menu(callback)
