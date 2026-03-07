"""Repository for payment transactions."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.transaction import Transaction


async def create_transaction(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    amount: float = 299.0,
    currency: str = "RUB",
    provider: str = "stub",
    comment: str | None = None,
) -> Transaction:
    tx = Transaction(
        user_id=str(user_id),
        amount=amount,
        currency=currency,
        provider=provider,
        comment=comment,
    )
    session.add(tx)
    await session.flush()
    return tx


async def get_transaction(session: AsyncSession, tx_id: uuid.UUID) -> Transaction | None:
    stmt = select(Transaction).where(Transaction.id == tx_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_pending_transactions(
    session: AsyncSession, user_id: uuid.UUID,
) -> list[Transaction]:
    stmt = (
        select(Transaction)
        .where(Transaction.user_id == str(user_id), Transaction.status == "pending")
        .order_by(Transaction.created_at.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def complete_transaction(
    session: AsyncSession,
    tx_id: uuid.UUID,
    status: str = "success",
    error_message: str | None = None,
) -> Transaction | None:
    """Mark transaction as success/failed. Returns None if not found or already processed."""
    tx = await get_transaction(session, tx_id)
    if tx is None or tx.status != "pending":
        return None
    tx.status = status
    tx.error_message = error_message
    await session.flush()
    return tx
