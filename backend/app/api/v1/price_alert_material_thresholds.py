from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_permission
from app.db.session import get_db_session
from app.models import User
from app.schemas.price_alert_material_thresholds import (
    EffectiveThresholdsResponse,
    MaterialFreshnessConfigResponse,
    MaterialFreshnessResponse,
    MaterialFreshnessUpdateRequest,
    MaterialThresholdItemResponse,
    MaterialThresholdListResponse,
    MaterialThresholdOverrideResponse,
    MaterialThresholdResponse,
    MaterialThresholdUpdateRequest,
)
from app.services import AuditLogContext, AuditLogService
from app.services.price_alert_material_threshold_service import (
    EffectiveThresholds,
    FreshnessConfig,
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


async def _material_metadata(
    service: PriceAlertMaterialThresholdService,
    material_id: UUID,
    changes: list[dict[str, str]],
) -> dict[str, object]:
    """Metadata audit của một vật tư: id, mã và tên (để nhật ký đọc được) cùng các thay đổi."""
    metadata: dict[str, object] = {"material_id": str(material_id)}
    labels = await service.material_labels(material_id)
    if labels is not None:
        metadata["material_code"], metadata["material_name"] = labels
    metadata["changes"] = changes
    return metadata


def _build_freshness(config: FreshnessConfig | None) -> MaterialFreshnessConfigResponse | None:
    if config is None:
        return None
    return MaterialFreshnessConfigResponse(
        is_watched=config.is_watched,
        expected_interval_days=config.expected_interval_days,
    )


def _build_item(view: MaterialThresholdView) -> MaterialThresholdItemResponse:
    return MaterialThresholdItemResponse(
        material_id=view.material_id,
        code=view.code,
        name=view.name,
        override=_build_override(view.override),
        effective=_build_effective(view.effective),
        freshness=_build_freshness(view.freshness),
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
    sort: Annotated[Literal["code", "name", "interval"], Query()] = "code",
    order: Annotated[Literal["asc", "desc"], Query()] = "asc",
) -> MaterialThresholdListResponse:
    page = await service.list_materials(
        limit=limit,
        offset=offset,
        search=search,
        sort=sort,
        descending=order == "desc",
    )
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
                metadata_json=await _material_metadata(service, material_id, result.changes),
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
                metadata_json=await _material_metadata(service, material_id, changes),
            ),
        )
    await session.commit()


@router.put("/{material_id}/freshness", response_model=MaterialFreshnessResponse)
async def put_material_freshness(
    request: Request,
    material_id: UUID,
    payload: MaterialFreshnessUpdateRequest,
    current_user: Annotated[User, Depends(require_permission("price_alerts.manage"))],
    service: Annotated[
        PriceAlertMaterialThresholdService,
        Depends(get_material_threshold_service),
    ],
    audit_log_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MaterialFreshnessResponse:
    try:
        result = await service.set_freshness(
            material_id=material_id,
            is_watched=payload.is_watched,
            expected_interval_days=payload.expected_interval_days,
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
            action="price_alerts.freshness_updated",
            entity_type="price_freshness_material",
            context=AuditLogContext.from_request(
                request=request,
                current_user=current_user,
                entity_id=str(material_id),
                metadata_json=await _material_metadata(service, material_id, result.changes),
            ),
        )
    await session.commit()
    freshness = _build_freshness(result.config)
    assert freshness is not None
    return MaterialFreshnessResponse(material_id=result.material_id, freshness=freshness)


@router.delete("/{material_id}/freshness", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material_freshness(
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
    changes = await service.clear_freshness(material_id=material_id)
    if changes:
        await audit_log_service.log_event(
            action="price_alerts.freshness_updated",
            entity_type="price_freshness_material",
            context=AuditLogContext.from_request(
                request=request,
                current_user=current_user,
                entity_id=str(material_id),
                metadata_json=await _material_metadata(service, material_id, changes),
            ),
        )
    await session.commit()
