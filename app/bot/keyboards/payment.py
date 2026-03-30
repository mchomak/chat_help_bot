"""Payment / tariff keyboards."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app import tariffs_config


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
    rows = []
    for plan in tariffs_config.TARIFFS.values():
        rows.append([InlineKeyboardButton(
            text=f"{plan.label} — {int(plan.price)} ₽  ({plan.base_screenshots} скринов)",
            callback_data=f"pay:tariff:{plan.key}",
        )])
    rows.append([InlineKeyboardButton(text="Назад", callback_data="menu:subscription")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def pack_selection_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for pack in tariffs_config.PACKS.values():
        rows.append([InlineKeyboardButton(
            text=f"{pack.label} — {int(pack.price)} ₽",
            callback_data=f"pay:pack:{pack.key}",
        )])
    rows.append([InlineKeyboardButton(text="Назад", callback_data="menu:subscription")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def payment_pending_keyboard(payment_url: str, payment_id: str) -> InlineKeyboardMarkup:
    """Keyboard shown after a payment is created: link to YooKassa + status check."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Перейти к оплате", url=payment_url)],
            [InlineKeyboardButton(
                text="🔄 Проверить статус оплаты",
                callback_data=f"pay:poll:{payment_id}",
            )],
            [InlineKeyboardButton(text="В меню", callback_data="back:menu")],
        ],
    )


def payment_error_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Попробовать снова", callback_data="pay:select_tariff")],
            [InlineKeyboardButton(text="В меню", callback_data="back:menu")],
        ],
    )
