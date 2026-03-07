"""Keyboards for the settings menu."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def settings_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пол", callback_data="set:edit:gender")],
            [InlineKeyboardButton(text="Тип ситуации", callback_data="set:edit:situation")],
            [InlineKeyboardButton(text="Роль в общении", callback_data="set:edit:role")],
            [InlineKeyboardButton(text="Стиль общения", callback_data="set:edit:style")],
            [InlineKeyboardButton(text="Кто я для ИИ", callback_data="set:edit:identity")],
            [InlineKeyboardButton(text="Сбросить все", callback_data="set:reset_all")],
            [InlineKeyboardButton(text="Статус доступа", callback_data="set:access_status")],
            [InlineKeyboardButton(text="В меню", callback_data="back:menu")],
        ],
    )
