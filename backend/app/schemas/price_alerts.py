from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class PriceAlertSettingsUpdateRequest(BaseModel):
    is_enabled: bool
    anomaly_enabled: bool
    reference_working_days: int = Field(ge=1, le=30)
    light_from_percent: Decimal = Field(gt=0, le=100, max_digits=5, decimal_places=2)
    medium_from_percent: Decimal = Field(gt=0, le=100, max_digits=5, decimal_places=2)
    large_over_percent: Decimal = Field(gt=0, le=100, max_digits=5, decimal_places=2)
    anomaly_percent: Decimal = Field(gt=0, max_digits=5, decimal_places=2)
    anomaly_lookback_days: int = Field(ge=1, le=365)
    max_trigger_delay_working_days: int = Field(ge=0, le=30)
    staff_lookback_days: int = Field(ge=1, le=365)
    dedupe_window_days: int = Field(ge=0, le=90)
    immediate_cap_per_scan: int = Field(ge=1, le=500)
    digest_hour_local: int = Field(ge=0, le=23)
    reference_fallback_days: int = Field(ge=0, le=365)


class PriceAlertSettingsResponse(BaseModel):
    is_enabled: bool
    anomaly_enabled: bool
    reference_working_days: int
    light_from_percent: Decimal
    medium_from_percent: Decimal
    large_over_percent: Decimal
    anomaly_percent: Decimal
    anomaly_lookback_days: int
    max_trigger_delay_working_days: int
    staff_lookback_days: int
    dedupe_window_days: int
    immediate_cap_per_scan: int
    digest_hour_local: int
    reference_fallback_days: int
    enabled_since: datetime | None = None
    updated_at: datetime
    updated_by_id: UUID | None = None
