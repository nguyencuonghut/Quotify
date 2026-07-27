from __future__ import annotations

from uuid import uuid4

from app.auth.permissions import (
    SYSTEM_ADMIN_ROLE_NAME,
    describe_permissions,
    has_any_role,
    has_permission,
    has_role,
    resolve_permission_codes,
    resolve_role_names,
)
from app.models import Permission, Role, User, UserStatus


def build_permission(code: str) -> Permission:
    return Permission(id=uuid4(), code=code)


def build_role(name: str, *permissions: Permission) -> Role:
    role = Role(id=uuid4(), name=name)
    role.permissions = list(permissions)
    return role


def build_user(*roles: Role) -> User:
    user = User(
        id=uuid4(),
        email="user@example.com",
        password_hash="hashed",
        status=UserStatus.ACTIVE,
    )
    user.roles = list(roles)
    return user


def test_permission_resolution_collects_codes_from_all_roles() -> None:
    users_read = build_permission("users.read")
    roles_read = build_permission("roles.read")
    manager = build_role("manager", users_read)
    auditor = build_role("auditor", roles_read)
    user = build_user(manager, auditor)

    assert resolve_permission_codes(user) == {"users.read", "roles.read"}
    assert resolve_role_names(user) == {"manager", "auditor"}


def test_admin_role_short_circuits_permission_checks() -> None:
    admin_role = build_role(SYSTEM_ADMIN_ROLE_NAME)
    user = build_user(admin_role)

    assert has_role(user, SYSTEM_ADMIN_ROLE_NAME) is True
    assert has_permission(user, "totally.missing.permission") is True


def test_non_admin_permission_check_respects_resolved_codes() -> None:
    dashboard_read = build_permission("dashboard.read")
    analyst_role = build_role("analyst", dashboard_read)
    user = build_user(analyst_role)

    assert has_permission(user, "dashboard.read") is True
    assert has_permission(user, "users.delete") is False
    assert has_any_role(user, {"analyst", "reviewer"}) is True


def test_describe_permissions_returns_roles_and_permissions() -> None:
    permission = build_permission("files.read")
    role = build_role("operator", permission)
    user = build_user(role)

    description = describe_permissions(user)

    assert description == {
        "roles": {"operator"},
        "permissions": {"files.read"},
    }
