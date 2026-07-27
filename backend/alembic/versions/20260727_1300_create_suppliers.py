"""create suppliers

Revision ID: 20260727_1300
Revises: 20260727_1200
Create Date: 2026-07-27 13:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260727_1300"
down_revision: str | None = "20260727_1200"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "suppliers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("supplier_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("tax_code", sa.String(length=50), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "supplier_type in ('domestic', 'international')",
            name="ck_suppliers_supplier_type",
        ),
        sa.CheckConstraint("status in ('active', 'inactive')", name="ck_suppliers_status"),
        sa.CheckConstraint("code = upper(btrim(code))", name="ck_suppliers_code_normalized"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_suppliers_code"), "suppliers", ["code"], unique=True)
    op.create_index(op.f("ix_suppliers_name"), "suppliers", ["name"], unique=False)
    op.create_index(
        op.f("ix_suppliers_supplier_type"),
        "suppliers",
        ["supplier_type"],
        unique=False,
    )

    op.create_table(
        "supplier_contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("title", sa.String(length=150), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "status in ('active', 'inactive')",
            name="ck_supplier_contacts_status",
        ),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_supplier_contacts_supplier_id"),
        "supplier_contacts",
        ["supplier_id"],
        unique=False,
    )

    op.create_table(
        "supplier_materials",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("material_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("supplier_id", "material_id", name="uq_supplier_materials_pair"),
    )
    op.create_index(
        op.f("ix_supplier_materials_material_id"),
        "supplier_materials",
        ["material_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_supplier_materials_supplier_id"),
        "supplier_materials",
        ["supplier_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_supplier_materials_supplier_id"), table_name="supplier_materials")
    op.drop_index(op.f("ix_supplier_materials_material_id"), table_name="supplier_materials")
    op.drop_table("supplier_materials")
    op.drop_index(op.f("ix_supplier_contacts_supplier_id"), table_name="supplier_contacts")
    op.drop_table("supplier_contacts")
    op.drop_index(op.f("ix_suppliers_supplier_type"), table_name="suppliers")
    op.drop_index(op.f("ix_suppliers_name"), table_name="suppliers")
    op.drop_index(op.f("ix_suppliers_code"), table_name="suppliers")
    op.drop_table("suppliers")
