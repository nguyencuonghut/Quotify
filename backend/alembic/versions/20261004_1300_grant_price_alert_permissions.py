"""grant price alert permissions to manager and admin roles

Revision ID: 20261004_1300
Revises: 20261004_1200
Create Date: 2026-10-04 13:00:00
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20261004_1300"
down_revision: str | None = "20261004_1200"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # `seed_auth_rbac.py` không tạo role `manager` và chỉ chạy lúc khởi động container, nên
    # migration tự tạo quyền rồi gán cho role đã có. Thiếu role nào thì bỏ qua role đó.
    op.execute(
        """
        INSERT INTO permissions (id, code, description)
        VALUES
            (gen_random_uuid(), 'price_alerts.receive_all',
             'Nhận thông báo biến động giá của mọi vật tư'),
            (gen_random_uuid(), 'price_alerts.manage',
             'Xem và cấu hình thông báo biến động giá')
        ON CONFLICT (code) DO NOTHING
        """,
    )
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT roles.id, permissions.id
        FROM roles
        CROSS JOIN permissions
        WHERE roles.name IN ('manager', 'admin')
          AND permissions.code IN ('price_alerts.receive_all', 'price_alerts.manage')
        ON CONFLICT DO NOTHING
        """,
    )


def downgrade() -> None:
    # Xóa quyền kéo theo các dòng `role_permissions` (ON DELETE CASCADE).
    op.execute(
        """
        DELETE FROM permissions
        WHERE code IN ('price_alerts.receive_all', 'price_alerts.manage')
        """,
    )
