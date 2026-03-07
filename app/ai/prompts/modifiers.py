"""Mapping of modifier keys to prompt fragments used across scenarios."""

from app.ai.prompts.first_message import (
    FIRST_MSG_MODIFIER_CONFIDENT,
    FIRST_MSG_MODIFIER_HUMOR,
    FIRST_MSG_MODIFIER_MORE,
    FIRST_MSG_MODIFIER_NEUTRAL,
)
from app.ai.prompts.profile_review import (
    PROFILE_REVIEW_MODIFIER_DETAILED,
    PROFILE_REVIEW_MODIFIER_MORE_RECS,
    PROFILE_REVIEW_MODIFIER_SHORT,
)
from app.ai.prompts.reply_message import (
    REPLY_MODIFIER_CONFIDENT,
    REPLY_MODIFIER_MORE,
    REPLY_MODIFIER_SHORTER,
    REPLY_MODIFIER_SOFTER,
)

MODIFIER_MAP: dict[str, dict[str, str]] = {
    "reply_message": {
        "softer": REPLY_MODIFIER_SOFTER,
        "confident": REPLY_MODIFIER_CONFIDENT,
        "shorter": REPLY_MODIFIER_SHORTER,
        "more": REPLY_MODIFIER_MORE,
    },
    "first_message": {
        "humor": FIRST_MSG_MODIFIER_HUMOR,
        "confident": FIRST_MSG_MODIFIER_CONFIDENT,
        "neutral": FIRST_MSG_MODIFIER_NEUTRAL,
        "more": FIRST_MSG_MODIFIER_MORE,
    },
    "profile_review": {
        "short": PROFILE_REVIEW_MODIFIER_SHORT,
        "detailed": PROFILE_REVIEW_MODIFIER_DETAILED,
        "more_recs": PROFILE_REVIEW_MODIFIER_MORE_RECS,
    },
}


def get_modifier_prompt(scenario: str, modifier: str) -> str:
    """Return prompt fragment for given scenario+modifier, or empty string."""
    return MODIFIER_MAP.get(scenario, {}).get(modifier, "")
