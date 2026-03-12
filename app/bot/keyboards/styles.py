"""Unified style selection keyboard and style definitions."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Style key -> display label
STYLE_OPTIONS: dict[str, str] = {
    "flirt": "Флирт",
    "bold": "Дерзкий",
    "romantic": "Романтичный / поэтичный",
    "intellectual": "Интеллектуальный / глубокий",
    "funny": "Максимально смешной",
    "calm": "Спокойный / уверенный",
}

# Style key -> prompt instruction for AI
STYLE_PROMPTS: dict[str, str] = {
    "flirt": "Flirty, playful tone with subtle hints and light teasing.",
    "bold": "Bold, provocative, edgy tone — confident and slightly daring.",
    "romantic": "Romantic, poetic tone — warm, heartfelt, with beautiful expressive language.",
    "intellectual": "Intellectual, deep tone — thoughtful, clever, with substance and wit.",
    "funny": "Maximum humor — witty, funny, entertaining, creative jokes and wordplay.",
    "calm": "Calm, confident tone — relaxed, assured, natural and easygoing.",
}

DEFAULT_STYLE_DESCRIPTION = "вежливо, уверенно, естественно"


def style_keyboard(callback_prefix: str = "style") -> InlineKeyboardMarkup:
    """Build an inline keyboard with style options.

    Each button callback_data = '{callback_prefix}:{style_key}'.
    """
    buttons = []
    for key, label in STYLE_OPTIONS.items():
        buttons.append(
            [InlineKeyboardButton(text=label, callback_data=f"{callback_prefix}:{key}")]
        )
    buttons.append(
        [InlineKeyboardButton(text="Назад", callback_data="back:menu")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_style_label(style_key: str | None) -> str:
    """Return human-readable style label."""
    if style_key is None:
        return DEFAULT_STYLE_DESCRIPTION
    return STYLE_OPTIONS.get(style_key, style_key)


def get_style_prompt(style_key: str | None) -> str:
    """Return AI prompt fragment for the given style."""
    if style_key is None:
        return f"Tone: {DEFAULT_STYLE_DESCRIPTION}"
    return STYLE_PROMPTS.get(style_key, f"Tone: {DEFAULT_STYLE_DESCRIPTION}")
