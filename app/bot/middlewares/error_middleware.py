"""Global error handling middleware — logs errors to DB and shows user-friendly messages."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.error_repo import log_error

logger = logging.getLogger(__name__)


class ErrorLoggingMiddleware(BaseMiddleware):
    """Catch unhandled exceptions, log to DB, and reply with a friendly message."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception as exc:
            logger.exception("Unhandled error in handler")

            # Try to log to DB
            db_session: AsyncSession | None = data.get("db_session")
            if db_session:
                try:
                    await log_error(
                        db_session,
                        source="handler",
                        message=str(exc),
                        exc=exc,
                        context={
                            "event_type": type(event).__name__,
                        },
                    )
                    await db_session.commit()
                except Exception:
                    logger.exception("Failed to log error to DB")

            # Friendly error to user.
            # For CallbackQuery: do NOT use callback.answer() — it may have already been
            # called earlier in the handler (Telegram only allows answering once), or the
            # query may have expired. Use message.answer() to send a new message instead.
            error_text = "Произошла внутренняя ошибка. Попробуйте позже или напишите /menu."
            try:
                if isinstance(event, Message):
                    await event.answer(error_text)
                elif isinstance(event, CallbackQuery):
                    if event.message:
                        await event.message.answer(error_text)
                    else:
                        # Fallback: try callback.answer — may fail if already answered/expired
                        try:
                            await event.answer(error_text, show_alert=True)
                        except TelegramBadRequest:
                            logger.warning(
                                "Cannot send error to user: callback query already answered or expired"
                            )
            except Exception:
                logger.exception("Failed to send error message to user")
