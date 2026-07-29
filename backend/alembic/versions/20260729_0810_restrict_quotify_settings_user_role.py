"""restrict quotify settings from baseline user role

Revision ID: 20260729_0810
Revises: 20260729_0800
Create Date: 2026-07-29 08:10:00
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260729_0810"
down_revision: str | None = "20260729_0800"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM role_permissions
        USING roles, permissions
        WHERE role_permissions.role_id = roles.id
          AND role_permissions.permission_id = permissions.id
          AND roles.name = 'user'
          AND permissions.code IN ('quotify_settings.read', 'quotify_settings.update')
        """,
    )


def downgrade() -> None:
    pass
