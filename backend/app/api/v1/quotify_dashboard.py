from __future__ import annotations

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_permission
from app.db.session import get_db_session
from app.models import User
from app.schemas.quotify_dashboard import (
    QuotifyEntryKpisResponse,
    QuotifyPriceTrendsResponse,
    QuotifyWeeklyEntryActivityResponse,
)
from app.schemas.quotify_material_freshness import QuotifyMaterialFreshnessResponse
from app.services.quotify_dashboard_service import QuotifyDashboardService
from app.services.quotify_material_freshness_service import QuotifyMaterialFreshnessService

router = APIRouter(prefix="/dashboard/quotify", tags=["dashboard", "quotify"])


def get_quotify_dashboard_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> QuotifyDashboardService:
    return QuotifyDashboardService(session)


def get_quotify_material_freshness_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> QuotifyMaterialFreshnessService:
    return QuotifyMaterialFreshnessService(session)


@router.get("/entry-kpis", response_model=QuotifyEntryKpisResponse)
async def get_entry_kpis(
    service: Annotated[QuotifyDashboardService, Depends(get_quotify_dashboard_service)],
    _: Annotated[User, Depends(require_permission("dashboard.read"))],
    material_id: UUID | None = None,
    delivery_month: date | None = None,
    received_date_start: date | None = None,
    received_date_end: date | None = None,
    supplier_type: Literal["domestic", "international"] | None = None,
) -> QuotifyEntryKpisResponse:
    data = await service.get_entry_kpis(
        material_id=material_id,
        delivery_month=delivery_month,
        received_date_start=received_date_start,
        received_date_end=received_date_end,
        supplier_type=supplier_type,
    )
    return QuotifyEntryKpisResponse.model_validate(data)


@router.get("/price-trends", response_model=QuotifyPriceTrendsResponse)
async def get_price_trends(
    service: Annotated[QuotifyDashboardService, Depends(get_quotify_dashboard_service)],
    _: Annotated[User, Depends(require_permission("dashboard.read"))],
    material_id: UUID | None = None,
    delivery_month: date | None = None,
    received_date_start: date | None = None,
    received_date_end: date | None = None,
    supplier_type: Literal["domestic", "international"] | None = None,
) -> QuotifyPriceTrendsResponse:
    data = await service.get_price_trends(
        material_id=material_id,
        delivery_month=delivery_month,
        received_date_start=received_date_start,
        received_date_end=received_date_end,
        supplier_type=supplier_type,
    )
    return QuotifyPriceTrendsResponse.model_validate(data)


@router.get("/weekly-entry-activity", response_model=QuotifyWeeklyEntryActivityResponse)
async def get_weekly_entry_activity(
    service: Annotated[QuotifyDashboardService, Depends(get_quotify_dashboard_service)],
    _: Annotated[User, Depends(require_permission("dashboard.read"))],
    week_start: date | None = None,
    user_id: UUID | None = None,
) -> QuotifyWeeklyEntryActivityResponse:
    data = await service.get_weekly_entry_activity(
        week_start=week_start,
        user_id=user_id,
    )
    return QuotifyWeeklyEntryActivityResponse.model_validate(data)


@router.get("/material-freshness", response_model=QuotifyMaterialFreshnessResponse)
async def get_material_freshness(
    service: Annotated[
        QuotifyMaterialFreshnessService,
        Depends(get_quotify_material_freshness_service),
    ],
    # Mọi người xem được Dashboard đều xem được bảng này, như các bảng khác của Dashboard. Việc
    # sửa danh sách theo dõi vẫn cần `price_alerts.manage` (trang cấu hình thông báo giá).
    _: Annotated[User, Depends(require_permission("dashboard.read"))],
    # Giới hạn khoảng ngày để ngày gần biên (vd. 9999-12-31) không làm tràn khi cộng 6 ngày.
    week_start: Annotated[date | None, Query(ge=date(2000, 1, 1), le=date(2100, 12, 31))] = None,
) -> QuotifyMaterialFreshnessResponse:
    data = await service.get_material_freshness(week_start=week_start)
    return QuotifyMaterialFreshnessResponse.model_validate(data)
