from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class QuoteLineCreateRequest(BaseModel):
    material_id: UUID
    price_original: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(min_length=1, max_length=10)
    unit: str = Field(min_length=1, max_length=10)
    delivery_month: date
    exchange_rate: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    exchange_rate_manual_reason: str | None = Field(default=None, max_length=255)


class QuoteCreateRequest(BaseModel):
    supplier_id: UUID
    received_date: date
    is_backfilled: bool = False
    backfill_reason: str | None = Field(default=None, max_length=500)
    lines: list[QuoteLineCreateRequest] = Field(min_length=1)


class QuoteDraftUpdateRequest(BaseModel):
    received_date: date
    is_backfilled: bool = False
    backfill_reason: str | None = Field(default=None, max_length=500)
    correction_reason: str | None = Field(default=None, max_length=500)
    lines: list[QuoteLineCreateRequest] = Field(min_length=1)


class QuoteLineResponse(BaseModel):
    id: UUID
    material_id: UUID
    material_code: str
    material_name: str
    price_original: Decimal
    currency: str
    unit: str
    delivery_month: date
    line_order: int
    exchange_rate: Decimal | None = None
    exchange_rate_source: str | None = None
    exchange_rate_source_mode: str | None = None
    exchange_rate_entered_at: datetime | None = None
    exchange_rate_manual_reason: str | None = None
    exchange_rate_actor_id: UUID | None = None
    import_tax_rate_percent: Decimal | None = None
    processing_cost_vnd_per_kg: Decimal | None = None
    price_converted_vnd_per_kg: Decimal
    purchase_marked_at: datetime | None = None
    purchase_marked_by_id: UUID | None = None

    class Config:
        from_attributes = True


class QuoteVersionResponse(BaseModel):
    id: UUID
    quote_id: UUID
    version_number: int
    received_date: date
    status: str
    file_id: UUID | None = None
    is_backfilled: bool
    backfill_reason: str | None = None
    correction_reason: str | None = None
    created_by_id: UUID | None = None
    confirmed_at: datetime | None = None
    confirmed_by_id: UUID | None = None
    superseded_at: datetime | None = None
    superseded_by_id: UUID | None = None
    superseded_by_version_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
    lines: list[QuoteLineResponse]

    class Config:
        from_attributes = True


class QuoteResponse(BaseModel):
    id: UUID
    supplier_id: UUID
    supplier_name: str
    supplier_code: str
    created_by_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
    versions: list[QuoteVersionResponse]

    class Config:
        from_attributes = True


class QuoteLinePurchaseToggleRequest(BaseModel):
    purchase: bool
    purchase_date: datetime | None = None
