from __future__ import annotations

import io
import typing
from collections.abc import Mapping
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.url_utils import build_api_file_download_path
from app.api.v1.auth import _build_current_user_response
from app.auth.dependencies import get_current_user, require_permission
from app.auth.hashing import hash_password, verify_password
from app.auth.permissions import has_permission, resolve_role_names
from app.core.rate_limit import build_rate_limit_dependency
from app.db.session import get_db_session
from app.models import User, UserStatus
from app.schemas import (
    UserAvatarUploadResponse,
    UserCreateRequest,
    UserListResponse,
    UserPasswordChangeRequest,
    UserResponse,
    UserRoleUpdateRequest,
    UserUpdateRequest,
)
from app.schemas.auth import CurrentUserResponse
from app.services import (
    AuditLogContext,
    AuditLogService,
    EmailAlreadyExistsError,
    FileAdminService,
    RoleNotFoundError,
    UserAdminService,
    UserNotFoundError,
)

router = APIRouter(prefix="/users", tags=["users"])

USER_AUDIT_FIELD_LABELS = {
    "email": "Email",
    "full_name": "Họ và tên",
    "status": "Trạng thái",
    "role_names": "Vai trò",
    "avatar_url": "Ảnh đại diện",
}

limit_users_avatar_upload = build_rate_limit_dependency(
    scope="users.avatar_upload",
    limit_setting="rate_limit_users_avatar_upload",
)


def get_user_admin_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserAdminService:
    return UserAdminService(session)


def get_audit_log_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuditLogService:
    return AuditLogService(session)


def get_file_admin_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FileAdminService:
    return FileAdminService(session)


def require_user_avatar_upload_permission(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if has_permission(current_user, "users.create") or has_permission(
        current_user,
        "users.update",
    ):
        return current_user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission to upload user avatars.",
    )


@router.get("", response_model=UserListResponse)
async def list_users(
    request: Request,
    current_user: Annotated[User, Depends(require_permission("users.read"))],
    user_admin_service: Annotated[UserAdminService, Depends(get_user_admin_service)],
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    search: str | None = None,
    status_filter: str | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> UserListResponse:
    user_status = None
    if status_filter:
        try:
            user_status = UserStatus(status_filter)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid status filter.",
            ) from exc

    users, total = await user_admin_service.list_users(
        limit=limit,
        offset=offset,
        search=search,
        status=user_status,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    return UserListResponse(
        items=[_build_user_response(u) for u in users],
        total=total,
    )


@router.post(
    "/me/avatar",
    response_model=CurrentUserResponse,
    dependencies=[Depends(limit_users_avatar_upload)],
)
async def upload_current_user_avatar(
    request: Request,
    file: UploadFile,
    current_user: Annotated[User, Depends(get_current_user)],
    file_admin_service: Annotated[FileAdminService, Depends(get_file_admin_service)],
    audit_log_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CurrentUserResponse:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is missing.",
        )

    content_type = file.content_type or "application/octet-stream"
    if not content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only image uploads are supported for user avatars.",
        )

    file_size = file.size
    data_stream: io.BytesIO | typing.BinaryIO
    if file_size is None or file_size <= 0:
        file_content = await file.read()
        file_size = len(file_content)
        data_stream = io.BytesIO(file_content)
    else:
        data_stream = file.file

    previous_avatar_url = current_user.avatar_url

    try:
        db_file = await file_admin_service.upload_file(
            filename=file.filename,
            content_type=content_type,
            size_bytes=file_size,
            data_stream=data_stream,
            is_public=True,
            uploaded_by_id=current_user.id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload avatar image: {exc}",
        ) from exc

    current_user.avatar_url = build_api_file_download_path(str(db_file.id))

    await audit_log_service.log_event(
        action="users.avatar_uploaded",
        entity_type="user",
        context=AuditLogContext.from_request(
            request=request,
            current_user=current_user,
            entity_id=str(current_user.id),
            metadata_json={
                "email": current_user.email,
                "filename": db_file.filename,
                "content_type": db_file.content_type,
                "size_bytes": db_file.size_bytes,
                "purpose": "user_avatar",
                "is_public": db_file.is_public,
                "outcome": "updated",
                "changes": [
                    _build_user_audit_change(
                        "avatar_url",
                        previous_avatar_url,
                        current_user.avatar_url,
                    )
                ],
            },
        ),
    )

    await session.commit()

    return _build_current_user_response(current_user)


