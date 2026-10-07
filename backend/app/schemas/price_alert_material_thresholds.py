from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EffectiveThresholdsResponse(BaseModel):
    light_from_percent: Decimal
    medium_from_percent: Decimal
    large_over_percent: Decimal
    anomaly_percent: Decimal


class MaterialThresholdOverrideResponse(BaseModel):
    light_from_percent: Decimal
    medium_from_percent: Decimal
    large_over_percent: Decimal
    anomaly_percent: Decimal | None = None


class MaterialFreshnessConfigResponse(BaseModel):
    is_watched: bool
    expected_interval_days: int


class MaterialThresholdItemResponse(BaseModel):
    material_id: UUID
    code: str
    name: str
    override: MaterialThresholdOverrideResponse | None = None
    effective: EffectiveThresholdsResponse
    # None nghĩa là vật tư chưa có cấu hình theo dõi độ mới của giá.
    freshness: MaterialFreshnessConfigResponse | None = None


class MaterialThresholdListResponse(BaseModel):
    items: list[MaterialThresholdItemResponse]
    total: int


class MaterialThresholdUpdateRequest(BaseModel):
    light_from_percent: Decimal = Field(gt=0, le=100, max_digits=5, decimal_places=2)
    medium_from_percent: Decimal = Field(gt=0, le=100, max_digits=5, decimal_places=2)
    large_over_percent: Decimal = Field(gt=0, le=100, max_digits=5, decimal_places=2)
    # None nghĩa là dùng ngưỡng giá bất thường mặc định trong cấu hình chung.
    anomaly_percent: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=5,
        decimal_places=2,
    )


class MaterialThresholdResponse(BaseModel):
    material_id: UUID
    override: MaterialThresholdOverrideResponse | None = None
    effective: EffectiveThresholdsResponse


class MaterialFreshnessUpdateRequest(BaseModel):
    model_config = ConfigDict(strict=True)

    is_watched: bool
    expected_interval_days: int = Field(ge=1, le=365)


class MaterialFreshnessResponse(BaseModel):
    material_id: UUID
    freshness: MaterialFreshnessConfigResponse
