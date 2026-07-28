"""create quotify settings

Revision ID: 20260728_0900
Revises: 20260727_1400
Create Date: 2026-07-28 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260728_0900"
down_revision: str | None = "20260727_1400"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "quotify_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "singleton_key",
            sa.String(length=30),
            server_default="default",
            nullable=False,
        ),
        sa.Column(
            "conversion_cost_vnd_per_kg",
            sa.Numeric(12, 2),
            server_default="200.00",
            nullable=False,
        ),
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
            "singleton_key = 'default'",
            name="ck_quotify_settings_singleton_key",
        ),
        sa.CheckConstraint(
            "conversion_cost_vnd_per_kg >= 0",
            name="ck_quotify_settings_conversion_cost_non_negative",
        ),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_quotify_settings_singleton_key"),
        "quotify_settings",
        ["singleton_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_quotify_settings_singleton_key"), table_name="quotify_settings")
    op.drop_table("quotify_settings")
