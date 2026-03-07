"""Handler for modifier buttons (regenerate with different tone/style)."""

from __future__ import annotations

import logging
import uuid

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.common import ensure_access
from app.bot.handlers.profile_review import _format_profile_review
from app.bot.keyboards.scenarios import (
    back_to_menu_keyboard,
    first_msg_result_keyboard,
    profile_result_keyboard,
    reply_result_keyboard,
)
from app.db.repositories import ai_repo, user_repo
from app.services import ai_service

router = Router(name="modifier")
logger = logging.getLogger(__name__)

RESULT_KEYBOARD_MAP = {
    "reply_message": reply_result_keyboard,
    "first_message": first_msg_result_keyboard,
    "profile_review": profile_result_keyboard,
}


@router.callback_query(F.data.startswith("mod:"))
async def on_modifier(
    callback: types.CallbackQuery,
    state: FSMContext,
    db_session: AsyncSession,
) -> None:
    """Handle modifier button presses: mod:<scenario>:<modifier>:<parent_request_id>."""
    parts = callback.data.split(":")
    if len(parts) != 4:
        await callback.answer("Неверный формат запроса.")
        return

    _, scenario, modifier, parent_id_str = parts

    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])

    if not await ensure_access(callback, db_session, user_id):
        return

    await callback.answer("Генерирую...")

    try:
        parent_id = uuid.UUID(parent_id_str)
    except ValueError:
        await callback.message.edit_text(
            "Ошибка: не найден исходный запрос.",
            reply_markup=back_to_menu_keyboard(),
        )
        return

    # Fetch original request to reuse input
    original = await ai_repo.get_ai_request(db_session, parent_id)
    if original is None:
        await callback.message.edit_text(
            "Исходный запрос не найден. Пожалуйста, начните заново.",
            reply_markup=back_to_menu_keyboard(),
        )
        return

    await callback.message.edit_text("Генерирую новые варианты...")

    try:
        settings = await user_repo.get_user_settings(db_session, user_id)
        result = await ai_service.generate(
            db_session,
            user_id=user_id,
            scenario=scenario,
            input_text=original.input_text,
            modifier=modifier,
            parent_request_id=parent_id,
            gender=settings.gender if settings else None,
            situation_type=settings.situation_type if settings else None,
            communication_role=settings.communication_role if settings else None,
            communication_style=settings.communication_style if settings else None,
            ai_identity_text=settings.ai_identity_text if settings else None,
        )

        request_id = result.get("request_id", parent_id_str)
        kb_factory = RESULT_KEYBOARD_MAP.get(scenario)

        if scenario == "profile_review":
            text = _format_profile_review(result)
        else:
            items = result.get("items", [])
            if not items:
                await callback.message.edit_text(
                    "Не удалось сгенерировать варианты.",
                    reply_markup=back_to_menu_keyboard(),
                )
                return
            header = "Варианты ответа:" if scenario == "reply_message" else "Варианты первого сообщения:"
            text_parts = [f"{header}\n"]
            for i, item in enumerate(items, 1):
                text_parts.append(f"{i}. {item}\n")
            text = "\n".join(text_parts)

        await callback.message.edit_text(
            text,
            reply_markup=kb_factory(request_id) if kb_factory else back_to_menu_keyboard(),
        )
    except Exception:
        logger.exception("modifier generation failed")
        await callback.message.edit_text(
            "Произошла ошибка. Попробуйте еще раз.",
            reply_markup=back_to_menu_keyboard(),
        )
