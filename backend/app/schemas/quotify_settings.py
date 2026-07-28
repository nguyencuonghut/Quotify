from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class QuotifySettingsResponse(BaseModel):
    id: UUID
    conversion_cost_vnd_per_kg: Decimal
    updated_by_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class ConversionCostUpdateRequest(BaseModel):
    conversion_cost_vnd_per_kg: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
