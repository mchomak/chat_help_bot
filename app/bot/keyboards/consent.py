"""Consent confirmation keyboard."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def consent_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Согласен(на)", callback_data="consent:agree")],
            [InlineKeyboardButton(text="Не согласен(на)", callback_data="consent:decline")],
        ],
    )
