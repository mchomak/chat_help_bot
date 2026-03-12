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
            [InlineKeyboardButton(text="✉️ Генератор первых сообщений", callback_data="menu:first_message")],
            [InlineKeyboardButton(text="💬 Флирт", callback_data="menu:flirt")],
            [InlineKeyboardButton(text="🔍 Анализатор диалога", callback_data="menu:analyzer")],
            [InlineKeyboardButton(text="🔄 Анти-игнор", callback_data="menu:anti_ignor")],
            [InlineKeyboardButton(text="📸 Подкаты по фото", callback_data="menu:photo_pickup")],
            [InlineKeyboardButton(text="💳 Подписка", callback_data="menu:subscription")],
            [
                InlineKeyboardButton(text="⚙️ Настройки", callback_data="menu:settings"),
                InlineKeyboardButton(text="❓ Помощь", callback_data="menu:help"),
            ],
        ],
    )
