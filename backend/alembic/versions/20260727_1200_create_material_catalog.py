"""create material catalog

Revision ID: 20260727_1200
Revises: 20260724_0930
Create Date: 2026-07-27 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260727_1200"
down_revision: str | None = "20260724_0930"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "material_types",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
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
            "status in ('active', 'inactive')",
            name="ck_material_types_status",
        ),
        sa.CheckConstraint(
            "code = upper(btrim(code))",
            name="ck_material_types_code_normalized",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_material_types_code"), "material_types", ["code"], unique=True)
    op.create_index(op.f("ix_material_types_name"), "material_types", ["name"], unique=False)

    op.create_table(
        "materials",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("material_type_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
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
        sa.CheckConstraint("status in ('active', 'inactive')", name="ck_materials_status"),
        sa.CheckConstraint("code = upper(btrim(code))", name="ck_materials_code_normalized"),
        sa.ForeignKeyConstraint(
            ["material_type_id"],
            ["material_types.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_materials_code"), "materials", ["code"], unique=True)
    op.create_index(op.f("ix_materials_name"), "materials", ["name"], unique=False)
    op.create_index(
        op.f("ix_materials_material_type_id"),
        "materials",
        ["material_type_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_materials_material_type_id"), table_name="materials")
    op.drop_index(op.f("ix_materials_name"), table_name="materials")
    op.drop_index(op.f("ix_materials_code"), table_name="materials")
    op.drop_table("materials")
    op.drop_index(op.f("ix_material_types_name"), table_name="material_types")
    op.drop_index(op.f("ix_material_types_code"), table_name="material_types")
    op.drop_table("material_types")
