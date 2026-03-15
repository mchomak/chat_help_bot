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
    "flirt": (
        "STYLE: Flirty and playful. Use subtle hints, double meanings, light teasing, "
        "and create romantic tension. Be charming but not vulgar. Add intrigue — make them "
        "curious and wanting more. Think 'confident flirt at a party', not 'cheesy pickup artist'."
    ),
    "bold": (
        "STYLE: Bold, daring, and provocative. Be confidently direct — say what others "
        "wouldn't dare. Use sharp wit, unexpected takes, and edgy humour. Think 'the person "
        "who owns the room' — self-assured without being rude. Take creative risks."
    ),
    "romantic": (
        "STYLE: Romantic and poetic. Use warm, heartfelt language with beautiful phrasing. "
        "Create a sense of intimacy and emotional depth. Reference feelings, sensations, "
        "and meaningful moments. Think 'a handwritten letter', not 'a greeting card'. "
        "Be genuine and sincere, not cheesy."
    ),
    "intellectual": (
        "STYLE: Intellectual and deep. Show genuine curiosity and thoughtfulness. Use clever "
        "wordplay, references, and observations that reveal depth. Ask questions that make "
        "people think. Think 'fascinating conversation at a dinner party'. Substance over "
        "surface — but still warm and engaging, not cold or pretentious."
    ),
    "funny": (
        "STYLE: Maximum humour. Be genuinely funny — witty observations, clever jokes, "
        "creative wordplay, absurd comparisons, playful self-deprecation. Think 'the funniest "
        "person in the group chat'. Each option should make someone laugh or at least smile. "
        "Humour should be smart, not crude."
    ),
    "calm": (
        "STYLE: Calm and confident. Relaxed, natural, easygoing — like someone who's "
        "comfortable in their own skin. No trying too hard, no overthinking. Simple, "
        "direct language. Think 'cool and collected'. Show interest without chasing. "
        "Less is more — confidence comes through in brevity and ease."
    ),
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
