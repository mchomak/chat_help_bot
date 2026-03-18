"""Consent confirmation keyboard."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.config import settings


def consent_keyboard() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    # Document links (shown only when URLs are configured)
    if settings.user_agreement_url:
        rows.append([
            InlineKeyboardButton(
                text="📄 Пользовательское соглашение",
                url=settings.user_agreement_url,
            )
        ])
    if settings.privacy_policy_url:
        rows.append([
            InlineKeyboardButton(
                text="🔒 Политика конфиденциальности",
                url=settings.privacy_policy_url,
            )
        ])

    rows.append([InlineKeyboardButton(text="✅ Принимаю", callback_data="consent:agree")])
    rows.append([InlineKeyboardButton(text="❌ Не принимаю", callback_data="consent:decline")])

    return InlineKeyboardMarkup(inline_keyboard=rows)
