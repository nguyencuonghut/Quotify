"""add price freshness reminder (Telegram 1D, Slice 5)

Revision ID: 20261007_0900
Revises: 20261006_1200
Create Date: 2026-10-07 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20261007_0900"
down_revision: str | None = "20261006_1200"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # Cờ và giờ nhắc cập nhật giá: tắt mặc định, chạy khi cả công tắc tổng `is_enabled` bật.
    op.add_column(
        "price_alert_settings",
        sa.Column("freshness_enabled", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "price_alert_settings",
        sa.Column("freshness_hour_local", sa.SmallInteger(), server_default="9", nullable=False),
    )
    op.create_check_constraint(
        "ck_price_alert_settings_freshness_hour",
        "price_alert_settings",
        "freshness_hour_local BETWEEN 0 AND 23",
    )
    op.add_column(
        "price_alert_scan_state",
        sa.Column("last_freshness_local_date", sa.Date(), nullable=True),
    )

    # Loại tin mới `freshness`: không gắn vật tư, không thuộc lần quét nào.
    op.drop_constraint("ck_price_alert_messages_kind", "price_alert_messages", type_="check")
    op.create_check_constraint(
        "ck_price_alert_messages_kind",
        "price_alert_messages",
        "kind IN ('change','anomaly','digest','freshness')",
    )
    op.drop_constraint(
        "ck_price_alert_messages_material_required",
        "price_alert_messages",
        type_="check",
    )
    op.create_check_constraint(
        "ck_price_alert_messages_material_required",
        "price_alert_messages",
        "kind IN ('digest','freshness') OR material_id IS NOT NULL",
    )
    # Mỗi người nhiều nhất một tin nhắc mỗi ngày địa phương (khóa idempotent).
    op.create_index(
        "uq_price_alert_messages_freshness",
        "price_alert_messages",
        ["user_id", "local_date"],
        unique=True,
        postgresql_where=sa.text("kind = 'freshness'"),
    )

    op.create_table(
        "price_alert_message_materials",
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("material_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("age_days", sa.Integer(), nullable=False),
        sa.Column("interval_days", sa.Integer(), nullable=False),
        sa.Column("last_received_date", sa.Date(), nullable=False),
        sa.Column("last_enterer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["price_alert_messages.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["last_enterer_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("message_id", "material_id"),
    )


def downgrade() -> None:
    op.drop_table("price_alert_message_materials")
    op.drop_index("uq_price_alert_messages_freshness", table_name="price_alert_messages")
    op.drop_constraint(
        "ck_price_alert_messages_material_required",
        "price_alert_messages",
        type_="check",
    )
    op.create_check_constraint(
        "ck_price_alert_messages_material_required",
        "price_alert_messages",
        "kind = 'digest' OR material_id IS NOT NULL",
    )
    op.drop_constraint("ck_price_alert_messages_kind", "price_alert_messages", type_="check")
    op.create_check_constraint(
        "ck_price_alert_messages_kind",
        "price_alert_messages",
        "kind IN ('change','anomaly','digest')",
    )
    op.drop_column("price_alert_scan_state", "last_freshness_local_date")
    op.drop_constraint(
        "ck_price_alert_settings_freshness_hour", "price_alert_settings", type_="check"
    )
    op.drop_column("price_alert_settings", "freshness_hour_local")
    op.drop_column("price_alert_settings", "freshness_enabled")
