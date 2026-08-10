"""rename conversion cost to processing cost and add import tax rate

Revision ID: 20260810_0900
Revises: 20260804_0900
Create Date: 2026-08-10 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260810_0900"
down_revision: str | None = "20260804_0900"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "quotify_settings",
        "conversion_cost_vnd_per_kg",
        new_column_name="processing_cost_vnd_per_kg",
    )
    op.drop_constraint(
        "ck_quotify_settings_conversion_cost_non_negative",
        "quotify_settings",
        type_="check",
    )
    op.create_check_constraint(
        "ck_quotify_settings_processing_cost_non_negative",
        "quotify_settings",
        "processing_cost_vnd_per_kg >= 0",
    )
    op.add_column(
        "quotify_settings",
        sa.Column(
            "import_tax_rate_percent",
            sa.Numeric(precision=5, scale=2),
            server_default="0.00",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_quotify_settings_import_tax_rate_non_negative",
        "quotify_settings",
        "import_tax_rate_percent >= 0",
    )

    op.alter_column(
        "quote_lines",
        "conversion_cost_vnd_per_kg",
        new_column_name="processing_cost_vnd_per_kg",
    )
    op.add_column(
        "quote_lines",
        sa.Column(
            "import_tax_rate_percent",
            sa.Numeric(precision=5, scale=2),
            nullable=True,
        ),
    )
    op.execute(
        "UPDATE quote_lines SET import_tax_rate_percent = 0.00 "
        "WHERE processing_cost_vnd_per_kg IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_column("quote_lines", "import_tax_rate_percent")
    op.alter_column(
        "quote_lines",
        "processing_cost_vnd_per_kg",
        new_column_name="conversion_cost_vnd_per_kg",
    )

    op.drop_constraint(
        "ck_quotify_settings_import_tax_rate_non_negative",
        "quotify_settings",
        type_="check",
    )
    op.drop_column("quotify_settings", "import_tax_rate_percent")
    op.drop_constraint(
        "ck_quotify_settings_processing_cost_non_negative",
        "quotify_settings",
        type_="check",
    )
    op.create_check_constraint(
        "ck_quotify_settings_conversion_cost_non_negative",
        "quotify_settings",
        "processing_cost_vnd_per_kg >= 0",
    )
    op.alter_column(
        "quotify_settings",
        "processing_cost_vnd_per_kg",
        new_column_name="conversion_cost_vnd_per_kg",
    )
