"""Build final prompt messages for the AI API from scenario, user context, and style."""

from __future__ import annotations

from app.ai.prompts.analyzer import (
    ANALYZER_SYSTEM,
    ANALYZER_SYSTEM_RU,
    ANALYZER_USER_IMAGE,
    ANALYZER_USER_IMAGE_RU,
    ANALYZER_USER_TEXT,
    ANALYZER_USER_TEXT_RU,
)
from app.ai.prompts.anti_ignor import (
    ANTI_IGNOR_SYSTEM,
    ANTI_IGNOR_SYSTEM_RU,
    ANTI_IGNOR_USER_IMAGE,
    ANTI_IGNOR_USER_IMAGE_RU,
    ANTI_IGNOR_USER_TEXT,
    ANTI_IGNOR_USER_TEXT_RU,
)
from app.ai.prompts.first_message import (
    FIRST_MSG_SYSTEM,
    FIRST_MSG_SYSTEM_RU,
    FIRST_MSG_USER_IMAGE,
    FIRST_MSG_USER_IMAGE_RU,
    FIRST_MSG_USER_TEXT,
    FIRST_MSG_USER_TEXT_RU,
)
from app.ai.prompts.flirt import (
    FLIRT_SYSTEM,
    FLIRT_SYSTEM_RU,
    FLIRT_USER_IMAGE,
    FLIRT_USER_IMAGE_RU,
    FLIRT_USER_TEXT,
    FLIRT_USER_TEXT_RU,
)
from app.ai.prompts.photo_pickup import (
    PHOTO_PICKUP_SYSTEM,
    PHOTO_PICKUP_SYSTEM_RU,
    PHOTO_PICKUP_USER_IMAGE,
    PHOTO_PICKUP_USER_IMAGE_RU,
)
from app.ai.prompts.profile_review import (
    PROFILE_REVIEW_SYSTEM,
    PROFILE_REVIEW_SYSTEM_RU,
    PROFILE_REVIEW_USER_IMAGE,
    PROFILE_REVIEW_USER_IMAGE_RU,
    PROFILE_REVIEW_USER_TEXT,
    PROFILE_REVIEW_USER_TEXT_RU,
)
from app.ai.prompts.reply_message import (
    REPLY_SYSTEM,
    REPLY_SYSTEM_RU,
    REPLY_USER_IMAGE,
    REPLY_USER_IMAGE_RU,
    REPLY_USER_TEXT,
    REPLY_USER_TEXT_RU,
)
from app.ai.prompts.safety import SAFETY_SYSTEM_BLOCK, SAFETY_SYSTEM_BLOCK_RU
from app.bot.keyboards.styles import get_style_prompt, get_style_prompt_ru

# ── Template registries ────────────────────────────────────────────────────────

SCENARIO_TEMPLATES_EN = {
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
    "flirt": {
        "system": FLIRT_SYSTEM,
        "user_text": FLIRT_USER_TEXT,
        "user_image": FLIRT_USER_IMAGE,
    },
    "profile_review": {
        "system": PROFILE_REVIEW_SYSTEM,
        "user_text": PROFILE_REVIEW_USER_TEXT,
        "user_image": PROFILE_REVIEW_USER_IMAGE,
    },
}

SCENARIO_TEMPLATES_RU = {
    "first_message": {
        "system": FIRST_MSG_SYSTEM_RU,
        "user_text": FIRST_MSG_USER_TEXT_RU,
        "user_image": FIRST_MSG_USER_IMAGE_RU,
    },
    "reply_message": {
        "system": REPLY_SYSTEM_RU,
        "user_text": REPLY_USER_TEXT_RU,
        "user_image": REPLY_USER_IMAGE_RU,
    },
    "analyzer": {
        "system": ANALYZER_SYSTEM_RU,
        "user_text": ANALYZER_USER_TEXT_RU,
        "user_image": ANALYZER_USER_IMAGE_RU,
    },
    "anti_ignor": {
        "system": ANTI_IGNOR_SYSTEM_RU,
        "user_text": ANTI_IGNOR_USER_TEXT_RU,
        "user_image": ANTI_IGNOR_USER_IMAGE_RU,
    },
    "photo_pickup": {
        "system": PHOTO_PICKUP_SYSTEM_RU,
        "user_text": None,  # photo_pickup only works with images
        "user_image": PHOTO_PICKUP_USER_IMAGE_RU,
    },
    "flirt": {
        "system": FLIRT_SYSTEM_RU,
        "user_text": FLIRT_USER_TEXT_RU,
        "user_image": FLIRT_USER_IMAGE_RU,
    },
    "profile_review": {
        "system": PROFILE_REVIEW_SYSTEM_RU,
        "user_text": PROFILE_REVIEW_USER_TEXT_RU,
        "user_image": PROFILE_REVIEW_USER_IMAGE_RU,
    },
}

