from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class AnomalyItemResponse(BaseModel):
    id: UUID
    material_id: UUID
    material_name: str
    delivery_month: date
    received_date: date
    price_new: Decimal
    median: Decimal
    percent_change: Decimal
    reference_prices: list[Decimal]
    reference_point_count: int | None
    quote_id: UUID
    entered_by_name: str | None
    review_status: str
    attached_count: int
    age_working_days: int
    created_at: datetime
    reviewed_by_name: str | None
    reviewed_at: datetime | None


class AnomalyListResponse(BaseModel):
    items: list[AnomalyItemResponse]
    total: int


class AnomalyReviewRequest(BaseModel):
    decision: Literal["accepted", "rejected"]


class AnomalyReviewResponse(BaseModel):
    id: UUID
    review_status: str
    reviewed_by_name: str | None
    reviewed_at: datetime | None


class AnomalyConflictDetail(BaseModel):
    message: str
    review_status: str | None
    reviewed_by_name: str | None
    reviewed_at: datetime | None
