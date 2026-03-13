"""Add age, city, goals, interests columns to user_settings.

Revision ID: 003
Revises: 002
Create Date: 2026-03-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("age", sa.Integer(), nullable=True),
    )
    op.add_column(
        "user_settings",
        sa.Column("city", sa.String(100), nullable=True),
    )
    op.add_column(
        "user_settings",
        sa.Column("goals", sa.String(100), nullable=True),
    )
    op.add_column(
        "user_settings",
        sa.Column("interests", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_settings", "interests")
    op.drop_column("user_settings", "goals")
    op.drop_column("user_settings", "city")
    op.drop_column("user_settings", "age")
