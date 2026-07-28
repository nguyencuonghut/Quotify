from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_permission
from app.db.session import get_db_session
from app.models import QuotifySetting, User
from app.schemas import ConversionCostUpdateRequest, QuotifySettingsResponse
from app.services import AuditLogContext, AuditLogService, QuotifySettingsService

router = APIRouter(prefix="/quotify-settings", tags=["quotify-settings"])


def get_quotify_settings_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> QuotifySettingsService:
    return QuotifySettingsService(session)


def get_audit_log_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuditLogService:
    return AuditLogService(session)


def _build_settings_response(setting: QuotifySetting) -> QuotifySettingsResponse:
    return QuotifySettingsResponse(
        id=setting.id,
        conversion_cost_vnd_per_kg=setting.conversion_cost_vnd_per_kg,
        updated_by_id=setting.updated_by_id,
        created_at=setting.created_at,
        updated_at=setting.updated_at,
    )


def _conversion_cost_change_metadata(
    *,
    old_value: Decimal,
    new_value: Decimal,
) -> dict[str, object]:
    return {
        "conversion_cost_vnd_per_kg": str(new_value),
        "changes": [
            {
                "field": "conversion_cost_vnd_per_kg",
                "label": "Chi phí quy đổi VNĐ/KG",
                "old_value": str(old_value),
                "new_value": str(new_value),
            },
        ],
    }


@router.get("", response_model=QuotifySettingsResponse)
async def get_quotify_settings(
    current_user: Annotated[User, Depends(require_permission("quotify_settings.read"))],
    settings_service: Annotated[
        QuotifySettingsService,
        Depends(get_quotify_settings_service),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> QuotifySettingsResponse:
    setting = await settings_service.get_or_create_settings()
    await session.commit()
    return _build_settings_response(setting)


@router.put("/conversion-cost", response_model=QuotifySettingsResponse)
async def update_conversion_cost(
    request: Request,
    payload: ConversionCostUpdateRequest,
    current_user: Annotated[User, Depends(require_permission("quotify_settings.update"))],
    settings_service: Annotated[
        QuotifySettingsService,
        Depends(get_quotify_settings_service),
    ],
    audit_log_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> QuotifySettingsResponse:
    old_setting = await settings_service.get_or_create_settings()
    old_value = old_setting.conversion_cost_vnd_per_kg
    try:
        setting = await settings_service.update_conversion_cost(
            conversion_cost_vnd_per_kg=payload.conversion_cost_vnd_per_kg,
            updated_by_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    await audit_log_service.log_event(
        action="quotify_settings.conversion_cost_updated",
        entity_type="quotify_setting",
        context=AuditLogContext.from_request(
            request=request,
            current_user=current_user,
            entity_id=str(setting.id),
            metadata_json=_conversion_cost_change_metadata(
                old_value=old_value,
                new_value=setting.conversion_cost_vnd_per_kg,
            ),
        ),
    )
    await session.commit()
    return _build_settings_response(setting)


