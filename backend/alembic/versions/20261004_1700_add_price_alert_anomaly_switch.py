"""add price alert anomaly switch

Revision ID: 20261004_1700
Revises: 20261004_1600
Create Date: 2026-10-04 17:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20261004_1700"
down_revision: str | None = "20261004_1600"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "price_alert_settings",
        sa.Column("anomaly_enabled", sa.Boolean(), server_default="false", nullable=False),
    )
    # Ảnh chụp các giá hợp lệ gần đây lúc gắn cờ: thẻ giữ nguyên số liệu dù dữ liệu sau đó đổi.
    op.add_column(
        "price_alert_events",
        sa.Column("reference_prices", sa.ARRAY(sa.Numeric(12, 2)), nullable=True),
    )
    # Người nhận là trưởng phòng (có nút) hay người nhập (không nút), để gửi đúng thẻ.
    op.add_column(
        "price_alert_messages",
        sa.Column("audience", sa.String(length=10), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("price_alert_messages", "audience")
    op.drop_column("price_alert_events", "reference_prices")
    op.drop_column("price_alert_settings", "anomaly_enabled")
