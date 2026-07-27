from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RoleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    permissions: list[str] = Field(default_factory=list)


class RoleUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    permissions: list[str] = Field(default_factory=list)


class RoleResponse(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    is_system: bool
    permissions: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class RoleListResponse(BaseModel):
    items: list[RoleResponse]
    total: int
