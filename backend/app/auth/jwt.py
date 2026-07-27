from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from app.core.config import get_settings


class AuthTokenError(Exception):
    """Raised when a JWT is invalid, expired, or uses the wrong claim set."""


@dataclass(slots=True, frozen=True)
class AccessTokenPayload:
    sub: UUID
    exp: datetime
    iat: datetime
    token_type: str


def issue_access_token(user_id: UUID, *, now: datetime | None = None) -> tuple[str, datetime]:
    settings = get_settings()
    issued_at = (now or datetime.now(UTC)).replace(microsecond=0)
    expires_at = issued_at + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": issued_at,
        "exp": expires_at,
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")
    return token, expires_at


def decode_access_token(token: str) -> AccessTokenPayload:
    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=["HS256"],
            options={"require": ["exp", "iat", "sub", "type"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthTokenError("Access token expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthTokenError("Access token is invalid.") from exc

    if payload["type"] != "access":
        raise AuthTokenError("Access token type is invalid.")

    return AccessTokenPayload(
        sub=UUID(payload["sub"]),
        exp=_coerce_timestamp(payload["exp"]),
        iat=_coerce_timestamp(payload["iat"]),
        token_type=payload["type"],
    )


def _coerce_timestamp(value: int | float | datetime) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    return datetime.fromtimestamp(value, tz=UTC)
