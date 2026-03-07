"""Tests for payment stub flow."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import transaction_repo
from app.services.access_service import AccessStatus, check_access
from app.services.payment_service import confirm_stub_payment, create_stub_payment


@pytest.mark.asyncio
async def test_create_stub_payment(session: AsyncSession, sample_user) -> None:
    tx_id = await create_stub_payment(session, sample_user.id)
    assert tx_id is not None
    tx = await transaction_repo.get_transaction(session, tx_id)
    assert tx.status == "pending"
    assert tx.provider == "stub"


@pytest.mark.asyncio
async def test_confirm_stub_payment_grants_access(session: AsyncSession, sample_user) -> None:
    tx_id = await create_stub_payment(session, sample_user.id)
    success = await confirm_stub_payment(session, tx_id, sample_user.id)
    assert success is True

    status = await check_access(session, sample_user.id)
    assert status == AccessStatus.PAID


@pytest.mark.asyncio
async def test_confirm_stub_payment_idempotent(session: AsyncSession, sample_user) -> None:
    tx_id = await create_stub_payment(session, sample_user.id)
    await confirm_stub_payment(session, tx_id, sample_user.id)
    # Second attempt should fail gracefully
    second = await confirm_stub_payment(session, tx_id, sample_user.id)
    assert second is False
