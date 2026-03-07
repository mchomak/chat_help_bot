"""Payment service — stub implementation for MVP."""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import transaction_repo
from app.services.access_service import grant_paid_access


async def create_stub_payment(
    session: AsyncSession,
    user_id: uuid.UUID,
    amount: float = 299.0,
) -> uuid.UUID:
    """Create a pending stub transaction. Returns transaction ID."""
    tx = await transaction_repo.create_transaction(
        session,
        user_id=user_id,
        amount=amount,
        provider="stub",
        comment="Stub payment for testing",
    )
    return tx.id


async def confirm_stub_payment(
    session: AsyncSession,
    tx_id: uuid.UUID,
    user_id: uuid.UUID,
    days: int = 30,
) -> bool:
    """Confirm stub payment and grant access. Returns True on success.

    Prevents double granting via access_granted flag.
    """
    tx = await transaction_repo.complete_transaction(session, tx_id, status="success")
    if tx is None:
        return False
    if tx.access_granted:
        return False

    tx.access_granted = True
    paid_until = datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=days)
    await grant_paid_access(session, user_id, paid_until, tx.id)
    return True
