"""create quote notes and revisions

Revision ID: 20260728_1100
Revises: 20260728_1000
Create Date: 2026-07-28 11:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260728_1100"
down_revision: str | None = "20260728_1000"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create quote_notes table
    op.create_table(
        "quote_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quote_id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.ForeignKeyConstraint(["quote_id"], ["quotes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_quote_notes_quote_id"), "quote_notes", ["quote_id"], unique=True)

    # 2. Create quote_note_revisions table
    op.create_table(
        "quote_note_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("note_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["note_id"], ["quote_notes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_quote_note_revisions_author_id"),
        "quote_note_revisions",
        ["author_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_quote_note_revisions_note_id"),
        "quote_note_revisions",
        ["note_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_quote_note_revisions_note_id"), table_name="quote_note_revisions")
    op.drop_index(op.f("ix_quote_note_revisions_author_id"), table_name="quote_note_revisions")
    op.drop_table("quote_note_revisions")

    op.drop_index(op.f("ix_quote_notes_quote_id"), table_name="quote_notes")
    op.drop_table("quote_notes")