# ── User context builders ──────────────────────────────────────────────────────

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

SITUATION_LABELS_RU = {
    "dating_app": "сайт знакомств / онлайн-знакомства",
    "real_life": "реальная жизнь / живое общение",
    "other": "другой контекст",
}

ROLE_LABELS_RU = {
    "initiator": "инициирует разговор",
    "continuing": "продолжает существующий разговор",
    "meeting": "хочет перейти к встрече",
    "other": "другая роль",
}


def _build_user_context(
    gender: str | None = None,
    situation_type: str | None = None,
    communication_role: str | None = None,
    ai_identity_text: str | None = None,
    communication_style: str | None = None,
) -> str:
    """Compose the user-context block injected into the system prompt (English)."""
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


def _build_user_context_ru(
    gender: str | None = None,
    situation_type: str | None = None,
    communication_role: str | None = None,
    ai_identity_text: str | None = None,
    communication_style: str | None = None,
) -> str:
    """Compose the user-context block injected into the system prompt (Russian)."""
    parts: list[str] = []
    if gender:
        parts.append(f"Пол пользователя: {gender}")
    if situation_type:
        label = SITUATION_LABELS_RU.get(situation_type, situation_type)
        parts.append(f"Ситуация: {label}")
    if communication_role:
        label = ROLE_LABELS_RU.get(communication_role, communication_role)
        parts.append(f"Роль пользователя: {label}")
    if ai_identity_text:
        parts.append(f"Самоописание пользователя для персонализации: {ai_identity_text}")
    elif not parts:
        parts.append("Тон по умолчанию: вежливо, уверенно, естественно")
    if communication_style:
        parts.append(f"Предпочтение по стилю общения: {communication_style}")
    if not parts:
        return ""
    return "Контекст пользователя:\n" + "\n".join(parts)


# ── Main builder ───────────────────────────────────────────────────────────────

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
    """Return list of messages in OpenAI chat-completion format.

    The prompt language (English or Russian) is determined by the AI_PROMPT_LANGUAGE
    environment variable, centralised in app.config.settings.ai.prompt_language.
    """
    from app.config import settings as app_settings

    lang = app_settings.ai.prompt_language  # "en" or "ru"
    use_russian = lang == "ru"

    templates = SCENARIO_TEMPLATES_RU if use_russian else SCENARIO_TEMPLATES_EN
    safety_block = SAFETY_SYSTEM_BLOCK_RU if use_russian else SAFETY_SYSTEM_BLOCK
    style_fn = get_style_prompt_ru if use_russian else get_style_prompt
    ctx_fn = _build_user_context_ru if use_russian else _build_user_context

    user_context = ctx_fn(
        gender=gender,
        situation_type=situation_type,
        communication_role=communication_role,
        ai_identity_text=ai_identity_text,
        communication_style=communication_style,
    )

    style_instruction = style_fn(style)

    # Legacy modifier support
    modifier_text = ""
    if modifier:
        from app.ai.prompts.modifiers import get_modifier_prompt
        modifier_text = get_modifier_prompt(scenario, modifier)

    # Build format kwargs — only include keys that exist in the template
    format_kwargs = {
        "count": count,
        "user_context": user_context,
        "safety": safety_block,
        "style_instruction": style_instruction,
    }

    system_template = templates[scenario]["system"]
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

        image_template = templates[scenario]["user_image"]
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
        text_template = templates[scenario].get("user_text")
        if text_template:
            text_kwargs = {"input_text": input_text, "count": count}
            if extra_context and "{extra_context}" in text_template:
                text_kwargs["extra_context"] = extra_context
            user_text = text_template.format(**text_kwargs)
            messages.append({"role": "user", "content": user_text})

    return messages
