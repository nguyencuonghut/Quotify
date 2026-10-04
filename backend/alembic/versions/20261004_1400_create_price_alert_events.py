"""create price alert events

Revision ID: 20261004_1400
Revises: 20261004_1300
Create Date: 2026-10-04 14:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20261004_1400"
down_revision: str | None = "20261004_1300"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "price_alert_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence_number", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("scan_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("quote_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("material_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("delivery_month", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("quote_line_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("direction", sa.String(length=4), nullable=False),
        sa.Column("level", sa.String(length=10), nullable=True),
        sa.Column("rule", sa.String(length=2), nullable=True),
        sa.Column("percent_change", sa.Numeric(8, 2), nullable=False),
        sa.Column("price_new", sa.Numeric(12, 2), nullable=False),
        sa.Column("price_ref", sa.Numeric(12, 2), nullable=False),
        sa.Column("received_date_new", sa.Date(), nullable=False),
        sa.Column("received_date_ref", sa.Date(), nullable=True),
        sa.Column("window_min", sa.Numeric(12, 2), nullable=True),
        sa.Column("window_max", sa.Numeric(12, 2), nullable=True),
        sa.Column("window_min_date", sa.Date(), nullable=True),
        sa.Column("window_max_date", sa.Date(), nullable=True),
        sa.Column("reference_point_count", sa.SmallInteger(), nullable=True),
        sa.Column("secondary_rule", sa.String(length=2), nullable=True),
        sa.Column("secondary_percent", sa.Numeric(8, 2), nullable=True),
        sa.Column("secondary_price_ref", sa.Numeric(12, 2), nullable=True),
        sa.Column("secondary_date_ref", sa.Date(), nullable=True),
        sa.Column("cnf_price_new", sa.Numeric(12, 2), nullable=True),
        sa.Column("cnf_price_ref", sa.Numeric(12, 2), nullable=True),
        sa.Column("cnf_date_ref", sa.Date(), nullable=True),
        sa.Column("review_status", sa.String(length=10), nullable=True),
        sa.Column("attached_to_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reminded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("kind IN ('change','anomaly')", name="ck_price_alert_events_kind"),
        sa.CheckConstraint("direction IN ('up','down')", name="ck_price_alert_events_direction"),
        sa.CheckConstraint(
            "level IS NULL OR level IN ('light','medium','large')",
            name="ck_price_alert_events_level",
        ),
        sa.CheckConstraint(
            "rule IS NULL OR rule IN ('R1','R2','R3')",
            name="ck_price_alert_events_rule",
        ),
        sa.CheckConstraint(
            "review_status IS NULL OR review_status IN ('pending','accepted','rejected','expired')",
            name="ck_price_alert_events_review_status",
        ),
        sa.ForeignKeyConstraint(["scan_run_id"], ["price_alert_scan_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["quote_version_id"], ["quote_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["quote_line_id"], ["quote_lines.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["attached_to_event_id"],
            ["price_alert_events.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sequence_number"),
    )
    op.create_index(
        "uq_price_alert_events_change",
        "price_alert_events",
        ["quote_version_id", "material_id", "delivery_month"],
        unique=True,
        postgresql_where=sa.text("kind = 'change'"),
    )
    op.create_index(
        "uq_price_alert_events_anomaly",
        "price_alert_events",
        ["quote_version_id", "quote_line_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'anomaly'"),
    )
    op.create_index(
        "ix_price_alert_events_chain",
        "price_alert_events",
        ["material_id", "delivery_month", "created_at"],
    )
    op.create_index(
        "ix_price_alert_events_pending_anomaly",
        "price_alert_events",
        ["review_status"],
        postgresql_where=sa.text("kind = 'anomaly' AND review_status = 'pending'"),
    )
    op.create_index("ix_price_alert_events_scan_run_id", "price_alert_events", ["scan_run_id"])


def downgrade() -> None:
    op.drop_table("price_alert_events")
