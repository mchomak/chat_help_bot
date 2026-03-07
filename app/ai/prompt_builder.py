"""Build final prompt messages for the AI API from scenario, user context, and modifiers."""

from __future__ import annotations

from app.ai.prompts.first_message import (
    FIRST_MSG_SYSTEM,
    FIRST_MSG_USER_IMAGE,
    FIRST_MSG_USER_TEXT,
)
from app.ai.prompts.modifiers import get_modifier_prompt
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

SCENARIO_TEMPLATES = {
    "reply_message": {
        "system": REPLY_SYSTEM,
        "user_text": REPLY_USER_TEXT,
        "user_image": REPLY_USER_IMAGE,
    },
    "first_message": {
        "system": FIRST_MSG_SYSTEM,
        "user_text": FIRST_MSG_USER_TEXT,
        "user_image": FIRST_MSG_USER_IMAGE,
    },
    "profile_review": {
        "system": PROFILE_REVIEW_SYSTEM,
        "user_text": PROFILE_REVIEW_USER_TEXT,
        "user_image": PROFILE_REVIEW_USER_IMAGE,
    },
}


def _build_user_context(
    gender: str | None = None,
    situation_type: str | None = None,
    communication_role: str | None = None,
    communication_style: str | None = None,
    ai_identity_text: str | None = None,
) -> str:
    """Compose the user-context block injected into the system prompt."""
    parts: list[str] = []
    if gender:
        parts.append(f"User gender: {gender}")
    if situation_type:
        parts.append(f"Situation: {situation_type}")
    if communication_role:
        parts.append(f"User role: {communication_role}")
    if communication_style:
        parts.append(f"Communication style: {communication_style}")
    if ai_identity_text:
        parts.append(f"User self-description for personalisation: {ai_identity_text}")
    if not parts:
        return ""
    return "User context:\n" + "\n".join(parts)


def build_messages(
    *,
    scenario: str,
    input_text: str | None = None,
    has_image: bool = False,
    image_base64: str | None = None,
    modifier: str | None = None,
    count: int = 4,
    gender: str | None = None,
    situation_type: str | None = None,
    communication_role: str | None = None,
    communication_style: str | None = None,
    ai_identity_text: str | None = None,
) -> list[dict]:
    """Return list of messages in OpenAI chat-completion format."""
    templates = SCENARIO_TEMPLATES[scenario]
    user_context = _build_user_context(
        gender=gender,
        situation_type=situation_type,
        communication_role=communication_role,
        communication_style=communication_style,
        ai_identity_text=ai_identity_text,
    )

    modifier_text = ""
    if modifier:
        modifier_text = get_modifier_prompt(scenario, modifier)

    system_text = templates["system"].format(
        count=count,
        user_context=user_context,
        safety=SAFETY_SYSTEM_BLOCK,
    )
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
        caption = templates["user_image"].format(count=count)
        if input_text:
            caption += f"\n\nAdditional context from user:\n{input_text}"
        user_content.append({"type": "text", "text": caption})
        messages.append({"role": "user", "content": user_content})
    elif input_text:
        user_text = templates["user_text"].format(input_text=input_text, count=count)
        messages.append({"role": "user", "content": user_text})

    return messages
