"""add quote version correction metadata

Revision ID: 20260730_0200
Revises: 20260729_0810
Create Date: 2026-07-30 02:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260730_0200"
down_revision: str | None = "20260729_0810"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "quote_versions",
        sa.Column("correction_reason", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "quote_versions",
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "quote_versions",
        sa.Column("superseded_by_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "quote_versions",
        sa.Column("superseded_by_version_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_quote_versions_superseded_by_id_users",
        "quote_versions",
        "users",
        ["superseded_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_quote_versions_superseded_by_version_id_quote_versions",
        "quote_versions",
        "quote_versions",
        ["superseded_by_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_quote_versions_superseded_by_version_id",
        "quote_versions",
        ["superseded_by_version_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_quote_versions_superseded_by_version_id", table_name="quote_versions")
    op.drop_constraint(
        "fk_quote_versions_superseded_by_version_id_quote_versions",
        "quote_versions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_quote_versions_superseded_by_id_users",
        "quote_versions",
        type_="foreignkey",
    )
    op.drop_column("quote_versions", "superseded_by_version_id")
    op.drop_column("quote_versions", "superseded_by_id")
    op.drop_column("quote_versions", "superseded_at")
    op.drop_column("quote_versions", "correction_reason")
