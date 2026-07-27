from __future__ import annotations

from collections.abc import Iterable

from app.models import Role, User

SYSTEM_ADMIN_ROLE_NAME = "admin"


def resolve_role_names(user: User) -> set[str]:
    return {role.name for role in user.roles}


def resolve_permission_codes(user: User) -> set[str]:
    codes: set[str] = set()
    for role in user.roles:
        codes.update(_role_permission_codes(role))
    return codes


def has_role(user: User, role_name: str) -> bool:
    return role_name in resolve_role_names(user)


def has_any_role(user: User, role_names: Iterable[str]) -> bool:
    current_role_names = resolve_role_names(user)
    return any(role_name in current_role_names for role_name in role_names)


def has_permission(user: User, permission_code: str) -> bool:
    if has_role(user, SYSTEM_ADMIN_ROLE_NAME):
        return True
    return permission_code in resolve_permission_codes(user)


def _role_permission_codes(role: Role) -> set[str]:
    return {permission.code for permission in role.permissions}


def describe_permissions(user: User) -> dict[str, set[str]]:
    return {
        "roles": resolve_role_names(user),
        "permissions": resolve_permission_codes(user),
    }
