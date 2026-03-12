"""Shared handler utilities: access gate, send menu, generation helpers."""

from __future__ import annotations

import logging
import uuid

from aiogram import types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.menu import PERSISTENT_MENU, main_menu_inline
from app.bot.keyboards.onboarding import gender_keyboard
from app.bot.keyboards.payment import payment_menu_keyboard
from app.bot.keyboards.scenarios import (
    error_with_retry_keyboard,
    post_generation_keyboard,
)
from app.bot.states.onboarding import OnboardingStates
from app.services.access_service import AccessStatus, activate_trial, check_access

logger = logging.getLogger(__name__)


async def send_menu(target: types.Message | types.CallbackQuery) -> None:
    """Send main menu message."""
    if isinstance(target, types.CallbackQuery):
        await target.message.edit_text("Выберите функцию:", reply_markup=main_menu_inline())
    else:
        await target.answer(
            "Выберите функцию:",
            reply_markup=main_menu_inline(),
        )


async def start_onboarding(message: types.Message, state: FSMContext) -> None:
    """Start the onboarding flow from step 1."""
    await message.answer(
        "Давайте настроим бот под вас.",
        reply_markup=PERSISTENT_MENU,
    )
    await message.answer(
        "Шаг 1/4. Укажите ваш пол:",
        reply_markup=gender_keyboard(),
    )
    await state.set_state(OnboardingStates.gender)


async def ensure_access(
    event: types.Message | types.CallbackQuery,
    session: AsyncSession,
    user_id: uuid.UUID,
) -> bool:
    """Check access (trial/paid). Auto-activate trial if not yet used. Returns True if access granted."""
    status = await check_access(session, user_id)

    if status in (AccessStatus.TRIAL, AccessStatus.PAID):
        return True

    if status == AccessStatus.NONE:
        # Activate trial
        access = await activate_trial(session, user_id)
        if access is not None:
            await session.commit()
            msg = "Пробный период активирован на 2 часа. Приятного использования!"
            if isinstance(event, types.CallbackQuery):
                await event.answer(msg, show_alert=True)
            else:
                await event.answer(msg)
            return True

    # Trial expired or already used, no paid access
    text = (
        "Пробный период закончился.\n"
        "Для продолжения использования оформите подписку."
    )
    if isinstance(event, types.CallbackQuery):
        await event.message.edit_text(text, reply_markup=payment_menu_keyboard())
    else:
        await event.answer(text, reply_markup=payment_menu_keyboard())
    return False


def settings_kwargs(settings) -> dict:
    """Extract AI-relevant fields from UserSettings for prompt building."""
    if settings is None:
        return {}
    return {
        "gender": settings.gender,
        "situation_type": settings.situation_type,
        "communication_role": settings.communication_role,
        "ai_identity_text": settings.ai_identity_text,
    }


async def generate_and_send(
    event: types.Message | types.CallbackQuery,
    state: FSMContext,
    db_session: AsyncSession,
    *,
    user_id: uuid.UUID,
    scenario: str,
    style: str | None,
    input_text: str | None = None,
    image_base64: str | None = None,
    image_file_id: str | None = None,
    image_mime_type: str | None = None,
    image_size: int | None = None,
    extra_context: str | None = None,
    processing_text: str = "Генерирую...",
    result_header: str = "Варианты:",
) -> None:
    """Universal generation flow: call AI, format result, show post-gen keyboard.

    Saves generation context in FSM state for re-generation.
    """
    from app.db.repositories import user_repo
    from app.services import ai_service

    if isinstance(event, types.CallbackQuery):
        processing_msg = await event.message.edit_text(processing_text)
    else:
        processing_msg = await event.answer(processing_text)

    try:
        user_settings = await user_repo.get_user_settings(db_session, user_id)
        skw = settings_kwargs(user_settings)

        result = await ai_service.generate(
            db_session,
            user_id=user_id,
            scenario=scenario,
            input_text=input_text,
            image_base64=image_base64,
            image_file_id=image_file_id,
            image_mime_type=image_mime_type,
            image_size=image_size,
            style=style,
            extra_context=extra_context,
            **skw,
        )

        items = result.get("items", [])
        analysis = result.get("analysis", [])
        request_id = result.get("request_id", "")

        if not items:
            await processing_msg.edit_text(
                "Не удалось сгенерировать варианты.",
                reply_markup=error_with_retry_keyboard(),
            )
            await state.set_state(None)
            return

        text_parts = []
        if analysis:
            text_parts.append("Анализ:\n")
            for i, point in enumerate(analysis, 1):
                text_parts.append(f"{i}. {point}")
            text_parts.append("")

        text_parts.append(f"{result_header}\n")
        for i, item in enumerate(items, 1):
            text_parts.append(f"{i}. {item}")

        # Save context for re-generation
        await state.update_data(
            gen_scenario=scenario,
            gen_style=style,
            gen_input_text=input_text,
            gen_image_file_id=image_file_id,
            gen_extra_context=extra_context,
            gen_request_id=request_id,
        )
        await state.set_state(None)

        await processing_msg.edit_text(
            "\n".join(text_parts),
            reply_markup=post_generation_keyboard(scenario),
        )

    except Exception:
        logger.exception("Generation failed for scenario=%s", scenario)
        await state.update_data(
            retry_scenario=scenario,
            retry_style=style,
            retry_text=input_text,
            retry_photo_file_id=image_file_id,
            retry_extra_context=extra_context,
        )
        await processing_msg.edit_text(
            "Произошла ошибка при обработке.",
            reply_markup=error_with_retry_keyboard(),
        )
        await state.set_state(None)
