"""Add payments table for YooKassa payment lifecycle.

Revision ID: 006
Revises: 005
Create Date: 2026-03-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("purchase_type", sa.String(20), nullable=False),
        sa.Column("purchase_key", sa.String(20), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="RUB"),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("yookassa_payment_id", sa.String(100), nullable=True),
        sa.Column("payment_url", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("goods_granted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payments_user_id", "payments", ["user_id"])
    op.create_index("ix_payments_status", "payments", ["status"])
    op.create_index("ix_payments_yookassa_payment_id", "payments", ["yookassa_payment_id"])


def downgrade() -> None:
    op.drop_index("ix_payments_yookassa_payment_id", "payments")
    op.drop_index("ix_payments_status", "payments")
    op.drop_index("ix_payments_user_id", "payments")
    op.drop_table("payments")
