"""Main menu and persistent keyboards."""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

# Persistent reply keyboard with single "Меню" button
PERSISTENT_MENU = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Меню")]],
    resize_keyboard=True,
    is_persistent=True,
)


def main_menu_inline() -> InlineKeyboardMarkup:
    """Inline keyboard for the main menu."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💬 Ответить на сообщение", callback_data="menu:reply_message")],
            [InlineKeyboardButton(text="✉️ Первое сообщение", callback_data="menu:first_message")],
            [InlineKeyboardButton(text="👤 Разбор профиля", callback_data="menu:profile_review")],
            [InlineKeyboardButton(text="⚙️ Настройки", callback_data="menu:settings")],
            [InlineKeyboardButton(text="💳 Оплата / Тариф", callback_data="menu:payment")],
            [InlineKeyboardButton(text="❓ Помощь", callback_data="menu:help")],
        ],
    )
