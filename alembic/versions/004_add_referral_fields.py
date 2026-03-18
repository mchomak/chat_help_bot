"""Add referral fields: referred_by_telegram_id to users, referral_bonus_granted to user_access.

Revision ID: 004
Revises: 003
Create Date: 2026-03-18
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("referred_by_telegram_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "user_access",
        sa.Column(
            "referral_bonus_granted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("user_access", "referral_bonus_granted")
    op.drop_column("users", "referred_by_telegram_id")
