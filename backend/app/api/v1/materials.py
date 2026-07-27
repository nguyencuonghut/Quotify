from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_permission
from app.db.session import get_db_session
from app.models import Material, User
from app.schemas import (
    MaterialCreateRequest,
    MaterialListResponse,
    MaterialResponse,
    MaterialUpdateRequest,
)
from app.services import (
    AuditLogContext,
    AuditLogService,
    MaterialAdminService,
    MaterialAlreadyExistsError,
    MaterialInUseError,
    MaterialNotFoundError,
    MaterialTypeNotFoundForMaterialError,
)

router = APIRouter(prefix="/materials", tags=["materials"])


def get_material_admin_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MaterialAdminService:
    return MaterialAdminService(session)


def get_audit_log_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuditLogService:
    return AuditLogService(session)


def _build_material_response(material: Material) -> MaterialResponse:
    return MaterialResponse(
        id=material.id,
        code=material.code,
        name=material.name,
        material_type_id=material.material_type_id,
        material_type_code=material.material_type.code,
        material_type_name=material.material_type.name,
        status=material.status,  # type: ignore[arg-type]
        note=material.note,
        created_at=material.created_at,
        updated_at=material.updated_at,
    )


def _material_change_metadata(*, old: Material | None, new: Material) -> dict[str, object]:
    labels = {
        "code": "Mã vật tư",
        "name": "Tên vật tư",
        "material_type_id": "Loại vật tư",
        "status": "Trạng thái",
        "note": "Ghi chú",
    }
    changes: list[dict[str, object]] = []
    for field, label in labels.items():
        old_value = str(getattr(old, field)) if old is not None and field.endswith("_id") else (
            getattr(old, field) if old is not None else None
        )
        new_value = str(getattr(new, field)) if field.endswith("_id") else getattr(new, field)
        if old is None or old_value != new_value:
            changes.append(
                {
                    "field": field,
                    "label": label,
                    "old_value": old_value,
                    "new_value": new_value,
                },
            )
    return {
        "code": new.code,
        "name": new.name,
        "material_type_code": new.material_type.code,
        "material_type_name": new.material_type.name,
        "changes": changes,
    }


@router.get("", response_model=MaterialListResponse)
async def list_materials(
    current_user: Annotated[User, Depends(require_permission("materials.read"))],
    material_admin_service: Annotated[MaterialAdminService, Depends(get_material_admin_service)],
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    search: str | None = None,
    status_filter: Literal["active", "inactive"] | None = Query(default=None, alias="status"),
    material_type_id: UUID | None = None,
    sort_by: str = "code",
    sort_order: str = "asc",
) -> MaterialListResponse:
    items, total = await material_admin_service.list_materials(
        limit=limit,
        offset=offset,
        search=search,
        status=status_filter,
        material_type_id=material_type_id,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return MaterialListResponse(
        items=[_build_material_response(item) for item in items],
        total=total,
    )


@router.get("/{material_id}", response_model=MaterialResponse)
async def get_material(
    material_id: UUID,
    current_user: Annotated[User, Depends(require_permission("materials.read"))],
    material_admin_service: Annotated[MaterialAdminService, Depends(get_material_admin_service)],
) -> MaterialResponse:
    try:
        return _build_material_response(await material_admin_service.get_material_by_id(material_id))
    except MaterialNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("", response_model=MaterialResponse, status_code=status.HTTP_201_CREATED)
async def create_material(
    request: Request,
    payload: MaterialCreateRequest,
    current_user: Annotated[User, Depends(require_permission("materials.create"))],
    material_admin_service: Annotated[MaterialAdminService, Depends(get_material_admin_service)],
    audit_log_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MaterialResponse:
    try:
        material = await material_admin_service.create_material(
            code=payload.code,
            name=payload.name,
            material_type_id=payload.material_type_id,
            status=payload.status,
            note=payload.note,
        )
        await audit_log_service.log_event(
            action="materials.material_created",
            entity_type="material",
            context=AuditLogContext.from_request(
                request=request,
                current_user=current_user,
                entity_id=str(material.id),
                metadata_json=_material_change_metadata(old=None, new=material),
            ),
        )
        await session.commit()
        return _build_material_response(material)
    except MaterialAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except MaterialTypeNotFoundForMaterialError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.put("/{material_id}", response_model=MaterialResponse)
async def update_material(
    material_id: UUID,
    request: Request,
    payload: MaterialUpdateRequest,
    current_user: Annotated[User, Depends(require_permission("materials.update"))],
    material_admin_service: Annotated[MaterialAdminService, Depends(get_material_admin_service)],
    audit_log_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MaterialResponse:
    try:
        old_material = await material_admin_service.get_material_by_id(material_id)
        old_snapshot = Material(
            id=old_material.id,
            code=old_material.code,
            name=old_material.name,
            material_type_id=old_material.material_type_id,
            status=old_material.status,
            note=old_material.note,
            created_at=old_material.created_at,
            updated_at=old_material.updated_at,
        )
        material = await material_admin_service.update_material(
            material_id=material_id,
            code=payload.code,
            name=payload.name,
            material_type_id=payload.material_type_id,
            status=payload.status,
            note=payload.note,
        )
        await audit_log_service.log_event(
            action="materials.material_updated",
            entity_type="material",
            context=AuditLogContext.from_request(
                request=request,
                current_user=current_user,
                entity_id=str(material.id),
                metadata_json=_material_change_metadata(old=old_snapshot, new=material),
            ),
        )
        await session.commit()
        return _build_material_response(material)
    except MaterialNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except MaterialAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except MaterialTypeNotFoundForMaterialError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material(
    material_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(require_permission("materials.delete"))],
    material_admin_service: Annotated[MaterialAdminService, Depends(get_material_admin_service)],
    audit_log_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    try:
        material = await material_admin_service.get_material_by_id(material_id)
        metadata = {
            "code": material.code,
            "name": material.name,
            "material_type_code": material.material_type.code,
            "material_type_name": material.material_type.name,
        }
        await material_admin_service.delete_material(material_id)
        await audit_log_service.log_event(
            action="materials.material_deleted",
            entity_type="material",
            context=AuditLogContext.from_request(
                request=request,
                current_user=current_user,
                entity_id=str(material_id),
                metadata_json=metadata,
            ),
        )
        await session.commit()
    except MaterialNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except MaterialInUseError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
