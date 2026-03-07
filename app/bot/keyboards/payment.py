"""Payment / tariff keyboards."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def payment_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Оплатить", callback_data="pay:create")],
            [InlineKeyboardButton(text="Проверить статус", callback_data="pay:check")],
            [InlineKeyboardButton(text="В меню", callback_data="back:menu")],
        ],
    )


def payment_confirm_keyboard(tx_id: str) -> InlineKeyboardMarkup:
    """Stub: confirm test payment (for development/testing only)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="[DEV] Подтвердить оплату", callback_data=f"pay:confirm:{tx_id}")],
            [InlineKeyboardButton(text="В меню", callback_data="back:menu")],
        ],
    )
