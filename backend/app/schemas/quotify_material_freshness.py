from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

MaterialFreshnessStatus = Literal["updated", "on_time", "overdue", "never"]


class QuotifyMaterialFreshnessItem(BaseModel):
    material_id: UUID
    material_code: str
    material_name: str
    material_type_id: UUID
    material_type_name: str
    is_watched: bool
    expected_interval_days: int | None = None
    update_count: int
    supplier_count: int
    last_received_date: date | None = None
    age_days: int | None = None
    status: MaterialFreshnessStatus
    last_enterer_id: UUID | None = None
    last_enterer_label: str | None = None


class QuotifyMaterialFreshnessSummary(BaseModel):
    # Chỉ tính trên vật tư đang theo dõi: watched = updated + on_time + overdue (overdue gồm
    # cả vật tư chưa từng có giá).
    watched_count: int
    updated_count: int
    on_time_count: int
    overdue_count: int
    # Vật tư không theo dõi nhưng có cập nhật trong tuần (nằm ngoài bốn số trên).
    unwatched_updated_count: int


class QuotifyMaterialFreshnessResponse(BaseModel):
    week_start: date
    week_end: date
    as_of_date: date
    summary: QuotifyMaterialFreshnessSummary
    items: list[QuotifyMaterialFreshnessItem]
