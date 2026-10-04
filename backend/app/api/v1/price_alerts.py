from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_permission
from app.db.session import get_db_session
from app.models import PriceAlertScanState, PriceAlertSetting, User
from app.schemas.price_alerts import PriceAlertSettingsResponse, PriceAlertSettingsUpdateRequest
from app.services import AuditLogContext, AuditLogService
from app.services.price_alert_settings_service import (
    PriceAlertSettingsService,
    PriceAlertSettingsValues,
)

router = APIRouter(prefix="/price-alert-settings", tags=["price-alert-settings"])


def get_price_alert_settings_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PriceAlertSettingsService:
    return PriceAlertSettingsService(session)


def get_audit_log_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuditLogService:
    return AuditLogService(session)


def _build_settings_response(
    setting: PriceAlertSetting,
    scan_state: PriceAlertScanState,
) -> PriceAlertSettingsResponse:
    return PriceAlertSettingsResponse(
        is_enabled=setting.is_enabled,
        reference_working_days=setting.reference_working_days,
        light_from_percent=setting.light_from_percent,
        medium_from_percent=setting.medium_from_percent,
        large_over_percent=setting.large_over_percent,
        anomaly_percent=setting.anomaly_percent,
        anomaly_lookback_days=setting.anomaly_lookback_days,
        max_trigger_delay_working_days=setting.max_trigger_delay_working_days,
        staff_lookback_days=setting.staff_lookback_days,
        dedupe_window_days=setting.dedupe_window_days,
        immediate_cap_per_scan=setting.immediate_cap_per_scan,
        digest_hour_local=setting.digest_hour_local,
        enabled_since=scan_state.enabled_since,
        updated_at=setting.updated_at,
        updated_by_id=setting.updated_by_id,
    )


@router.get("", response_model=PriceAlertSettingsResponse)
async def get_price_alert_settings(
    current_user: Annotated[User, Depends(require_permission("price_alerts.manage"))],
    settings_service: Annotated[
        PriceAlertSettingsService,
        Depends(get_price_alert_settings_service),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PriceAlertSettingsResponse:
    setting = await settings_service.get_or_create_settings()
    scan_state = await settings_service.get_or_create_scan_state()
    await session.commit()
    await session.refresh(setting)
    await session.refresh(scan_state)
    return _build_settings_response(setting, scan_state)


@router.put("", response_model=PriceAlertSettingsResponse)
async def update_price_alert_settings(
    request: Request,
    payload: PriceAlertSettingsUpdateRequest,
    current_user: Annotated[User, Depends(require_permission("price_alerts.manage"))],
    settings_service: Annotated[
        PriceAlertSettingsService,
        Depends(get_price_alert_settings_service),
    ],
    audit_log_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PriceAlertSettingsResponse:
    try:
        result = await settings_service.update_settings(
            values=PriceAlertSettingsValues(**payload.model_dump()),
            updated_by_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    if result.changes:
        await audit_log_service.log_event(
            action="price_alerts.settings_updated",
            entity_type="price_alert_setting",
            context=AuditLogContext.from_request(
                request=request,
                current_user=current_user,
                entity_id=str(result.setting.id),
                metadata_json={"changes": result.changes},
            ),
        )
    await session.commit()
    await session.refresh(result.setting)
    await session.refresh(result.scan_state)
    return _build_settings_response(result.setting, result.scan_state)
