"""User model."""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import BigInteger, DateTime, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language_code: Mapped[str | None] = mapped_column(String(10), nullable=True)


class UserSettings(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, nullable=False, unique=True, index=True,
    )
    gender: Mapped[str | None] = mapped_column(String(50), nullable=True)
    situation_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    communication_role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    communication_style: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ai_identity_text: Mapped[str | None] = mapped_column(String(300), nullable=True)
    default_style: Mapped[str | None] = mapped_column(String(50), nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    goals: Mapped[str | None] = mapped_column(String(100), nullable=True)
    interests: Mapped[str | None] = mapped_column(String(500), nullable=True)
    onboarding_completed: Mapped[bool] = mapped_column(default=False, nullable=False)


class UserConsent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "user_consents"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, nullable=False, unique=True, index=True,
    )
    consent_given: Mapped[bool] = mapped_column(default=False, nullable=False)
    consented_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    version_code: Mapped[str] = mapped_column(String(20), default="v1", nullable=False)


class UserAccess(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_access"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, nullable=False, unique=True, index=True,
    )
    trial_used: Mapped[bool] = mapped_column(default=False, nullable=False)
    trial_started_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    trial_expires_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    access_status: Mapped[str] = mapped_column(
        String(20), default="none", nullable=False,
    )  # none / trial / expired / paid
    paid_until: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    last_successful_payment_id: Mapped[str | None] = mapped_column(String, nullable=True)
