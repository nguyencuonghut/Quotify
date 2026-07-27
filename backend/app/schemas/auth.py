from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class CurrentUserResponse(BaseModel):
    id: UUID
    email: str
    status: str
    roles: list[str]
    permissions: list[str]
    last_login_at: datetime | None
    full_name: str
    avatar_url: str | None = None
