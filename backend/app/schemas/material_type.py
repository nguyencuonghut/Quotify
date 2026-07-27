from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

MaterialStatus = Literal["active", "inactive"]


class MaterialTypeCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=150)
    status: MaterialStatus = "active"
    note: str | None = Field(default=None, max_length=2000)


class MaterialTypeUpdateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=150)
    status: MaterialStatus
    note: str | None = Field(default=None, max_length=2000)


class MaterialTypeResponse(BaseModel):
    id: UUID
    code: str
    name: str
    status: MaterialStatus
    note: str | None = None
    created_at: datetime
    updated_at: datetime


class MaterialTypeListResponse(BaseModel):
    items: list[MaterialTypeResponse]
    total: int
