"""AI request and result models."""

from __future__ import annotations

import datetime

from sqlalchemy import JSON, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, UUIDPrimaryKeyMixin


class AIRequest(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ai_requests"

    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    scenario_type: Mapped[str] = mapped_column(String(50), nullable=False)
    input_type: Mapped[str] = mapped_column(String(20), nullable=False)  # text / image / text_image
    input_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    image_mime_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    image_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(20), default="v1", nullable=False)
    modifier: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    finished_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    parent_request_id: Mapped[str | None] = mapped_column(
        String, nullable=True, index=True,
    )


class AIResult(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ai_results"

    request_id: Mapped[str] = mapped_column(
        String, nullable=False, unique=True, index=True,
    )
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
