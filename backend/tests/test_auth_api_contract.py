from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.api.v1.auth import _build_access_token_response, _build_current_user_response
from app.auth.hashing import hash_password
from app.models import Permission, Role, User, UserStatus


def test_build_access_token_response_computes_positive_expiry() -> None:
    expires_at = datetime.now(UTC) + timedelta(minutes=15)

    payload = _build_access_token_response("token-value", expires_at)

    assert payload.access_token == "token-value"
    assert payload.token_type == "bearer"
    assert 1 <= payload.expires_in <= 900


def test_build_current_user_response_includes_roles_and_permissions() -> None:
    permission = Permission(id=uuid4(), code="users.read")
    role = Role(id=uuid4(), name="manager")
    role.permissions = [permission]
    user = User(
        id=uuid4(),
        email="manager@example.com",
        password_hash=hash_password("Secret123!"),
        status=UserStatus.ACTIVE,
        full_name="Manager User",
    )
    user.roles = [role]

    payload = _build_current_user_response(user)

    assert payload.email == "manager@example.com"
    assert payload.status == "active"
    assert payload.roles == ["manager"]
    assert payload.permissions == ["users.read"]
