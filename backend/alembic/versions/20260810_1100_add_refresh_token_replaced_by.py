"""add replaced_by_id to refresh_tokens for rotation reuse detection

Revision ID: 20260810_1100
Revises: 20260810_0900
Create Date: 2026-08-10 11:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260810_1100"
down_revision: str | None = "20260810_0900"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "refresh_tokens",
        sa.Column("replaced_by_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_refresh_tokens_replaced_by_id",
        "refresh_tokens",
        "refresh_tokens",
        ["replaced_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_refresh_tokens_replaced_by_id"),
        "refresh_tokens",
        ["replaced_by_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_refresh_tokens_replaced_by_id"), table_name="refresh_tokens")
    op.drop_constraint("fk_refresh_tokens_replaced_by_id", "refresh_tokens", type_="foreignkey")
    op.drop_column("refresh_tokens", "replaced_by_id")
