"""Migration của thông báo biến động giá chạy từng bước trên database tạm (Slice 1)."""

from __future__ import annotations

import pytest
from migration_helpers import run_alembic, sql

pytestmark = pytest.mark.integration

BEFORE_ALERTS = "20261004_1100"
FOUNDATION = "20261004_1200"
PERMISSIONS = "20261004_1300"
ALERT_CODES = {"price_alerts.manage", "price_alerts.receive_all"}
ALERT_TABLES = (
    "price_alert_settings",
    "price_alert_scan_state",
    "price_alert_scan_runs",
    "price_alert_scanned_versions",
    "price_alert_material_thresholds",
    "user_alert_preferences",
)


def _create_roles(database_url: str, *names: str) -> None:
    for name in names:
        sql(
            database_url,
            "INSERT INTO roles (id, name, is_system) VALUES (gen_random_uuid(), :name, false)",
            name=name,
        )


def _grants(database_url: str) -> dict[str, set[str]]:
    rows = sql(
        database_url,
        """
        SELECT roles.name, permissions.code
        FROM role_permissions
        JOIN roles ON roles.id = role_permissions.role_id
        JOIN permissions ON permissions.id = role_permissions.permission_id
        WHERE permissions.code LIKE 'price_alerts.%'
        """,
    )
    grants: dict[str, set[str]] = {}
    for role_name, code in rows:
        grants.setdefault(role_name, set()).add(code)
    return grants


def _permission_codes(database_url: str) -> set[str]:
    return {
        code
        for (code,) in sql(
            database_url,
            "SELECT code FROM permissions WHERE code LIKE 'price_alerts.%'",
        )
    }


def _table_exists(database_url: str, table: str) -> bool:
    ((regclass,),) = sql(database_url, "SELECT to_regclass(:name)", name=f"public.{table}")
    return regclass is not None


def test_manager_and_admin_get_both_permissions_and_user_gets_none(
    empty_database_url: str,
) -> None:
    run_alembic(empty_database_url, "upgrade", BEFORE_ALERTS)
    _create_roles(empty_database_url, "manager", "admin", "user")

    run_alembic(empty_database_url, "upgrade", "head")

    assert _permission_codes(empty_database_url) == ALERT_CODES
    assert _grants(empty_database_url) == {"manager": ALERT_CODES, "admin": ALERT_CODES}


def test_missing_manager_role_is_skipped_without_error(empty_database_url: str) -> None:
    run_alembic(empty_database_url, "upgrade", BEFORE_ALERTS)
    _create_roles(empty_database_url, "admin", "user")

    run_alembic(empty_database_url, "upgrade", "head")

    assert _permission_codes(empty_database_url) == ALERT_CODES
    assert _grants(empty_database_url) == {"admin": ALERT_CODES}


def test_running_before_the_seed_creates_permissions_and_assigns_nothing(
    empty_database_url: str,
) -> None:
    run_alembic(empty_database_url, "upgrade", "head")

    assert _permission_codes(empty_database_url) == ALERT_CODES
    assert _grants(empty_database_url) == {}


def test_existing_permission_rows_are_reused_not_duplicated(empty_database_url: str) -> None:
    run_alembic(empty_database_url, "upgrade", BEFORE_ALERTS)
    _create_roles(empty_database_url, "manager")
    sql(
        empty_database_url,
        "INSERT INTO permissions (id, code) VALUES (gen_random_uuid(), 'price_alerts.manage')",
    )
    ((existing_id,),) = sql(
        empty_database_url,
        "SELECT id FROM permissions WHERE code = 'price_alerts.manage'",
    )

    run_alembic(empty_database_url, "upgrade", "head")

    ((same_id,),) = sql(
        empty_database_url,
        "SELECT id FROM permissions WHERE code = 'price_alerts.manage'",
    )
    assert same_id == existing_id
    assert _grants(empty_database_url) == {"manager": ALERT_CODES}


def test_rerunning_the_permission_migration_is_idempotent(empty_database_url: str) -> None:
    run_alembic(empty_database_url, "upgrade", BEFORE_ALERTS)
    _create_roles(empty_database_url, "manager", "admin")
    run_alembic(empty_database_url, "upgrade", "head")

    sql(empty_database_url, "UPDATE alembic_version SET version_num = :v", v=FOUNDATION)
    run_alembic(empty_database_url, "upgrade", PERMISSIONS)

    ((permission_rows,),) = sql(
        empty_database_url,
        "SELECT count(*) FROM permissions WHERE code LIKE 'price_alerts.%'",
    )
    ((grant_rows,),) = sql(
        empty_database_url,
        """
        SELECT count(*) FROM role_permissions
        JOIN permissions ON permissions.id = role_permissions.permission_id
        WHERE permissions.code LIKE 'price_alerts.%'
        """,
    )
    assert permission_rows == 2
    assert grant_rows == 4


def test_downgrade_removes_only_the_price_alert_permissions(empty_database_url: str) -> None:
    run_alembic(empty_database_url, "upgrade", BEFORE_ALERTS)
    _create_roles(empty_database_url, "manager")
    sql(
        empty_database_url,
        "INSERT INTO permissions (id, code) VALUES (gen_random_uuid(), 'quotes.read')",
    )
    sql(
        empty_database_url,
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT roles.id, permissions.id FROM roles, permissions
        WHERE roles.name = 'manager' AND permissions.code = 'quotes.read'
        """,
    )
    run_alembic(empty_database_url, "upgrade", "head")
    assert _grants(empty_database_url) == {"manager": ALERT_CODES}

    run_alembic(empty_database_url, "downgrade", FOUNDATION)

    assert _permission_codes(empty_database_url) == set()
    assert _grants(empty_database_url) == {}
    remaining = sql(
        empty_database_url,
        """
        SELECT permissions.code FROM role_permissions
        JOIN permissions ON permissions.id = role_permissions.permission_id
        """,
    )
    assert remaining == [("quotes.read",)]
    assert all(_table_exists(empty_database_url, table) for table in ALERT_TABLES)


def test_foundation_tables_downgrade_and_upgrade_again(empty_database_url: str) -> None:
    run_alembic(empty_database_url, "upgrade", "head")
    assert all(_table_exists(empty_database_url, table) for table in ALERT_TABLES)

    run_alembic(empty_database_url, "downgrade", BEFORE_ALERTS)

    assert not any(_table_exists(empty_database_url, table) for table in ALERT_TABLES)
    assert _permission_codes(empty_database_url) == set()

    run_alembic(empty_database_url, "upgrade", "head")

    assert all(_table_exists(empty_database_url, table) for table in ALERT_TABLES)
    assert sql(empty_database_url, "SELECT is_enabled FROM price_alert_settings") == [(False,)]
    assert sql(
        empty_database_url,
        "SELECT watermark_confirmed_at, last_run_at FROM price_alert_scan_state",
    ) == [(None, None)]
