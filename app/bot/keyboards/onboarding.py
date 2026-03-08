"""Keyboards for the onboarding flow."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def gender_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Мужчина", callback_data="onb:gender:male")],
            [InlineKeyboardButton(text="Женщина", callback_data="onb:gender:female")],
            [InlineKeyboardButton(text="Пропустить", callback_data="onb:gender:skip")],
        ],
    )


def skip_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить", callback_data="onb:skip")],
        ],
    )
