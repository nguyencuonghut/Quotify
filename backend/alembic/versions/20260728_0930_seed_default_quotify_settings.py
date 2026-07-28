"""seed default quotify settings

Revision ID: 20260728_0930
Revises: 20260728_0900
Create Date: 2026-07-28 09:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260728_0930"
down_revision: str | None = "20260728_0900"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO quotify_settings (
                id,
                singleton_key,
                conversion_cost_vnd_per_kg,
                created_at,
                updated_at
            )
            VALUES (
                '00000000-0000-4000-8000-000000000001',
                'default',
                200.00,
                now(),
                now()
            )
            ON CONFLICT (singleton_key) DO NOTHING
            """,
        ),
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM quotify_settings
            WHERE id = '00000000-0000-4000-8000-000000000001'
              AND singleton_key = 'default'
              AND updated_by_id IS NULL
              AND conversion_cost_vnd_per_kg = 200.00
            """,
        ),
    )
