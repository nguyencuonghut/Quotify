"""create price alert foundation tables

Revision ID: 20261004_1200
Revises: 20261004_1100
Create Date: 2026-10-04 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20261004_1200"
down_revision: str | None = "20261004_1100"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

SETTINGS_ROW_ID = "00000000-0000-4000-8000-0000000000a1"
SCAN_STATE_ROW_ID = "00000000-0000-4000-8000-0000000000a2"


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "price_alert_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "singleton_key",
            sa.String(length=30),
            server_default="default",
            nullable=False,
        ),
        sa.Column("reference_working_days", sa.Integer(), server_default="7", nullable=False),
        sa.Column(
            "light_from_percent",
            sa.Numeric(5, 2),
            server_default="2.50",
            nullable=False,
        ),
        sa.Column(
            "medium_from_percent",
            sa.Numeric(5, 2),
            server_default="5.00",
            nullable=False,
        ),
        sa.Column(
            "large_over_percent",
            sa.Numeric(5, 2),
            server_default="10.00",
            nullable=False,
        ),
        sa.Column("anomaly_percent", sa.Numeric(5, 2), server_default="30.00", nullable=False),
        sa.Column("anomaly_lookback_days", sa.Integer(), server_default="30", nullable=False),
        sa.Column(
            "max_trigger_delay_working_days",
            sa.Integer(),
            server_default="3",
            nullable=False,
        ),
        sa.Column("staff_lookback_days", sa.Integer(), server_default="90", nullable=False),
        sa.Column("dedupe_window_days", sa.Integer(), server_default="14", nullable=False),
        sa.Column("immediate_cap_per_scan", sa.Integer(), server_default="30", nullable=False),
        sa.Column("digest_hour_local", sa.SmallInteger(), server_default="8", nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("updated_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "singleton_key = 'default'",
            name="ck_price_alert_settings_singleton_key",
        ),
        sa.CheckConstraint(
            "0 < light_from_percent AND light_from_percent < medium_from_percent "
            "AND medium_from_percent < large_over_percent "
            "AND large_over_percent < anomaly_percent",
            name="ck_price_alert_settings_thresholds_ordered",
        ),
        sa.CheckConstraint(
            "reference_working_days BETWEEN 1 AND 30",
            name="ck_price_alert_settings_reference_working_days",
        ),
        sa.CheckConstraint(
            "anomaly_lookback_days BETWEEN 1 AND 365",
            name="ck_price_alert_settings_anomaly_lookback_days",
        ),
        sa.CheckConstraint(
            "max_trigger_delay_working_days BETWEEN 0 AND 30",
            name="ck_price_alert_settings_max_trigger_delay",
        ),
        sa.CheckConstraint(
            "staff_lookback_days BETWEEN 1 AND 365",
            name="ck_price_alert_settings_staff_lookback_days",
        ),
        sa.CheckConstraint(
            "dedupe_window_days BETWEEN 0 AND 90",
            name="ck_price_alert_settings_dedupe_window_days",
        ),
        sa.CheckConstraint(
            "immediate_cap_per_scan BETWEEN 1 AND 500",
            name="ck_price_alert_settings_immediate_cap",
        ),
        sa.CheckConstraint(
            "digest_hour_local BETWEEN 0 AND 23",
            name="ck_price_alert_settings_digest_hour",
        ),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("singleton_key"),
    )

    op.create_table(
        "price_alert_scan_state",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "singleton_key",
            sa.String(length=30),
            server_default="default",
            nullable=False,
        ),
        sa.Column("watermark_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enabled_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_digest_local_date", sa.Date(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "singleton_key = 'default'",
            name="ck_price_alert_scan_state_singleton_key",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("singleton_key"),
    )

    op.create_table(
        "price_alert_scan_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("versions_scanned", sa.Integer(), server_default="0", nullable=False),
        sa.Column("events_created", sa.Integer(), server_default="0", nullable=False),
        sa.Column("messages_created", sa.Integer(), server_default="0", nullable=False),
        sa.Column("messages_sent", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_price_alert_scan_runs_started_at",
        "price_alert_scan_runs",
        ["started_at"],
    )

    op.create_table(
        "price_alert_scanned_versions",
        sa.Column("version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "scanned_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("is_trigger_source", sa.Boolean(), nullable=False),
        sa.Column("trigger_delay_working_days", sa.SmallInteger(), nullable=True),
        sa.Column("scan_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["version_id"], ["quote_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["scan_run_id"],
            ["price_alert_scan_runs.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("version_id"),
    )
    op.create_index(
        "ix_price_alert_scanned_versions_scanned_at",
        "price_alert_scanned_versions",
        ["scanned_at"],
    )
    op.create_index(
        "ix_price_alert_scanned_versions_scan_run_id",
        "price_alert_scanned_versions",
        ["scan_run_id"],
    )

    op.create_table(
        "price_alert_material_thresholds",
        sa.Column("material_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("light_from_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("medium_from_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("large_over_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("anomaly_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("updated_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "(light_from_percent IS NULL) = (medium_from_percent IS NULL) "
            "AND (medium_from_percent IS NULL) = (large_over_percent IS NULL)",
            name="ck_price_alert_material_thresholds_all_or_none",
        ),
        sa.CheckConstraint(
            "light_from_percent IS NULL OR "
            "(0 < light_from_percent AND light_from_percent < medium_from_percent "
            "AND medium_from_percent < large_over_percent)",
            name="ck_price_alert_material_thresholds_ordered",
        ),
        sa.CheckConstraint(
            "anomaly_percent IS NULL OR large_over_percent IS NULL "
            "OR anomaly_percent > large_over_percent",
            name="ck_price_alert_material_thresholds_anomaly_above_large",
        ),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("material_id"),
    )

    op.create_table(
        "user_alert_preferences",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("min_level", sa.String(length=10), nullable=True),
        sa.Column("admin_receive_all", sa.Boolean(), server_default="false", nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "min_level IS NULL OR min_level IN ('light','medium','large')",
            name="ck_user_alert_preferences_min_level",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.execute(
        sa.text(
            f"""
            INSERT INTO price_alert_settings (id, singleton_key)
            VALUES ('{SETTINGS_ROW_ID}', 'default')
            ON CONFLICT (singleton_key) DO NOTHING
            """,
        ),
    )
    op.execute(
        sa.text(
            f"""
            INSERT INTO price_alert_scan_state (id, singleton_key)
            VALUES ('{SCAN_STATE_ROW_ID}', 'default')
            ON CONFLICT (singleton_key) DO NOTHING
            """,
        ),
    )


def downgrade() -> None:
    op.drop_table("user_alert_preferences")
    op.drop_table("price_alert_material_thresholds")
    op.drop_index(
        "ix_price_alert_scanned_versions_scan_run_id",
        table_name="price_alert_scanned_versions",
    )
    op.drop_index(
        "ix_price_alert_scanned_versions_scanned_at",
        table_name="price_alert_scanned_versions",
    )
    op.drop_table("price_alert_scanned_versions")
    op.drop_index("ix_price_alert_scan_runs_started_at", table_name="price_alert_scan_runs")
    op.drop_table("price_alert_scan_runs")
    op.drop_table("price_alert_scan_state")
    op.drop_table("price_alert_settings")
