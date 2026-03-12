"""Build final prompt messages for the AI API from scenario, user context, and style."""

from __future__ import annotations

from app.ai.prompts.analyzer import (
    ANALYZER_SYSTEM,
    ANALYZER_USER_IMAGE,
    ANALYZER_USER_TEXT,
)
from app.ai.prompts.anti_ignor import (
    ANTI_IGNOR_SYSTEM,
    ANTI_IGNOR_USER_IMAGE,
    ANTI_IGNOR_USER_TEXT,
)
from app.ai.prompts.first_message import (
    FIRST_MSG_SYSTEM,
    FIRST_MSG_USER_IMAGE,
    FIRST_MSG_USER_TEXT,
)
from app.ai.prompts.photo_pickup import (
    PHOTO_PICKUP_SYSTEM,
    PHOTO_PICKUP_USER_IMAGE,
)
from app.ai.prompts.profile_review import (
    PROFILE_REVIEW_SYSTEM,
    PROFILE_REVIEW_USER_IMAGE,
    PROFILE_REVIEW_USER_TEXT,
)
from app.ai.prompts.reply_message import (
    REPLY_SYSTEM,
    REPLY_USER_IMAGE,
    REPLY_USER_TEXT,
)
from app.ai.prompts.safety import SAFETY_SYSTEM_BLOCK
from app.bot.keyboards.styles import get_style_prompt

SCENARIO_TEMPLATES = {
    "first_message": {
        "system": FIRST_MSG_SYSTEM,
        "user_text": FIRST_MSG_USER_TEXT,
        "user_image": FIRST_MSG_USER_IMAGE,
    },
    "reply_message": {
        "system": REPLY_SYSTEM,
        "user_text": REPLY_USER_TEXT,
        "user_image": REPLY_USER_IMAGE,
    },
    "analyzer": {
        "system": ANALYZER_SYSTEM,
        "user_text": ANALYZER_USER_TEXT,
        "user_image": ANALYZER_USER_IMAGE,
    },
    "anti_ignor": {
        "system": ANTI_IGNOR_SYSTEM,
        "user_text": ANTI_IGNOR_USER_TEXT,
        "user_image": ANTI_IGNOR_USER_IMAGE,
    },
    "photo_pickup": {
        "system": PHOTO_PICKUP_SYSTEM,
        "user_text": None,  # photo_pickup only works with images
        "user_image": PHOTO_PICKUP_USER_IMAGE,
    },
    "profile_review": {
        "system": PROFILE_REVIEW_SYSTEM,
        "user_text": PROFILE_REVIEW_USER_TEXT,
        "user_image": PROFILE_REVIEW_USER_IMAGE,
    },
}

SITUATION_LABELS = {
    "dating_app": "dating app / online dating",
    "real_life": "real life / in-person communication",
    "other": "other context",
}

ROLE_LABELS = {
    "initiator": "initiating conversation",
    "continuing": "continuing existing conversation",
    "meeting": "wants to move to an in-person meeting",
    "other": "other role",
}


def _build_user_context(
    gender: str | None = None,
    situation_type: str | None = None,
    communication_role: str | None = None,
    ai_identity_text: str | None = None,
    communication_style: str | None = None,
) -> str:
    """Compose the user-context block injected into the system prompt."""
    parts: list[str] = []
    if gender:
        parts.append(f"User gender: {gender}")
    if situation_type:
        label = SITUATION_LABELS.get(situation_type, situation_type)
        parts.append(f"Situation: {label}")
    if communication_role:
        label = ROLE_LABELS.get(communication_role, communication_role)
        parts.append(f"User role: {label}")
    if ai_identity_text:
        parts.append(f"User self-description for personalisation: {ai_identity_text}")
    elif not parts:
        # Default style when no identity provided
        parts.append("Default tone: вежливо, уверенно, естественно")
    if communication_style:
        parts.append(f"Communication style preference: {communication_style}")
    if not parts:
        return ""
    return "User context:\n" + "\n".join(parts)


def build_messages(
    *,
    scenario: str,
    input_text: str | None = None,
    has_image: bool = False,
    image_base64: str | None = None,
    style: str | None = None,
    modifier: str | None = None,
    extra_context: str | None = None,
    count: int = 4,
    gender: str | None = None,
    situation_type: str | None = None,
    communication_role: str | None = None,
    ai_identity_text: str | None = None,
    communication_style: str | None = None,
) -> list[dict]:
    """Return list of messages in OpenAI chat-completion format."""
    templates = SCENARIO_TEMPLATES[scenario]
    user_context = _build_user_context(
        gender=gender,
        situation_type=situation_type,
        communication_role=communication_role,
        ai_identity_text=ai_identity_text,
        communication_style=communication_style,
    )

    style_instruction = get_style_prompt(style)

    # Legacy modifier support
    modifier_text = ""
    if modifier:
        from app.ai.prompts.modifiers import get_modifier_prompt
        modifier_text = get_modifier_prompt(scenario, modifier)

    # Build format kwargs — only include keys that exist in the template
    format_kwargs = {
        "count": count,
        "user_context": user_context,
        "safety": SAFETY_SYSTEM_BLOCK,
        "style_instruction": style_instruction,
    }

    system_template = templates["system"]
    system_text = system_template.format(**format_kwargs)

    if modifier_text:
        system_text += f"\n\nAdditional instruction: {modifier_text}"

    messages: list[dict] = [{"role": "system", "content": system_text}]

    # User message
    if has_image and image_base64:
        user_content: list[dict] = []
        user_content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
        })

        image_template = templates["user_image"]
        # Build caption with available format variables
        caption_kwargs = {"count": count}
        if extra_context and "{extra_context}" in image_template:
            caption_kwargs["extra_context"] = extra_context
        caption = image_template.format(**caption_kwargs)

        if input_text:
            caption += f"\n\nAdditional context from user:\n{input_text}"
        user_content.append({"type": "text", "text": caption})
        messages.append({"role": "user", "content": user_content})
    elif input_text:
        text_template = templates.get("user_text")
        if text_template:
            text_kwargs = {"input_text": input_text, "count": count}
            if extra_context and "{extra_context}" in text_template:
                text_kwargs["extra_context"] = extra_context
            user_text = text_template.format(**text_kwargs)
            messages.append({"role": "user", "content": user_text})

    return messages
