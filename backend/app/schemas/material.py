from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

MaterialStatus = Literal["active", "inactive"]


class MaterialCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=150)
    material_type_id: UUID
    status: MaterialStatus = "active"
    note: str | None = Field(default=None, max_length=2000)


class MaterialUpdateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=150)
    material_type_id: UUID
    status: MaterialStatus
    note: str | None = Field(default=None, max_length=2000)


class MaterialResponse(BaseModel):
    id: UUID
    code: str
    name: str
    material_type_id: UUID
    material_type_code: str
    material_type_name: str
    status: MaterialStatus
    note: str | None = None
    created_at: datetime
    updated_at: datetime


class MaterialListResponse(BaseModel):
    items: list[MaterialResponse]
    total: int
