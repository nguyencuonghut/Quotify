"""add price alert follow-up and fallback reference columns

Revision ID: 20261004_1600
Revises: 20261004_1500
Create Date: 2026-10-04 16:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20261004_1600"
down_revision: str | None = "20261004_1500"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "price_alert_settings",
        sa.Column(
            "reference_fallback_days",
            sa.Integer(),
            server_default="30",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_price_alert_settings_reference_fallback_days",
        "price_alert_settings",
        "reference_fallback_days BETWEEN 0 AND 365",
    )
    op.add_column("price_alert_events", sa.Column("prior_alert_price", sa.Numeric(12, 2)))
    op.add_column("price_alert_events", sa.Column("prior_alert_date", sa.Date()))
    op.add_column("price_alert_events", sa.Column("reference_age_days", sa.SmallInteger()))


def downgrade() -> None:
    op.drop_column("price_alert_events", "reference_age_days")
    op.drop_column("price_alert_events", "prior_alert_date")
    op.drop_column("price_alert_events", "prior_alert_price")
    op.drop_constraint(
        "ck_price_alert_settings_reference_fallback_days",
        "price_alert_settings",
        type_="check",
    )
    op.drop_column("price_alert_settings", "reference_fallback_days")
