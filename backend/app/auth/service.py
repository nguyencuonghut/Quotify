from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.hashing import verify_password
from app.auth.jwt import issue_access_token
from app.core.config import get_settings
from app.models import RefreshToken, Role, User, UserStatus


class InvalidCredentialsError(Exception):
    """Raised when authentication fails."""


class InactiveUserError(Exception):
    """Raised when a user cannot authenticate due to status."""


class RefreshTokenError(Exception):
    """Raised when refresh token operations fail."""


@dataclass(slots=True, frozen=True)
class AccessTokenResult:
    token: str
    expires_at: datetime


@dataclass(slots=True, frozen=True)
class AuthSessionBundle:
    access_token: str
    access_token_expires_at: datetime
    refresh_token: str
    refresh_token_expires_at: datetime
    user: User


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = get_settings()

    async def authenticate(self, *, email: str, password: str) -> AuthSessionBundle:
        user = await self._get_user_by_email(email)

        if user is None or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError("Invalid credentials.")

        self._ensure_user_can_authenticate(user)

        bundle = await self._issue_session_for_user(user)
        user.last_login_at = datetime.now(UTC)
        await self.session.flush()
        return bundle

    async def refresh_session(self, *, refresh_token: str) -> AuthSessionBundle:
        token_hash = _hash_refresh_token(refresh_token)
        refresh_token_record = await self._get_refresh_token_record(token_hash)

        if refresh_token_record is None:
            raise RefreshTokenError("Refresh token is invalid.")

        now = datetime.now(UTC)
        if refresh_token_record.revoked_at is not None:
            raise RefreshTokenError("Refresh token is revoked.")
        if refresh_token_record.expires_at <= now:
            raise RefreshTokenError("Refresh token expired.")

        user = refresh_token_record.user
        self._ensure_user_can_authenticate(user)

        refresh_token_record.revoked_at = now
        refresh_token_record.last_used_at = now

        bundle = await self._issue_session_for_user(user)
        await self.session.flush()
        return bundle

    async def revoke_refresh_token(self, *, refresh_token: str) -> User | None:
        token_hash = _hash_refresh_token(refresh_token)
        refresh_token_record = await self._get_refresh_token_record(token_hash)

        if refresh_token_record is None or refresh_token_record.revoked_at is not None:
            return None

        now = datetime.now(UTC)
        refresh_token_record.revoked_at = now
        refresh_token_record.last_used_at = now
        await self.session.flush()
        return refresh_token_record.user

    async def get_active_user(self, *, user_id: UUID) -> User | None:
        statement = (
            select(User)
            .options(selectinload(User.roles).selectinload(Role.permissions))
            .where(User.id == user_id)
        )
        result = await self.session.execute(statement)
        user = result.scalar_one_or_none()
        if user is None or user.status is not UserStatus.ACTIVE:
            return None
        return user

    async def _issue_session_for_user(self, user: User) -> AuthSessionBundle:
        now = datetime.now(UTC)
        access_token, access_token_expires_at = issue_access_token(user.id, now=now)

        refresh_token = token_urlsafe(48)
        refresh_token_expires_at = now + timedelta(days=self.settings.refresh_token_expire_days)
        refresh_token_record = RefreshToken(
            user_id=user.id,
            token_hash=_hash_refresh_token(refresh_token),
            expires_at=refresh_token_expires_at,
        )
        refresh_token_record.user = user
        self.session.add(refresh_token_record)
        await self.session.flush()

        return AuthSessionBundle(
            access_token=access_token,
            access_token_expires_at=access_token_expires_at,
            refresh_token=refresh_token,
            refresh_token_expires_at=refresh_token_expires_at,
            user=user,
        )

    async def _get_user_by_email(self, email: str) -> User | None:
        statement = (
            select(User)
            .options(selectinload(User.roles).selectinload(Role.permissions))
            .where(User.email == email)
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def _get_refresh_token_record(self, token_hash: str) -> RefreshToken | None:
        statement = (
            select(RefreshToken)
            .options(selectinload(RefreshToken.user))
            .where(RefreshToken.token_hash == token_hash)
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    @staticmethod
    def _ensure_user_can_authenticate(user: User) -> None:
        if user.status is not UserStatus.ACTIVE:
            raise InactiveUserError("User account is not active.")


def create_access_token_result(user_id: UUID) -> AccessTokenResult:
    token, expires_at = issue_access_token(user_id)
    return AccessTokenResult(token=token, expires_at=expires_at)


def _hash_refresh_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()
