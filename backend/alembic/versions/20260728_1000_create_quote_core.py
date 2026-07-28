"""create quote core

Revision ID: 20260728_1000
Revises: 20260728_0930
Create Date: 2026-07-28 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260728_1000"
down_revision: str | None = "20260728_0930"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create quotes table
    op.create_table(
        "quotes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_quotes_created_by_id"), "quotes", ["created_by_id"], unique=False)
    op.create_index(op.f("ix_quotes_supplier_id"), "quotes", ["supplier_id"], unique=False)

    # 2. Create quote_versions table
    op.create_table(
        "quote_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quote_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("received_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_backfilled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("backfill_reason", sa.String(length=500), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by_id", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.ForeignKeyConstraint(["confirmed_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["quote_id"], ["quotes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("quote_id", "version_number", name="uq_quote_version_number"),
    )
    op.create_index(op.f("ix_quote_versions_quote_id"), "quote_versions", ["quote_id"], unique=False)
    op.create_index(op.f("ix_quote_versions_received_date"), "quote_versions", ["received_date"], unique=False)
    op.create_index(op.f("ix_quote_versions_status"), "quote_versions", ["status"], unique=False)

    # Partial index: only one draft per quote
    op.create_index(
        "uq_quote_versions_single_draft",
        "quote_versions",
        ["quote_id"],
        unique=True,
        postgresql_where=sa.text("status = 'draft'"),
    )

    # 3. Create quote_lines table
    op.create_table(
        "quote_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quote_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("material_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("price_original", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("unit", sa.String(length=10), nullable=False),
        sa.Column("delivery_month", sa.Date(), nullable=False),
        sa.Column("exchange_rate", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("exchange_rate_source", sa.String(length=120), nullable=True),
        sa.Column("exchange_rate_source_mode", sa.String(length=30), nullable=True),
        sa.Column("exchange_rate_entered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exchange_rate_manual_reason", sa.String(length=255), nullable=True),
        sa.Column("exchange_rate_actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("conversion_cost_vnd_per_kg", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("price_converted_vnd_per_kg", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("purchase_marked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("purchase_marked_by_id", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.ForeignKeyConstraint(["exchange_rate_actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["purchase_marked_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["quote_version_id"], ["quote_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_quote_lines_delivery_month"), "quote_lines", ["delivery_month"], unique=False)
    op.create_index(op.f("ix_quote_lines_material_id"), "quote_lines", ["material_id"], unique=False)
    op.create_index(op.f("ix_quote_lines_quote_version_id"), "quote_lines", ["quote_version_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_quote_lines_quote_version_id"), table_name="quote_lines")
    op.drop_index(op.f("ix_quote_lines_material_id"), table_name="quote_lines")
    op.drop_index(op.f("ix_quote_lines_delivery_month"), table_name="quote_lines")
    op.drop_table("quote_lines")

    op.drop_index("uq_quote_versions_single_draft", table_name="quote_versions")
    op.drop_index(op.f("ix_quote_versions_status"), table_name="quote_versions")
    op.drop_index(op.f("ix_quote_versions_received_date"), table_name="quote_versions")
    op.drop_index(op.f("ix_quote_versions_quote_id"), table_name="quote_versions")
    op.drop_table("quote_versions")

    op.drop_index(op.f("ix_quotes_supplier_id"), table_name="quotes")
    op.drop_index(op.f("ix_quotes_created_by_id"), table_name="quotes")
    op.drop_table("quotes")
