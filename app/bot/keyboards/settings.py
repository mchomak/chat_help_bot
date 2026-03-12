"""Keyboards for the settings menu."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def settings_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пол", callback_data="set:edit:gender")],
            [InlineKeyboardButton(text="Ситуация", callback_data="set:edit:situation")],
            [InlineKeyboardButton(text="Роль", callback_data="set:edit:role")],
            [InlineKeyboardButton(text="Идеальная версия", callback_data="set:edit:identity")],
            [InlineKeyboardButton(text="Сбросить все", callback_data="set:reset_all")],
            [
                InlineKeyboardButton(text="Назад", callback_data="back:menu"),
                InlineKeyboardButton(text="Меню", callback_data="back:menu"),
            ],
        ],
    )
