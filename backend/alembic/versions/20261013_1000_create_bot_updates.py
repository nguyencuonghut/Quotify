"""create bot_updates (chatbot pipeline, plan 5.1, S1)

Revision ID: 20261013_1000
Revises: 20261007_0900
Create Date: 2026-10-13 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20261013_1000"
down_revision: str | None = "20261007_0900"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # Chỉ thêm bảng mới (additive): code cũ chạy được trên schema này.
    op.create_table(
        "bot_updates",
        sa.Column("update_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=12), server_default="text", nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("payload_text", sa.Text(), nullable=True),
        sa.Column("reply_text", sa.Text(), nullable=True),
        sa.Column("sent_parts", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("attempts", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_category", sa.String(length=40), nullable=True),
        sa.Column("reply_saved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued','processing','replied','failed','dropped')",
            name="ck_bot_updates_status",
        ),
        sa.CheckConstraint("kind IN ('text')", name="ck_bot_updates_kind"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("update_id"),
    )
    op.create_index(
        "ix_bot_updates_chat_open",
        "bot_updates",
        ["chat_id", "update_id"],
        postgresql_where=sa.text("status IN ('queued','processing')"),
    )
    op.create_index("ix_bot_updates_status_received", "bot_updates", ["status", "received_at"])
    op.create_index("ix_bot_updates_user_received", "bot_updates", ["user_id", "received_at"])


def downgrade() -> None:
    op.drop_index("ix_bot_updates_user_received", table_name="bot_updates")
    op.drop_index("ix_bot_updates_status_received", table_name="bot_updates")
    op.drop_index("ix_bot_updates_chat_open", table_name="bot_updates")
    op.drop_table("bot_updates")
