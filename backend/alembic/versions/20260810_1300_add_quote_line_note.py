"""add note column to quote_lines

Revision ID: 20260810_1300
Revises: 20260810_1100
Create Date: 2026-08-10 13:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260810_1300"
down_revision: str | None = "20260810_1100"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("quote_lines", sa.Column("note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("quote_lines", "note")
