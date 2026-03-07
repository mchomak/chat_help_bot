"""Middleware that ensures user exists in DB and user_id is in FSM state."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import user_repo


class EnsureUserMiddleware(BaseMiddleware):
    """Ensure user record exists and user_id is stored in FSM data."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = None
        if isinstance(event, Message) and event.from_user:
            tg_user = event.from_user
        elif isinstance(event, CallbackQuery) and event.from_user:
            tg_user = event.from_user

        if tg_user is not None:
            state: FSMContext | None = data.get("state")
            db_session: AsyncSession | None = data.get("db_session")

            if state and db_session:
                state_data = await state.get_data()
                if "user_id" not in state_data:
                    user, _ = await user_repo.get_or_create_user(
                        db_session,
                        telegram_id=tg_user.id,
                        defaults={
                            "username": tg_user.username,
                            "first_name": tg_user.first_name,
                            "last_name": tg_user.last_name,
                            "language_code": tg_user.language_code,
                        },
                    )
                    await db_session.commit()
                    await state.update_data(user_id=str(user.id))

        return await handler(event, data)
