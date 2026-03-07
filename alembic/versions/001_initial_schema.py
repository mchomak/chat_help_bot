"""Initial schema — all tables.

Revision ID: 001
Revises: None
Create Date: 2026-03-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False, unique=True, index=True),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("first_name", sa.String(255), nullable=True),
        sa.Column("last_name", sa.String(255), nullable=True),
        sa.Column("language_code", sa.String(10), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "user_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", sa.String(), nullable=False, unique=True, index=True),
        sa.Column("gender", sa.String(50), nullable=True),
        sa.Column("situation_type", sa.String(100), nullable=True),
        sa.Column("communication_role", sa.String(100), nullable=True),
        sa.Column("communication_style", sa.String(500), nullable=True),
        sa.Column("ai_identity_text", sa.String(300), nullable=True),
        sa.Column("onboarding_completed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "user_consents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", sa.String(), nullable=False, unique=True, index=True),
        sa.Column("consent_given", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version_code", sa.String(20), nullable=False, server_default=sa.text("'v1'")),
    )

    op.create_table(
        "user_access",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", sa.String(), nullable=False, unique=True, index=True),
        sa.Column("trial_used", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("trial_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("access_status", sa.String(20), nullable=False, server_default=sa.text("'none'")),
        sa.Column("paid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_successful_payment_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "ai_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", sa.String(), nullable=False, index=True),
        sa.Column("scenario_type", sa.String(50), nullable=False),
        sa.Column("input_type", sa.String(20), nullable=False),
        sa.Column("input_text", sa.Text(), nullable=True),
        sa.Column("image_file_id", sa.String(255), nullable=True),
        sa.Column("image_mime_type", sa.String(50), nullable=True),
        sa.Column("image_size", sa.Integer(), nullable=True),
        sa.Column("image_width", sa.Integer(), nullable=True),
        sa.Column("image_height", sa.Integer(), nullable=True),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("prompt_version", sa.String(20), nullable=False, server_default=sa.text("'v1'")),
        sa.Column("modifier", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parent_request_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
    )

    op.create_table(
        "ai_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("request_id", sa.String(), nullable=False, unique=True, index=True),
        sa.Column("raw_response", sa.Text(), nullable=True),
        sa.Column("normalized_response", postgresql.JSONB(), nullable=True),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", sa.String(), nullable=False, index=True),
        sa.Column("provider", sa.String(50), nullable=False, server_default=sa.text("'stub'")),
        sa.Column("external_payment_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("currency", sa.String(10), nullable=False, server_default=sa.text("'RUB'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("access_granted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    op.create_table(
        "error_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("stacktrace", sa.Text(), nullable=True),
        sa.Column("context", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("error_logs")
    op.drop_table("transactions")
    op.drop_table("ai_results")
    op.drop_table("ai_requests")
    op.drop_table("user_access")
    op.drop_table("user_consents")
    op.drop_table("user_settings")
    op.drop_table("users")
