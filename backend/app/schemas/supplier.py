from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

CatalogStatus = Literal["active", "inactive"]
SupplierType = Literal["domestic", "international"]
SUPPLIER_TYPE_VALUES: tuple[SupplierType, ...] = ("domestic", "international")


def normalize_supplier_types(values: Sequence[str]) -> str:
    normalized: list[SupplierType] = []
    for value in values:
        candidate = value.strip().lower()
        if candidate not in SUPPLIER_TYPE_VALUES:
            raise ValueError("Loại NCC chỉ nhận domestic hoặc international.")
        supplier_type: SupplierType = candidate
        if supplier_type not in normalized:
            normalized.append(supplier_type)

    if not normalized:
        raise ValueError("Loại NCC là bắt buộc.")

    return ",".join(
        supplier_type for supplier_type in SUPPLIER_TYPE_VALUES if supplier_type in normalized
    )


def split_supplier_types(value: str) -> list[SupplierType]:
    return [
        supplier_type
        for supplier_type in SUPPLIER_TYPE_VALUES
        if supplier_type in {part.strip().lower() for part in value.split(",") if part.strip()}
    ]


class SupplierContactRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    title: str | None = Field(default=None, max_length=150)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    status: CatalogStatus = "active"


class SupplierCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    supplier_type: list[SupplierType] = Field(min_length=1, max_length=2)
    status: CatalogStatus = "active"
    tax_code: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=2000)
    note: str | None = Field(default=None, max_length=2000)
    contacts: list[SupplierContactRequest] = Field(default_factory=list)
    material_ids: list[UUID] = Field(default_factory=list)

    @field_validator("supplier_type", mode="before")
    @classmethod
    def normalize_supplier_type_payload(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value


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
    supplier_type: list[SupplierType]
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
