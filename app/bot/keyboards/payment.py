"""Payment / tariff keyboards."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.config import settings


def payment_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оформить подписку", callback_data="pay:select_tariff")],
            [InlineKeyboardButton(text="📸 Докупить скриншоты", callback_data="pay:select_pack")],
            [InlineKeyboardButton(text="🔄 Проверить статус", callback_data="pay:check")],
            [InlineKeyboardButton(text="В меню", callback_data="back:menu")],
        ],
    )


def tariff_selection_keyboard() -> InlineKeyboardMarkup:
    t = settings.tariffs
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"1 неделя — {int(t.week_price)} ₽  ({t.week_screenshots} скринов)",
                callback_data="pay:tariff:week",
            )],
            [InlineKeyboardButton(
                text=f"1 месяц — {int(t.month_price)} ₽  ({t.month_screenshots} скринов)",
                callback_data="pay:tariff:month",
            )],
            [InlineKeyboardButton(
                text=f"3 месяца — {int(t.quarter_price)} ₽  ({t.quarter_screenshots} скринов)",
                callback_data="pay:tariff:quarter",
            )],
            [InlineKeyboardButton(text="Назад", callback_data="menu:subscription")],
        ],
    )


def pack_selection_keyboard() -> InlineKeyboardMarkup:
    t = settings.tariffs
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{t.pack_s_screenshots} скринов — {int(t.pack_s_price)} ₽",
                callback_data="pay:pack:s",
            )],
            [InlineKeyboardButton(
                text=f"{t.pack_m_screenshots} скринов — {int(t.pack_m_price)} ₽",
                callback_data="pay:pack:m",
            )],
            [InlineKeyboardButton(
                text=f"{t.pack_l_screenshots} скринов — {int(t.pack_l_price)} ₽",
                callback_data="pay:pack:l",
            )],
            [InlineKeyboardButton(text="Назад", callback_data="menu:subscription")],
        ],
    )


def payment_confirm_keyboard(tx_id: str, purchase_type: str, purchase_key: str) -> InlineKeyboardMarkup:
    """Stub: confirm test payment (for development/testing only).

    Encodes purchase type and key in the callback so the confirm handler
    knows what to credit without FSM state.
    """
    confirm_data = f"pay:confirm:{purchase_type}:{purchase_key}:{tx_id}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="[DEV] Подтвердить оплату", callback_data=confirm_data)],
            [InlineKeyboardButton(text="В меню", callback_data="back:menu")],
        ],
    )
