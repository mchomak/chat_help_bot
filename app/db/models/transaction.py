"""Transaction / payment event model."""

from __future__ import annotations

import datetime

from sqlalchemy import DateTime, Numeric, String, Text, func
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, UUIDPrimaryKeyMixin


class Transaction(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "transactions"

    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(50), default="stub", nullable=False)
    external_payment_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False,
    )  # pending / success / failed / cancelled
    amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="RUB", nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_granted: Mapped[bool] = mapped_column(default=False, nullable=False)
