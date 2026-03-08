"""Keyboards for the settings menu."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def settings_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пол", callback_data="set:edit:gender")],
            [InlineKeyboardButton(text="Стиль общения", callback_data="set:edit:style")],
            [InlineKeyboardButton(text="О себе", callback_data="set:edit:identity")],
            [InlineKeyboardButton(text="Сбросить все", callback_data="set:reset_all")],
            [InlineKeyboardButton(text="Статус доступа", callback_data="set:access_status")],
            [InlineKeyboardButton(text="В меню", callback_data="back:menu")],
        ],
    )
