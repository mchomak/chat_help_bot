"""Repository for error logs."""

from __future__ import annotations

import traceback

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.error_log import ErrorLog


async def log_error(
    session: AsyncSession,
    *,
    source: str,
    message: str,
    exc: BaseException | None = None,
    context: dict | None = None,
) -> ErrorLog:
    """Persist an error record."""
    tb = traceback.format_exception(exc) if exc else None
    entry = ErrorLog(
        source=source,
        message=message,
        stacktrace="".join(tb) if tb else None,
        context=context,
    )
    session.add(entry)
    await session.flush()
    return entry
