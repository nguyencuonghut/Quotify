from app.db.base import Base


def test_auth_rbac_tables_registered_in_metadata() -> None:
    expected_tables = {
        "audit_logs",
        "permissions",
        "refresh_tokens",
        "role_permissions",
        "roles",
        "user_roles",
        "users",
    }

    assert expected_tables.issubset(Base.metadata.tables.keys())
