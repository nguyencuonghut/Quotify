from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class QuoteFlattenedResponse(BaseModel):
    id: UUID
    quote_id: UUID
    quote_version_id: UUID
    supplier_id: UUID
    supplier_name: str
    supplier_code: str
    material_id: UUID
    material_name: str
    material_code: str
    material_type_name: str
    material_type_code: str
    received_date: date
    delivery_month: date
    price_original: Decimal
    currency: str
    unit: str
    exchange_rate: Decimal | None = None
    exchange_rate_source: str | None = None
    conversion_cost_vnd_per_kg: Decimal | None = None
    price_converted_vnd_per_kg: Decimal
    purchased: bool
    version_number: int
    version_status: str
    created_by_name: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class QuoteListResponse(BaseModel):
    items: list[QuoteFlattenedResponse]
    total: int
