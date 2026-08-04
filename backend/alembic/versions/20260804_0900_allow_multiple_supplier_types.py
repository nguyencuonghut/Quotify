"""Allow suppliers to have multiple supplier types."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260804_0900"
down_revision: str | None = "20260730_0200"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_suppliers_supplier_type", "suppliers", type_="check")
    op.create_check_constraint(
        "ck_suppliers_supplier_type",
        "suppliers",
        "supplier_type in ('domestic', 'international', 'domestic,international')",
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "update suppliers set supplier_type = 'domestic' "
            "where supplier_type = 'domestic,international'",
        ),
    )
    op.drop_constraint("ck_suppliers_supplier_type", "suppliers", type_="check")
    op.create_check_constraint(
        "ck_suppliers_supplier_type",
        "suppliers",
        "supplier_type in ('domestic', 'international')",
    )
