from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_permission
from app.db.session import get_db_session
from app.models import Role, User
from app.schemas import (
    RoleCreateRequest,
    RoleListResponse,
    RoleLookupResponse,
    RoleResponse,
    RoleUpdateRequest,
)
from app.services import (
    AuditLogContext,
    AuditLogService,
    PermissionNotFoundError,
    RoleAdminService,
    RoleAlreadyExistsError,
    RoleNotFoundError,
    SystemRoleModificationError,
)

router = APIRouter(prefix="/roles", tags=["roles"])


def get_role_admin_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RoleAdminService:
    return RoleAdminService(session)


def get_audit_log_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuditLogService:
    return AuditLogService(session)


def _build_role_response(role: Role) -> RoleResponse:
    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        permissions=[p.code for p in role.permissions],
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


@router.get("", response_model=RoleListResponse)
async def list_roles(
    current_user: Annotated[User, Depends(require_permission("roles.read"))],
    role_admin_service: Annotated[RoleAdminService, Depends(get_role_admin_service)],
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    search: str | None = None,
    sort_by: str = "name",
    sort_order: str = "asc",
) -> RoleListResponse:
    roles, total = await role_admin_service.list_roles(
        limit=limit,
        offset=offset,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return RoleListResponse(
        items=[_build_role_response(r) for r in roles],
        total=total,
    )


@router.get("/lookup", response_model=RoleLookupResponse)
async def lookup_roles(
    current_user: Annotated[User, Depends(require_permission("roles.read"))],
    role_admin_service: Annotated[RoleAdminService, Depends(get_role_admin_service)],
) -> RoleLookupResponse:
    roles = await role_admin_service.lookup_all_roles()
    return RoleLookupResponse(items=[_build_role_response(r) for r in roles])


@router.get("/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: UUID,
    current_user: Annotated[User, Depends(require_permission("roles.read"))],
    role_admin_service: Annotated[RoleAdminService, Depends(get_role_admin_service)],
) -> RoleResponse:
    try:
        role = await role_admin_service.get_role_by_id(role_id)
        return _build_role_response(role)
    except RoleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    request: Request,
    payload: RoleCreateRequest,
    current_user: Annotated[User, Depends(require_permission("roles.create"))],
    role_admin_service: Annotated[RoleAdminService, Depends(get_role_admin_service)],
    audit_log_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RoleResponse:
    try:
        role = await role_admin_service.create_role(
            name=payload.name,
            description=payload.description,
            permission_codes=payload.permissions,
        )

        await audit_log_service.log_event(
            action="roles.role_created",
            entity_type="role",
            context=AuditLogContext.from_request(
                request=request,
                current_user=current_user,
                entity_id=str(role.id),
                metadata_json={
                    "name": role.name,
                    "description": role.description,
                    "permissions": payload.permissions,
                },
            ),
        )

        await session.commit()

        return _build_role_response(role)
    except RoleAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except PermissionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.put("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: UUID,
    request: Request,
    payload: RoleUpdateRequest,
    current_user: Annotated[User, Depends(require_permission("roles.update"))],
    role_admin_service: Annotated[RoleAdminService, Depends(get_role_admin_service)],
    audit_log_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RoleResponse:
    try:
        role = await role_admin_service.update_role(
            role_id=role_id,
            name=payload.name,
            description=payload.description,
            permission_codes=payload.permissions,
        )

        await audit_log_service.log_event(
            action="roles.role_updated",
            entity_type="role",
            context=AuditLogContext.from_request(
                request=request,
                current_user=current_user,
                entity_id=str(role.id),
                metadata_json={
                    "name": role.name,
                    "description": role.description,
                    "permissions": payload.permissions,
                },
            ),
        )

        await session.commit()

        return _build_role_response(role)
    except RoleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (RoleAlreadyExistsError, SystemRoleModificationError, PermissionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(require_permission("roles.delete"))],
    role_admin_service: Annotated[RoleAdminService, Depends(get_role_admin_service)],
    audit_log_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    try:
        role = await role_admin_service.get_role_by_id(role_id)
        role_name = role.name
        await role_admin_service.delete_role(role_id)

        await audit_log_service.log_event(
            action="roles.role_deleted",
            entity_type="role",
            context=AuditLogContext.from_request(
                request=request,
                current_user=current_user,
                entity_id=str(role_id),
                metadata_json={
                    "name": role_name,
                },
            ),
        )

        await session.commit()
    except RoleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except SystemRoleModificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
