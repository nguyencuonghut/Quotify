"""add cancellation fields to quotes

Revision ID: 20260824_1000
Revises: 20260819_0900
Create Date: 2026-08-24 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260824_1000"
down_revision: str | None = "20260819_0900"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "quotes",
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "quotes",
        sa.Column("cancelled_by_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "quotes",
        sa.Column("cancel_reason", sa.String(length=500), nullable=True),
    )
    op.create_foreign_key(
        "fk_quotes_cancelled_by_id_users",
        "quotes",
        "users",
        ["cancelled_by_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_quotes_cancelled_by_id_users", "quotes", type_="foreignkey")
    op.drop_column("quotes", "cancel_reason")
    op.drop_column("quotes", "cancelled_by_id")
    op.drop_column("quotes", "cancelled_at")
