"""Keyboards for the settings menu."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def settings_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пол", callback_data="set:edit:gender")],
            [InlineKeyboardButton(text="Возраст", callback_data="set:edit:age")],
            [InlineKeyboardButton(text="Город", callback_data="set:edit:city")],
            [InlineKeyboardButton(text="Цель", callback_data="set:edit:goals")],
            [InlineKeyboardButton(text="Интересы", callback_data="set:edit:interests")],
            [InlineKeyboardButton(text="Ситуация", callback_data="set:edit:situation")],
            [InlineKeyboardButton(text="Роль", callback_data="set:edit:role")],
            [InlineKeyboardButton(text="О себе", callback_data="set:edit:identity")],
            [InlineKeyboardButton(text="🔗 Реферальная система", callback_data="set:referral")],
            [InlineKeyboardButton(text="Сбросить все", callback_data="set:reset_all")],
            [InlineKeyboardButton(text="Назад", callback_data="back:menu")],
        ],
    )
