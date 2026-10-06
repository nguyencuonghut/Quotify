"""create price freshness watch list

Revision ID: 20261006_1200
Revises: 20261006_0900
Create Date: 2026-10-06 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20261006_1200"
down_revision: str | None = "20261006_0900"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # Danh sách vật tư được theo dõi độ mới của giá, kèm chu kỳ kỳ vọng (ngày). Không có hàng
    # nghĩa là không theo dõi. Bảng riêng, không đụng bảng ngưỡng của thông báo biến động giá.
    op.create_table(
        "price_freshness_materials",
        sa.Column("material_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_watched", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("expected_interval_days", sa.Integer(), nullable=False),
        sa.Column("updated_by_id", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.CheckConstraint(
            "expected_interval_days BETWEEN 1 AND 365",
            name="ck_price_freshness_materials_interval",
        ),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("material_id"),
    )


def downgrade() -> None:
    op.drop_table("price_freshness_materials")
