from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_permission
from app.db.session import get_db_session
from app.models import MaterialType, User
from app.schemas import (
    MaterialTypeCreateRequest,
    MaterialTypeListResponse,
    MaterialTypeResponse,
    MaterialTypeUpdateRequest,
)
from app.services import (
    AuditLogContext,
    AuditLogService,
    MaterialTypeAdminService,
    MaterialTypeAlreadyExistsError,
    MaterialTypeInUseError,
    MaterialTypeNotFoundError,
)

router = APIRouter(prefix="/material-types", tags=["material-types"])


def get_material_type_admin_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MaterialTypeAdminService:
    return MaterialTypeAdminService(session)


def get_audit_log_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuditLogService:
    return AuditLogService(session)


def _build_material_type_response(material_type: MaterialType) -> MaterialTypeResponse:
    return MaterialTypeResponse(
        id=material_type.id,
        code=material_type.code,
        name=material_type.name,
        status=material_type.status,  # type: ignore[arg-type]
        note=material_type.note,
        created_at=material_type.created_at,
        updated_at=material_type.updated_at,
    )


def _material_type_change_metadata(
    *,
    old: MaterialType | None,
    new: MaterialType,
) -> dict[str, object]:
    labels = {
        "code": "Mã loại vật tư",
        "name": "Tên loại vật tư",
        "status": "Trạng thái",
        "note": "Ghi chú",
    }
    changes: list[dict[str, object]] = []
    for field, label in labels.items():
        old_value = getattr(old, field) if old is not None else None
        new_value = getattr(new, field)
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
        "changes": changes,
    }


@router.get("", response_model=MaterialTypeListResponse)
async def list_material_types(
    current_user: Annotated[User, Depends(require_permission("material_types.read"))],
    material_type_admin_service: Annotated[
        MaterialTypeAdminService,
        Depends(get_material_type_admin_service),
    ],
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    search: str | None = None,
    status_filter: Literal["active", "inactive"] | None = Query(default=None, alias="status"),
    sort_by: str = "code",
    sort_order: str = "asc",
) -> MaterialTypeListResponse:
    items, total = await material_type_admin_service.list_material_types(
        limit=limit,
        offset=offset,
        search=search,
        status=status_filter,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return MaterialTypeListResponse(
        items=[_build_material_type_response(item) for item in items],
        total=total,
    )


@router.get("/{material_type_id}", response_model=MaterialTypeResponse)
async def get_material_type(
    material_type_id: UUID,
    current_user: Annotated[User, Depends(require_permission("material_types.read"))],
    material_type_admin_service: Annotated[
        MaterialTypeAdminService,
        Depends(get_material_type_admin_service),
    ],
) -> MaterialTypeResponse:
    try:
        return _build_material_type_response(
            await material_type_admin_service.get_material_type_by_id(material_type_id),
        )
    except MaterialTypeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("", response_model=MaterialTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_material_type(
    request: Request,
    payload: MaterialTypeCreateRequest,
    current_user: Annotated[User, Depends(require_permission("material_types.create"))],
    material_type_admin_service: Annotated[
        MaterialTypeAdminService,
        Depends(get_material_type_admin_service),
    ],
    audit_log_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MaterialTypeResponse:
    try:
        material_type = await material_type_admin_service.create_material_type(
            code=payload.code,
            name=payload.name,
            status=payload.status,
            note=payload.note,
        )
        await audit_log_service.log_event(
            action="material_types.material_type_created",
            entity_type="material_type",
            context=AuditLogContext.from_request(
                request=request,
                current_user=current_user,
                entity_id=str(material_type.id),
                metadata_json=_material_type_change_metadata(old=None, new=material_type),
            ),
        )
        await session.commit()
        return _build_material_type_response(material_type)
    except MaterialTypeAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.put("/{material_type_id}", response_model=MaterialTypeResponse)
async def update_material_type(
    material_type_id: UUID,
    request: Request,
    payload: MaterialTypeUpdateRequest,
    current_user: Annotated[User, Depends(require_permission("material_types.update"))],
    material_type_admin_service: Annotated[
        MaterialTypeAdminService,
        Depends(get_material_type_admin_service),
    ],
    audit_log_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MaterialTypeResponse:
    try:
        old_material_type = await material_type_admin_service.get_material_type_by_id(
            material_type_id,
        )
        old_snapshot = MaterialType(
            id=old_material_type.id,
            code=old_material_type.code,
            name=old_material_type.name,
            status=old_material_type.status,
            note=old_material_type.note,
            created_at=old_material_type.created_at,
            updated_at=old_material_type.updated_at,
        )
        material_type = await material_type_admin_service.update_material_type(
            material_type_id=material_type_id,
            code=payload.code,
            name=payload.name,
            status=payload.status,
            note=payload.note,
        )
        await audit_log_service.log_event(
            action="material_types.material_type_updated",
            entity_type="material_type",
            context=AuditLogContext.from_request(
                request=request,
                current_user=current_user,
                entity_id=str(material_type.id),
                metadata_json=_material_type_change_metadata(
                    old=old_snapshot,
                    new=material_type,
                ),
            ),
        )
        await session.commit()
        return _build_material_type_response(material_type)
    except MaterialTypeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except MaterialTypeAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete("/{material_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material_type(
    material_type_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(require_permission("material_types.delete"))],
    material_type_admin_service: Annotated[
        MaterialTypeAdminService,
        Depends(get_material_type_admin_service),
    ],
    audit_log_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    try:
        material_type = await material_type_admin_service.get_material_type_by_id(
            material_type_id,
        )
        metadata = {
            "code": material_type.code,
            "name": material_type.name,
        }
        await material_type_admin_service.delete_material_type(material_type_id)
        await audit_log_service.log_event(
            action="material_types.material_type_deleted",
            entity_type="material_type",
            context=AuditLogContext.from_request(
                request=request,
                current_user=current_user,
                entity_id=str(material_type_id),
                metadata_json=metadata,
            ),
        )
        await session.commit()
    except MaterialTypeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except MaterialTypeInUseError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
