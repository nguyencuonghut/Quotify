from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class QuotifyEntryUserKpi(BaseModel):
    user_id: UUID | None = None
    user_email: str | None = None
    user_full_name: str | None = None
    user_label: str
    quote_count: int


class QuotifyEntryKpisResponse(BaseModel):
    total_quote_count: int
    user_kpis: list[QuotifyEntryUserKpi]


class QuotifyPriceSummary(BaseModel):
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    avg_price: Decimal | None = None
    total_lines: int
    total_quotes: int
    purchased_lines: int


class QuotifyPriceTrendPoint(BaseModel):
    received_date: date
    delivery_month: date
    converted_price_vnd_per_kg: Decimal
    supplier_id: UUID
    supplier_name: str
    supplier_code: str
    supplier_type: str
    supplier_label: str
    material_id: UUID
    material_name: str
    material_code: str
    quote_id: UUID
    quote_version_id: UUID
    line_id: UUID
    purchased: bool
    purchase_marked_at: datetime | None = None
    confirmed_at: datetime


class QuotifyPurchaseContext(BaseModel):
    purchased_line_id: UUID
    quote_id: UUID
    material_id: UUID
    delivery_month: date
    purchase_marked_at: datetime
    at_purchase: QuotifyPriceSummary
    after_purchase: QuotifyPriceSummary


class QuotifyPriceTrendsResponse(BaseModel):
    summary: QuotifyPriceSummary
    points: list[QuotifyPriceTrendPoint]
    purchase_contexts: list[QuotifyPurchaseContext]
