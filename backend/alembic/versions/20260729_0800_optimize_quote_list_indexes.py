"""optimize quote list indexes

Revision ID: 20260729_0800
Revises: 20260729_0700
Create Date: 2026-07-29 08:00:00
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260729_0800"
down_revision: str | None = "20260729_0700"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_index(
        "ix_quote_lines_material_delivery_created",
        "quote_lines",
        ["material_id", "delivery_month", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_quote_lines_delivery_created",
        "quote_lines",
        ["delivery_month", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_quote_lines_currency_created",
        "quote_lines",
        ["currency", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_quote_lines_converted_price",
        "quote_lines",
        ["price_converted_vnd_per_kg", "id"],
        unique=False,
    )
    op.create_index(
        "ix_quote_lines_original_price",
        "quote_lines",
        ["price_original", "id"],
        unique=False,
    )
    op.create_index(
        "ix_quote_lines_purchase_marked",
        "quote_lines",
        ["purchase_marked_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_quote_lines_created_id",
        "quote_lines",
        ["created_at", "id"],
        unique=False,
    )

    op.create_index(
        "ix_quote_versions_received_id",
        "quote_versions",
        ["received_date", "id"],
        unique=False,
    )
    op.create_index(
        "ix_quote_versions_created_by_received",
        "quote_versions",
        ["created_by_id", "received_date", "id"],
        unique=False,
    )
    op.create_index(
        "ix_quote_versions_version_number_id",
        "quote_versions",
        ["version_number", "id"],
        unique=False,
    )
    op.create_index(
        "ix_quotes_supplier_id_id",
        "quotes",
        ["supplier_id", "id"],
        unique=False,
    )

    op.create_index(
        "ix_suppliers_name_trgm",
        "suppliers",
        ["name"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_suppliers_code_trgm",
        "suppliers",
        ["code"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"code": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_materials_name_trgm",
        "materials",
        ["name"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_materials_code_trgm",
        "materials",
        ["code"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"code": "gin_trgm_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_materials_code_trgm", table_name="materials")
    op.drop_index("ix_materials_name_trgm", table_name="materials")
    op.drop_index("ix_suppliers_code_trgm", table_name="suppliers")
    op.drop_index("ix_suppliers_name_trgm", table_name="suppliers")
    op.drop_index("ix_quotes_supplier_id_id", table_name="quotes")
    op.drop_index("ix_quote_versions_version_number_id", table_name="quote_versions")
    op.drop_index("ix_quote_versions_created_by_received", table_name="quote_versions")
    op.drop_index("ix_quote_versions_received_id", table_name="quote_versions")
    op.drop_index("ix_quote_lines_created_id", table_name="quote_lines")
    op.drop_index("ix_quote_lines_purchase_marked", table_name="quote_lines")
    op.drop_index("ix_quote_lines_original_price", table_name="quote_lines")
    op.drop_index("ix_quote_lines_converted_price", table_name="quote_lines")
    op.drop_index("ix_quote_lines_currency_created", table_name="quote_lines")
    op.drop_index("ix_quote_lines_delivery_created", table_name="quote_lines")
    op.drop_index("ix_quote_lines_material_delivery_created", table_name="quote_lines")
