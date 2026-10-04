"""create price alert messages

Revision ID: 20261004_1500
Revises: 20261004_1400
Create Date: 2026-10-04 15:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20261004_1500"
down_revision: str | None = "20261004_1400"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

STATUSES = "'pending','sending','sent','failed','suppressed','digest_queued','skipped'"


def upgrade() -> None:
    op.create_table(
        "price_alert_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence_number", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("telegram_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("material_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("scan_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("level_max", sa.String(length=10), nullable=True),
        sa.Column("direction", sa.String(length=4), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("status_reason", sa.String(length=30), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.String(length=255), nullable=True),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "kind IN ('change','anomaly','digest')",
            name="ck_price_alert_messages_kind",
        ),
        sa.CheckConstraint(
            f"status IN ({STATUSES})",
            name="ck_price_alert_messages_status",
        ),
        sa.CheckConstraint(
            "level_max IS NULL OR level_max IN ('light','medium','large')",
            name="ck_price_alert_messages_level",
        ),
        sa.CheckConstraint(
            "direction IS NULL OR direction IN ('up','down')",
            name="ck_price_alert_messages_direction",
        ),
        sa.CheckConstraint(
            "kind = 'digest' OR material_id IS NOT NULL",
            name="ck_price_alert_messages_material_required",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["telegram_account_id"],
            ["telegram_accounts.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scan_run_id"], ["price_alert_scan_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sequence_number"),
        sa.UniqueConstraint(
            "user_id",
            "material_id",
            "scan_run_id",
            "kind",
            name="uq_price_alert_messages_unit",
        ),
    )
    op.create_index(
        "uq_price_alert_messages_digest",
        "price_alert_messages",
        ["user_id", "scan_run_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'digest' AND material_id IS NULL"),
    )
    op.create_index(
        "ix_price_alert_messages_status", "price_alert_messages", ["status", "created_at"]
    )
    op.create_index(
        "ix_price_alert_messages_user_material_day",
        "price_alert_messages",
        ["user_id", "material_id", "local_date"],
    )
    op.create_index("ix_price_alert_messages_scan_run_id", "price_alert_messages", ["scan_run_id"])

    op.create_table(
        "price_alert_message_events",
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["price_alert_messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["event_id"], ["price_alert_events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("message_id", "event_id"),
    )
    op.create_index(
        "ix_price_alert_message_events_event_id", "price_alert_message_events", ["event_id"]
    )


def downgrade() -> None:
    op.drop_table("price_alert_message_events")
    op.drop_table("price_alert_messages")
