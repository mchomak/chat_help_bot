"""Middleware that provides an async DB session to every handler."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.db.session import get_session_factory


class DbSessionMiddleware(BaseMiddleware):
    """Injects `db_session` into handler kwargs. Auto-closes after handler."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        factory = get_session_factory()
        async with factory() as session:
            data["db_session"] = session
            try:
                result = await handler(event, data)
                return result
            except Exception:
                await session.rollback()
                raise
