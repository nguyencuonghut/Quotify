"""Thêm index truy vấn cho audit logs

Revision ID: 20260724_0930
Revises: 20260611_0700
Create Date: 2026-07-24 09:30:00
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260724_0930"
down_revision: str | None = "20260611_0700"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at_id
        ON audit_logs (created_at DESC, id DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_audit_logs_actor_created_at_id
        ON audit_logs (actor_user_id, created_at DESC, id DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_audit_logs_entity_created_at_id
        ON audit_logs (entity_type, entity_id, created_at DESC, id DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_audit_logs_request_id
        ON audit_logs (request_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_audit_logs_action_created_at_id
        ON audit_logs (action, created_at DESC, id DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_audit_logs_action_created_at_id")
    op.execute("DROP INDEX IF EXISTS ix_audit_logs_request_id")
    op.execute("DROP INDEX IF EXISTS ix_audit_logs_entity_created_at_id")
    op.execute("DROP INDEX IF EXISTS ix_audit_logs_actor_created_at_id")
    op.execute("DROP INDEX IF EXISTS ix_audit_logs_created_at_id")
