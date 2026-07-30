from __future__ import annotations

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_permission
from app.db.session import get_db_session
from app.models import User
from app.schemas.quotify_dashboard import (
    QuotifyEntryKpisResponse,
    QuotifyPriceTrendsResponse,
    QuotifyWeeklyEntryActivityResponse,
)
from app.services.quotify_dashboard_service import QuotifyDashboardService

router = APIRouter(prefix="/dashboard/quotify", tags=["dashboard", "quotify"])


def get_quotify_dashboard_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> QuotifyDashboardService:
    return QuotifyDashboardService(session)


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
