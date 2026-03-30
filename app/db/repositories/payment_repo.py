"""Repository for Payment records (YooKassa payment lifecycle)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.payment import Payment, PaymentStatus


async def create_payment(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    purchase_type: str,
    purchase_key: str,
    amount: float,
    currency: str = "RUB",
) -> Payment:
    """Insert a new Payment record with status=pending and flush (no commit)."""
    payment = Payment(
        user_id=user_id,
        purchase_type=purchase_type,
        purchase_key=purchase_key,
        amount=amount,
        currency=currency,
        status=PaymentStatus.PENDING,
    )
    session.add(payment)
    await session.flush()
    return payment


async def get_payment(session: AsyncSession, payment_id: uuid.UUID) -> Payment | None:
    stmt = select(Payment).where(Payment.id == payment_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_by_yookassa_id(session: AsyncSession, yookassa_payment_id: str) -> Payment | None:
    stmt = select(Payment).where(Payment.yookassa_payment_id == yookassa_payment_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_latest_pending_payment(
    session: AsyncSession, user_id: uuid.UUID,
) -> Payment | None:
    """Return the most recent payment in waiting_for_payment status for the user."""
    stmt = (
        select(Payment)
        .where(
            Payment.user_id == user_id,
            Payment.status == PaymentStatus.WAITING_FOR_PAYMENT,
        )
        .order_by(Payment.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
