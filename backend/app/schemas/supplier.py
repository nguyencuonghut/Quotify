from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

CatalogStatus = Literal["active", "inactive"]
SupplierType = Literal["domestic", "international"]


class SupplierContactRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    title: str | None = Field(default=None, max_length=150)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    status: CatalogStatus = "active"


class SupplierCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    supplier_type: SupplierType
    status: CatalogStatus = "active"
    tax_code: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=2000)
    note: str | None = Field(default=None, max_length=2000)
    contacts: list[SupplierContactRequest] = Field(default_factory=list)
    material_ids: list[UUID] = Field(default_factory=list)


class SupplierUpdateRequest(SupplierCreateRequest):
    pass


class SupplierContactResponse(BaseModel):
    id: UUID
    name: str
    title: str | None
    email: str | None
    phone: str | None
    status: CatalogStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SupplierMaterialResponse(BaseModel):
    material_id: UUID
    material_code: str
    material_name: str


class SupplierResponse(BaseModel):
    id: UUID
    code: str
    name: str
    supplier_type: SupplierType
    status: CatalogStatus
    tax_code: str | None
    address: str | None
    note: str | None
    contacts: list[SupplierContactResponse]
    materials: list[SupplierMaterialResponse]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SupplierListResponse(BaseModel):
    items: list[SupplierResponse]
    total: int


class SupplierLookupResponse(BaseModel):
    items: list[SupplierResponse]
