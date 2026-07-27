from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

import jwt
import pytest

from app.auth.hashing import hash_password, verify_password
from app.auth.jwt import AuthTokenError, decode_access_token, issue_access_token
from app.auth.service import AuthService, InvalidCredentialsError, RefreshTokenError
from app.core.config import get_settings
from app.models import RefreshToken, User, UserStatus


class FakeScalarResult:
    def __init__(self, value: object | None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object | None:
        return self._value


class FakeAsyncSession:
    def __init__(
        self,
        *,
        user_by_email: dict[str, User] | None = None,
        refresh_by_hash: dict[str, RefreshToken] | None = None,
        user_by_id: dict[object, User] | None = None,
    ) -> None:
        self.user_by_email = user_by_email or {}
        self.refresh_by_hash = refresh_by_hash or {}
        self.user_by_id = user_by_id or {}
        self.added: list[object] = []
        self.flush_count = 0

    async def execute(self, statement: object) -> FakeScalarResult:
        compiled = str(statement)
        params = statement.compile().params  # type: ignore[attr-defined]

        if "id_1" in params and "FROM users" in compiled:
            return FakeScalarResult(self.user_by_id.get(params["id_1"]))

        if "email_1" in params and "FROM users" in compiled:
            return FakeScalarResult(self.user_by_email.get(params["email_1"]))

        if "FROM refresh_tokens" in compiled and "refresh_tokens.token_hash" in compiled:
            return FakeScalarResult(self.refresh_by_hash.get(params["token_hash_1"]))

        raise AssertionError(f"Unexpected statement: {compiled}")

    async def get(self, model: type[User], key: object) -> User | None:
        assert model is User
        return self.user_by_id.get(key)

    def add(self, instance: object) -> None:
        self.added.append(instance)

    async def flush(self) -> None:
        self.flush_count += 1


def build_user(*, email: str = "admin@example.com", status: UserStatus = UserStatus.ACTIVE) -> User:
    return User(
        id=uuid4(),
        email=email,
        password_hash=hash_password("Secret123!"),
        status=status,
    )


def test_hash_and_verify_password() -> None:
    password_hash = hash_password("Secret123!")

    assert verify_password("Secret123!", password_hash) is True
    assert verify_password("wrong-password", password_hash) is False


def test_issue_and_decode_access_token() -> None:
    user_id = uuid4()

    token, expires_at = issue_access_token(user_id)
    payload = decode_access_token(token)

    assert payload.sub == user_id
    assert payload.token_type == "access"
    assert payload.exp == expires_at


def test_decode_access_token_rejects_wrong_type() -> None:
    settings = get_settings()
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": str(uuid4()),
            "type": "refresh",
            "iat": now,
            "exp": now,
        },
        settings.jwt_secret_key,
        algorithm="HS256",
    )

    with pytest.raises(AuthTokenError):
        decode_access_token(token)


@pytest.mark.asyncio
async def test_authenticate_issues_access_and_refresh_tokens() -> None:
    user = build_user()
    session = FakeAsyncSession(user_by_email={user.email: user})
    service = AuthService(session)  # type: ignore[arg-type]

    bundle = await service.authenticate(email=user.email, password="Secret123!")

    assert bundle.user is user
    assert bundle.access_token
    assert bundle.refresh_token
    assert bundle.access_token_expires_at.tzinfo is UTC
    assert bundle.refresh_token_expires_at.tzinfo is UTC
    assert len(session.added) == 1
    assert isinstance(session.added[0], RefreshToken)


@pytest.mark.asyncio
async def test_authenticate_rejects_invalid_credentials() -> None:
    user = build_user()
    session = FakeAsyncSession(user_by_email={user.email: user})
    service = AuthService(session)  # type: ignore[arg-type]

    with pytest.raises(InvalidCredentialsError):
        await service.authenticate(email=user.email, password="wrong-password")


@pytest.mark.asyncio
async def test_refresh_session_revokes_old_token_and_issues_new_one() -> None:
    user = build_user()
    session = FakeAsyncSession(user_by_email={user.email: user})
    service = AuthService(session)  # type: ignore[arg-type]
    login_bundle = await service.authenticate(email=user.email, password="Secret123!")
    stored_token = session.added[0]
    assert isinstance(stored_token, RefreshToken)
    session.refresh_by_hash[stored_token.token_hash] = stored_token

    refreshed_bundle = await service.refresh_session(refresh_token=login_bundle.refresh_token)

    assert stored_token.revoked_at is not None
    assert refreshed_bundle.refresh_token != login_bundle.refresh_token


@pytest.mark.asyncio
async def test_refresh_session_rejects_revoked_token() -> None:
    user = build_user()
    raw_token = "revoked-refresh-token"
    token_hash = sha256(raw_token.encode("utf-8")).hexdigest()
    revoked_token = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime(2099, 1, 1, tzinfo=UTC),
        revoked_at=datetime.now(UTC),
    )
    revoked_token.user = user

    session = FakeAsyncSession(refresh_by_hash={token_hash: revoked_token})
    service = AuthService(session)  # type: ignore[arg-type]

    with pytest.raises(RefreshTokenError):
        await service.refresh_session(refresh_token=raw_token)


@pytest.mark.asyncio
async def test_revoke_refresh_token_returns_user_when_revoked() -> None:
    user = build_user()
    raw_token = "refresh-token-to-revoke"
    token_hash = sha256(raw_token.encode("utf-8")).hexdigest()
    token_record = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime(2099, 1, 1, tzinfo=UTC),
    )
    token_record.user = user

    session = FakeAsyncSession(refresh_by_hash={token_hash: token_record})
    service = AuthService(session)  # type: ignore[arg-type]

    revoked_user = await service.revoke_refresh_token(refresh_token=raw_token)

    assert revoked_user is user
    assert token_record.revoked_at is not None
    assert token_record.last_used_at is not None


@pytest.mark.asyncio
async def test_get_active_user_returns_none_for_inactive_status() -> None:
    inactive_user = build_user(status=UserStatus.INACTIVE)
    session = FakeAsyncSession(user_by_id={inactive_user.id: inactive_user})
    service = AuthService(session)  # type: ignore[arg-type]

    assert await service.get_active_user(user_id=inactive_user.id) is None
