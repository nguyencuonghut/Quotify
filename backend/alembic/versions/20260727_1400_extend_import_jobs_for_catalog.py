"""extend import jobs for catalog imports

Revision ID: 20260727_1400
Revises: 20260727_1300
Create Date: 2026-07-27 14:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260727_1400"
down_revision: str | None = "20260727_1300"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "import_jobs",
        sa.Column(
            "entity_type",
            sa.String(length=50),
            nullable=False,
            server_default="users",
        ),
    )
    op.add_column(
        "import_jobs",
        sa.Column(
            "task_name",
            sa.String(length=120),
            nullable=False,
            server_default="import_users_task",
        ),
    )
    op.create_index(
        op.f("ix_import_jobs_entity_type"),
        "import_jobs",
        ["entity_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_import_jobs_entity_type"), table_name="import_jobs")
    op.drop_column("import_jobs", "task_name")
    op.drop_column("import_jobs", "entity_type")
