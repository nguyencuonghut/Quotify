from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_permission
from app.db.session import get_db_session
from app.models import User
from app.schemas.price_alert_material_thresholds import (
    EffectiveThresholdsResponse,
    MaterialThresholdItemResponse,
    MaterialThresholdListResponse,
    MaterialThresholdOverrideResponse,
    MaterialThresholdResponse,
    MaterialThresholdUpdateRequest,
)
from app.services import AuditLogContext, AuditLogService
from app.services.price_alert_material_threshold_service import (
    EffectiveThresholds,
    MaterialNotFoundError,
    MaterialThresholdView,
    PriceAlertMaterialThresholdService,
    ThresholdOverride,
)

router = APIRouter(
    prefix="/price-alert-settings/materials",
    tags=["price-alert-settings"],
)


def get_material_threshold_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PriceAlertMaterialThresholdService:
    return PriceAlertMaterialThresholdService(session)


def get_audit_log_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuditLogService:
    return AuditLogService(session)


def _build_override(
    override: ThresholdOverride | None,
) -> MaterialThresholdOverrideResponse | None:
    if override is None:
        return None
    return MaterialThresholdOverrideResponse(
        light_from_percent=override.light_from_percent,
        medium_from_percent=override.medium_from_percent,
        large_over_percent=override.large_over_percent,
        anomaly_percent=override.anomaly_percent,
    )


def _build_effective(effective: EffectiveThresholds) -> EffectiveThresholdsResponse:
    return EffectiveThresholdsResponse(
        light_from_percent=effective.light_from_percent,
        medium_from_percent=effective.medium_from_percent,
        large_over_percent=effective.large_over_percent,
        anomaly_percent=effective.anomaly_percent,
    )


def _build_item(view: MaterialThresholdView) -> MaterialThresholdItemResponse:
    return MaterialThresholdItemResponse(
        material_id=view.material_id,
        code=view.code,
        name=view.name,
        override=_build_override(view.override),
        effective=_build_effective(view.effective),
    )


@router.get("", response_model=MaterialThresholdListResponse)
async def list_material_thresholds(
    current_user: Annotated[User, Depends(require_permission("price_alerts.manage"))],
    service: Annotated[
        PriceAlertMaterialThresholdService,
        Depends(get_material_threshold_service),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    search: Annotated[str | None, Query(max_length=100)] = None,
) -> MaterialThresholdListResponse:
    page = await service.list_materials(limit=limit, offset=offset, search=search)
    # Lần đọc đầu có thể tạo dòng cấu hình mặc định nên phải commit.
    await session.commit()
    return MaterialThresholdListResponse(
        items=[_build_item(view) for view in page.items],
        total=page.total,
    )


@router.put("/{material_id}", response_model=MaterialThresholdResponse)
async def put_material_threshold(
    request: Request,
    material_id: UUID,
    payload: MaterialThresholdUpdateRequest,
    current_user: Annotated[User, Depends(require_permission("price_alerts.manage"))],
    service: Annotated[
        PriceAlertMaterialThresholdService,
        Depends(get_material_threshold_service),
    ],
    audit_log_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MaterialThresholdResponse:
    try:
        result = await service.set_override(
            material_id=material_id,
            light=payload.light_from_percent,
            medium=payload.medium_from_percent,
            large=payload.large_over_percent,
            anomaly=payload.anomaly_percent,
            updated_by_id=current_user.id,
        )
    except MaterialNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material not found",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    if result.changes:
        await audit_log_service.log_event(
            action="price_alerts.threshold_updated",
            entity_type="price_alert_material_threshold",
            context=AuditLogContext.from_request(
                request=request,
                current_user=current_user,
                entity_id=str(material_id),
                metadata_json={
                    "material_id": str(material_id),
                    "material_code": result.view.code,
                    "changes": result.changes,
                },
            ),
        )
    await session.commit()
    return MaterialThresholdResponse(
        material_id=result.view.material_id,
        override=_build_override(result.view.override),
        effective=_build_effective(result.view.effective),
    )


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material_threshold(
    request: Request,
    material_id: UUID,
    current_user: Annotated[User, Depends(require_permission("price_alerts.manage"))],
    service: Annotated[
        PriceAlertMaterialThresholdService,
        Depends(get_material_threshold_service),
    ],
    audit_log_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    changes = await service.clear_override(material_id=material_id)
    if changes:
        await audit_log_service.log_event(
            action="price_alerts.threshold_updated",
            entity_type="price_alert_material_threshold",
            context=AuditLogContext.from_request(
                request=request,
                current_user=current_user,
                entity_id=str(material_id),
                metadata_json={"material_id": str(material_id), "changes": changes},
            ),
        )
    await session.commit()
