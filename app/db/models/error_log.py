"""Centralised error log model."""

from __future__ import annotations

import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, UUIDPrimaryKeyMixin


class ErrorLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "error_logs"

    source: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    stacktrace: Mapped[str | None] = mapped_column(Text, nullable=True)
    context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
