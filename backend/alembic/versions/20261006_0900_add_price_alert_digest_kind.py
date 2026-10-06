"""add price alert daily digest kind

Revision ID: 20261006_0900
Revises: 20261004_1700
Create Date: 2026-10-06 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20261006_0900"
down_revision: str | None = "20261004_1700"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # Phân biệt bản tin hằng ngày (mức Nhẹ) với tin tóm tắt tràn trần và cụm giá bất thường.
    op.add_column(
        "price_alert_messages",
        sa.Column("digest_kind", sa.String(length=12), nullable=True),
    )
    op.create_check_constraint(
        "ck_price_alert_messages_digest_kind",
        "price_alert_messages",
        "digest_kind IS NULL OR digest_kind = 'daily'",
    )
    # Mỗi người nhiều nhất một bản tin hằng ngày mỗi ngày địa phương (khóa idempotent).
    op.create_index(
        "uq_price_alert_messages_daily_digest",
        "price_alert_messages",
        ["user_id", "local_date"],
        unique=True,
        postgresql_where=sa.text("digest_kind = 'daily'"),
    )


def downgrade() -> None:
    op.drop_index("uq_price_alert_messages_daily_digest", table_name="price_alert_messages")
    op.drop_constraint(
        "ck_price_alert_messages_digest_kind",
        "price_alert_messages",
        type_="check",
    )
    op.drop_column("price_alert_messages", "digest_kind")
