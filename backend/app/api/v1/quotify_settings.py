from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_permission
from app.db.session import get_db_session
from app.models import QuotifySetting, User
from app.schemas import QuotifySettingsResponse, QuotifySettingsUpdateRequest
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
        import_tax_rate_percent=setting.import_tax_rate_percent,
        processing_cost_vnd_per_kg=setting.processing_cost_vnd_per_kg,
        updated_by_id=setting.updated_by_id,
        created_at=setting.created_at,
        updated_at=setting.updated_at,
    )


def _settings_change_metadata(
    *,
    old_import_tax_rate_percent: Decimal,
    old_processing_cost_vnd_per_kg: Decimal,
    new_setting: QuotifySetting,
) -> dict[str, object]:
    changes: list[dict[str, str]] = []
    if old_import_tax_rate_percent != new_setting.import_tax_rate_percent:
        changes.append(
            {
                "field": "import_tax_rate_percent",
                "label": "Thuế nhập khẩu (%)",
                "old_value": str(old_import_tax_rate_percent),
                "new_value": str(new_setting.import_tax_rate_percent),
            },
        )
    if old_processing_cost_vnd_per_kg != new_setting.processing_cost_vnd_per_kg:
        changes.append(
            {
                "field": "processing_cost_vnd_per_kg",
                "label": "Chi phí làm hàng VNĐ/KG",
                "old_value": str(old_processing_cost_vnd_per_kg),
                "new_value": str(new_setting.processing_cost_vnd_per_kg),
            },
        )
    return {
        "import_tax_rate_percent": str(new_setting.import_tax_rate_percent),
        "processing_cost_vnd_per_kg": str(new_setting.processing_cost_vnd_per_kg),
        "changes": changes,
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
    await session.refresh(setting)
    return _build_settings_response(setting)


@router.put("", response_model=QuotifySettingsResponse)
async def update_quotify_settings(
    request: Request,
    payload: QuotifySettingsUpdateRequest,
    current_user: Annotated[User, Depends(require_permission("quotify_settings.update"))],
    settings_service: Annotated[
        QuotifySettingsService,
        Depends(get_quotify_settings_service),
    ],
    audit_log_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> QuotifySettingsResponse:
    old_setting = await settings_service.get_or_create_settings()
    old_import_tax_rate_percent = old_setting.import_tax_rate_percent
    old_processing_cost_vnd_per_kg = old_setting.processing_cost_vnd_per_kg
    try:
        setting = await settings_service.update_quotify_settings(
            import_tax_rate_percent=payload.import_tax_rate_percent,
            processing_cost_vnd_per_kg=payload.processing_cost_vnd_per_kg,
            updated_by_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    await audit_log_service.log_event(
        action="quotify_settings.updated",
        entity_type="quotify_setting",
        context=AuditLogContext.from_request(
            request=request,
            current_user=current_user,
            entity_id=str(setting.id),
            metadata_json=_settings_change_metadata(
                old_import_tax_rate_percent=old_import_tax_rate_percent,
                old_processing_cost_vnd_per_kg=old_processing_cost_vnd_per_kg,
                new_setting=setting,
            ),
        ),
    )
    await session.commit()
    await session.refresh(setting)
    return _build_settings_response(setting)


