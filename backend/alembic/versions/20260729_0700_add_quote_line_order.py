"""add quote line display order

Revision ID: 20260729_0700
Revises: 20260728_1100
Create Date: 2026-07-29 07:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260729_0700"
down_revision: str | None = "20260728_1100"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("quote_lines", sa.Column("line_order", sa.Integer(), nullable=True))

    op.execute(
        """
        WITH ordered_lines AS (
            SELECT
                quote_lines.id,
                ROW_NUMBER() OVER (
                    PARTITION BY quote_lines.quote_version_id
                    ORDER BY
                        materials.code ASC,
                        quote_lines.delivery_month ASC,
                        quote_lines.created_at ASC,
                        quote_lines.id ASC
                ) - 1 AS computed_order
            FROM quote_lines
            JOIN materials ON materials.id = quote_lines.material_id
        )
        UPDATE quote_lines
        SET line_order = ordered_lines.computed_order
        FROM ordered_lines
        WHERE quote_lines.id = ordered_lines.id
        """,
    )

    op.alter_column(
        "quote_lines",
        "line_order",
        existing_type=sa.Integer(),
        nullable=False,
        server_default="0",
    )
    op.create_index(
        "ix_quote_lines_version_order",
        "quote_lines",
        ["quote_version_id", "line_order"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_quote_lines_version_order", table_name="quote_lines")
    op.drop_column("quote_lines", "line_order")
