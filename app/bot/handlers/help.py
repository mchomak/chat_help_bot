"""Help handler."""

from __future__ import annotations

from aiogram import F, Router, types
from aiogram.filters import Command

from app.bot.keyboards.scenarios import back_to_menu_keyboard

router = Router(name="help")

HELP_TEXT = (
    "Что умеет бот:\n\n"
    "💬 Ответить на сообщение — отправьте скриншот или текст переписки, "
    "и бот предложит варианты ответа.\n\n"
    "✉️ Первое сообщение — отправьте скриншот профиля или описание, "
    "и бот предложит варианты первого сообщения.\n\n"
    "👤 Разбор профиля — отправьте описание своего профиля, "
    "и бот даст рекомендации по улучшению.\n\n"
    "Вместо скриншота можно отправить текст.\n\n"
    "Пробный период — 2 часа, активируется при первом AI-запросе.\n\n"
    "Все ответы носят рекомендательный характер и не гарантируют результат."
)


@router.message(Command("help"))
async def cmd_help(message: types.Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=back_to_menu_keyboard())


@router.callback_query(F.data == "menu:help")
async def cb_help(callback: types.CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text(HELP_TEXT, reply_markup=back_to_menu_keyboard())
