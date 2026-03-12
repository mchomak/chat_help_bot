"""Handler for the 'Flirt' menu item — style selector.

Sets the default style for all generation scenarios.
"""

from __future__ import annotations

import uuid

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.scenarios import nav_keyboard
from app.bot.keyboards.styles import get_style_label, style_keyboard
from app.db.repositories import user_repo

router = Router(name="flirt")


@router.callback_query(F.data == "menu:flirt")
async def start_flirt(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await callback.message.edit_text(
        "Выберите стиль ответов по умолчанию:",
        reply_markup=style_keyboard("flirtstyle"),
    )


@router.callback_query(F.data.startswith("flirtstyle:"))
async def on_flirt_style_chosen(
    callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession,
) -> None:
    style_key = callback.data.split(":")[-1]
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])

    await user_repo.update_settings(db_session, user_id, default_style=style_key)
    await db_session.commit()

    await callback.answer("Стиль сохранён!")
    await callback.message.edit_text(
        f"Стиль «{get_style_label(style_key)}» установлен по умолчанию.\n\n"
        "Он будет применяться при генерации ответов во всех режимах.",
        reply_markup=nav_keyboard("menu"),
    )