@router.put("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_current_user_password(
    payload: UserPasswordChangeRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    audit_log_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    current_user.password_hash = hash_password(payload.new_password)

    await audit_log_service.log_event(
        action="users.password_changed",
        entity_type="user",
        context=AuditLogContext.from_request(
            request=request,
            current_user=current_user,
            entity_id=str(current_user.id),
            metadata_json={
                "email": current_user.email,
                "changes": [
                    {
                        "field": "login_information",
                        "label": "Thông tin đăng nhập",
                        "old_value": "[HIDDEN]",
                        "new_value": "Đã cập nhật",
                    }
                ],
                "outcome": "updated",
            },
        ),
    )

    await session.commit()


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    current_user: Annotated[User, Depends(require_permission("users.read"))],
    user_admin_service: Annotated[UserAdminService, Depends(get_user_admin_service)],
) -> UserResponse:
    try:
        user = await user_admin_service.get_user_by_id(user_id)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return _build_user_response(user)


@router.post(
    "/avatar-upload",
    response_model=UserAvatarUploadResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limit_users_avatar_upload)],
)
async def upload_user_avatar(
    request: Request,
    file: UploadFile,
    current_user: Annotated[User, Depends(require_user_avatar_upload_permission)],
    file_admin_service: Annotated[FileAdminService, Depends(get_file_admin_service)],
    audit_log_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
) -> UserAvatarUploadResponse:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is missing.",
        )

    content_type = file.content_type or "application/octet-stream"
    if not content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only image uploads are supported for user avatars.",
        )

    file_size = file.size
    data_stream: io.BytesIO | typing.BinaryIO
    if file_size is None or file_size <= 0:
        file_content = await file.read()
        file_size = len(file_content)
        data_stream = io.BytesIO(file_content)
    else:
        data_stream = file.file

    try:
        db_file = await file_admin_service.upload_file(
            filename=file.filename,
            content_type=content_type,
            size_bytes=file_size,
            data_stream=data_stream,
            is_public=True,
            uploaded_by_id=current_user.id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload avatar image: {exc}",
        ) from exc

    await audit_log_service.log_event(
        action="users.avatar_uploaded",
        entity_type="file",
        context=AuditLogContext.from_request(
            request=request,
            current_user=current_user,
            entity_id=str(db_file.id),
            metadata_json={
                "filename": db_file.filename,
                "content_type": db_file.content_type,
                "size_bytes": db_file.size_bytes,
                "purpose": "user_avatar",
                "is_public": db_file.is_public,
                "outcome": "uploaded",
            },
        ),
    )

    await file_admin_service.session.commit()

    return UserAvatarUploadResponse(
        avatar_url=build_api_file_download_path(str(db_file.id)),
        filename=db_file.filename,
    )


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(
    payload: UserCreateRequest,
    request: Request,
    current_user: Annotated[User, Depends(require_permission("users.create"))],
    user_admin_service: Annotated[UserAdminService, Depends(get_user_admin_service)],
    audit_log_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserResponse:
    try:
        created_user = await user_admin_service.create_user(
            email=payload.email,
            password=payload.password,
            status=UserStatus(payload.status),
            role_names=payload.role_names,
            full_name=payload.full_name,
            avatar_url=payload.avatar_url,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="User status is invalid.",
        ) from exc
    except EmailAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except RoleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    await audit_log_service.log_event(
        action="users.user_created",
        entity_type="user",
        context=AuditLogContext.from_request(
            request=request,
            current_user=current_user,
            entity_id=str(created_user.id),
            metadata_json={
                "email": created_user.email,
                "changes": _build_user_created_audit_changes(
                    _snapshot_user_audit_state(created_user),
                ),
                "outcome": "created",
                "role_names": sorted(resolve_role_names(created_user)),
            },
        ),
    )

    await session.commit()

    return _build_user_response(created_user)


@router.put(
    "/{user_id}",
    response_model=UserResponse,
)
async def update_user(
    user_id: UUID,
    payload: UserUpdateRequest,
    request: Request,
    current_user: Annotated[User, Depends(require_permission("users.update"))],
    user_admin_service: Annotated[UserAdminService, Depends(get_user_admin_service)],
    audit_log_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserResponse:
    try:
        user_status = UserStatus(payload.status)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="User status is invalid.",
        ) from exc

    try:
        existing_user = await user_admin_service.get_user_by_id(user_id)
        previous_user_state = _snapshot_user_audit_state(existing_user)
        updated_user = await user_admin_service.update_user(
            user_id=user_id,
            email=payload.email,
            status=user_status,
            password=payload.password,
            role_names=payload.role_names,
            full_name=payload.full_name,
            avatar_url=payload.avatar_url,
        )
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except EmailAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except RoleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    await audit_log_service.log_event(
        action="users.user_updated",
        entity_type="user",
        context=AuditLogContext.from_request(
            request=request,
            current_user=current_user,
            entity_id=str(updated_user.id),
            metadata_json={
                "email": updated_user.email,
                "changes": _build_user_update_audit_changes(
                    previous_user_state,
                    _snapshot_user_audit_state(updated_user),
                    includes_password_change=payload.password is not None,
                ),
                "outcome": "updated",
                "role_names": sorted(resolve_role_names(updated_user)),
            },
        ),
    )

    await session.commit()

    return _build_user_response(updated_user)


@router.put(
    "/{user_id}/roles",
    response_model=UserResponse,
)
async def update_user_roles(
    user_id: UUID,
    payload: UserRoleUpdateRequest,
    request: Request,
    current_user: Annotated[User, Depends(require_permission("users.update"))],
    user_admin_service: Annotated[UserAdminService, Depends(get_user_admin_service)],
    audit_log_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserResponse:
    try:
        existing_user = await user_admin_service.get_user_by_id(user_id)
        previous_user_state = _snapshot_user_audit_state(existing_user)
        updated_user = await user_admin_service.update_user_roles(
            user_id=user_id,
            role_names=payload.role_names,
        )
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except RoleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    await audit_log_service.log_event(
        action="users.roles_updated",
        entity_type="user",
        context=AuditLogContext.from_request(
            request=request,
            current_user=current_user,
            entity_id=str(updated_user.id),
            metadata_json={
                "email": updated_user.email,
                "changes": _build_user_update_audit_changes(
                    previous_user_state,
                    _snapshot_user_audit_state(updated_user),
                    includes_password_change=False,
                    fields=("role_names",),
                ),
                "outcome": "updated",
                "role_names": sorted(resolve_role_names(updated_user)),
            },
        ),
    )

    await session.commit()

    return _build_user_response(updated_user)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_user(
    user_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(require_permission("users.delete"))],
    user_admin_service: Annotated[UserAdminService, Depends(get_user_admin_service)],
    audit_log_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete yourself.",
        )

    try:
        target_user = await user_admin_service.get_user_by_id(user_id)
        target_email = target_user.email
        await user_admin_service.delete_user(user_id)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    await audit_log_service.log_event(
        action="users.user_deleted",
        entity_type="user",
        context=AuditLogContext.from_request(
            request=request,
            current_user=current_user,
            entity_id=str(user_id),
            metadata_json={
                "email": target_email,
            },
        ),
    )

    await session.commit()


def _snapshot_user_audit_state(user: User) -> dict[str, object]:
    return {
        "email": user.email,
        "full_name": user.full_name,
        "status": user.status.value,
        "role_names": sorted(resolve_role_names(user)),
        "avatar_url": user.avatar_url,
    }


def _build_user_created_audit_changes(
    new_state: Mapping[str, object],
) -> list[dict[str, object]]:
    return [
        _build_user_audit_change(field, None, new_state.get(field))
        for field in USER_AUDIT_FIELD_LABELS
        if new_state.get(field) not in (None, "", [])
    ]


def _build_user_update_audit_changes(
    previous_state: Mapping[str, object],
    new_state: Mapping[str, object],
    *,
    includes_password_change: bool,
    fields: tuple[str, ...] | None = None,
) -> list[dict[str, object]]:
    inspected_fields = fields or tuple(USER_AUDIT_FIELD_LABELS)
    changes = [
        _build_user_audit_change(
            field,
            previous_state.get(field),
            new_state.get(field),
        )
        for field in inspected_fields
        if previous_state.get(field) != new_state.get(field)
    ]

    if includes_password_change:
        changes.append(
            {
                "field": "login_information",
                "label": "Thông tin đăng nhập",
                "old_value": "[HIDDEN]",
                "new_value": "Đã cập nhật",
            }
        )

    return changes


def _build_user_audit_change(
    field: str,
    old_value: object,
    new_value: object,
) -> dict[str, object]:
    return {
        "field": field,
        "label": USER_AUDIT_FIELD_LABELS[field],
        "old_value": old_value,
        "new_value": new_value,
    }


def _build_user_response(user: User) -> UserResponse:
    current_user_payload = _build_current_user_response(user)
    return UserResponse(
        id=current_user_payload.id,
        email=current_user_payload.email,
        status=current_user_payload.status,
        roles=current_user_payload.roles,
        permissions=current_user_payload.permissions,
        last_login_at=current_user_payload.last_login_at,
        full_name=current_user_payload.full_name,
        avatar_url=current_user_payload.avatar_url,
    )
