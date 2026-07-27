"""Authentication package scaffold."""

from app.auth.dependencies import get_current_user, oauth2_scheme
from app.auth.hashing import hash_password, needs_rehash, verify_password
from app.auth.jwt import AccessTokenPayload, AuthTokenError, decode_access_token, issue_access_token
from app.auth.permissions import (
    SYSTEM_ADMIN_ROLE_NAME,
    describe_permissions,
    has_any_role,
    has_permission,
    has_role,
    resolve_permission_codes,
    resolve_role_names,
)
from app.auth.service import (
    AccessTokenResult,
    AuthService,
    AuthSessionBundle,
    InactiveUserError,
    InvalidCredentialsError,
    RefreshTokenError,
    create_access_token_result,
)

__all__ = [
    "AccessTokenPayload",
    "AccessTokenResult",
    "AuthService",
    "AuthSessionBundle",
    "AuthTokenError",
    "SYSTEM_ADMIN_ROLE_NAME",
    "InactiveUserError",
    "InvalidCredentialsError",
    "RefreshTokenError",
    "create_access_token_result",
    "decode_access_token",
    "describe_permissions",
    "get_current_user",
    "has_any_role",
    "has_permission",
    "has_role",
    "hash_password",
    "issue_access_token",
    "needs_rehash",
    "oauth2_scheme",
    "resolve_permission_codes",
    "resolve_role_names",
    "verify_password",
]
