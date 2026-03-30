"""Payment record model — full lifecycle for YooKassa payments."""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Boolean, DateTime, Numeric, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, UUIDPrimaryKeyMixin


class PaymentStatus:
    PENDING = "pending"                      # DB record created, API call not yet made
    WAITING_FOR_PAYMENT = "waiting_for_payment"  # YooKassa payment created, awaiting user
    SUCCEEDED = "succeeded"                  # YooKassa confirmed payment
    CANCELED = "canceled"                    # Canceled by user or YooKassa
    API_ERROR = "api_error"                  # YooKassa API call failed
    FAILED = "failed"                        # Payment failed on YooKassa side


class Payment(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "payments"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    # "tariff" or "pack"
    purchase_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # "week" / "month" / "quarter"  or  "s" / "m" / "l"
    purchase_key: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="RUB", nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default=PaymentStatus.PENDING, nullable=False, index=True,
    )
    yookassa_payment_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    payment_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Idempotency guard: set to True once goods (access / screenshots) are credited
    goods_granted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )
