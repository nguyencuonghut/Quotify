from __future__ import annotations

import io
import typing
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.url_utils import build_api_file_download_path
from app.auth.dependencies import get_current_user, require_permission
from app.auth.jwt import decode_access_token
from app.auth.permissions import has_permission
from app.auth.service import AuthService
from app.core.rate_limit import build_rate_limit_dependency
from app.db.session import get_db_session
from app.models import File, User
from app.schemas.file import FileListResponse, FileResponse
from app.services.audit_log import AuditLogContext, AuditLogService
from app.services.file_admin import (
    FileAdminService,
    FileMetadataNotFoundError,
    FilePermissionDeniedError,
)

router = APIRouter(prefix="/files", tags=["files"])

limit_files_upload = build_rate_limit_dependency(
    scope="files.upload",
    limit_setting="rate_limit_files_upload",
)


def get_file_admin_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FileAdminService:
    return FileAdminService(session)


def get_audit_log_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuditLogService:
    return AuditLogService(session)


async def get_optional_current_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> User | None:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header.partition("Bearer ")[2].strip()
    try:
        payload = decode_access_token(token)
        auth_service = AuthService(session)
        return await auth_service.get_active_user(user_id=payload.sub)
    except Exception:
        return None


def _build_file_response(db_file: File) -> FileResponse:
    return FileResponse(
        id=db_file.id,
        filename=db_file.filename,
        content_type=db_file.content_type,
        size_bytes=db_file.size_bytes,
        is_public=db_file.is_public,
        uploaded_by_id=db_file.uploaded_by_id,
        created_at=db_file.created_at,
        url=build_api_file_download_path(str(db_file.id)),
    )


@router.post(
    "/upload",
    response_model=FileResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(require_permission("files.upload")),
        Depends(limit_files_upload),
    ],
)
async def upload_file(
    request: Request,
    file: UploadFile,
    is_public: bool = Form(False),
    file_admin_service: Annotated[FileAdminService, Depends(get_file_admin_service)] = None,  # type: ignore[assignment]
    audit_service: Annotated[AuditLogService, Depends(get_audit_log_service)] = None,  # type: ignore[assignment]
    current_user: Annotated[User, Depends(get_current_user)] = None,  # type: ignore[assignment]
) -> FileResponse:
    # Validation checks
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is missing.",
        )

    file_size = file.size
    data_stream: io.BytesIO | typing.BinaryIO
    if file_size is None or file_size <= 0:
        # FastAPI might not have size populated depending on the upload provider,
        # but normally it's populated. Let's read to check if size is missing.
        file_content = await file.read()
        file_size = len(file_content)
        data_stream = io.BytesIO(file_content)
    else:
        data_stream = file.file

    try:
        db_file = await file_admin_service.upload_file(
            filename=file.filename,
            content_type=file.content_type or "application/octet-stream",
            size_bytes=file_size,
            data_stream=data_stream,
            is_public=is_public,
            uploaded_by_id=current_user.id,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file to storage: {e}",
        ) from e

    # Emit Audit Log
    await audit_service.log_event(
        action="files.file_uploaded",
        entity_type="file",
        context=AuditLogContext.from_request(
            request=request,
            current_user=current_user,
            entity_id=str(db_file.id),
            metadata_json={
                "filename": db_file.filename,
                "size_bytes": db_file.size_bytes,
                "is_public": db_file.is_public,
            },
        ),
    )
    # Commit changes on the request lifecycle
    await file_admin_service.session.commit()

    return _build_file_response(db_file)


@router.get(
    "",
    response_model=FileListResponse,
    dependencies=[Depends(require_permission("files.read"))],
)
async def list_files(
    request: Request,
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    search: str | None = None,
    file_admin_service: Annotated[FileAdminService, Depends(get_file_admin_service)] = None,  # type: ignore[assignment]
    current_user: Annotated[User, Depends(get_current_user)] = None,  # type: ignore[assignment]
) -> FileListResponse:
    read_all = has_permission(current_user, "files.read_all")

    files, total = await file_admin_service.list_files(
        limit=limit,
        offset=offset,
        search=search,
        user_id=current_user.id,
        read_all=read_all,
    )

    items = [_build_file_response(f) for f in files]

    return FileListResponse(items=items, total=total)


@router.get(
    "/{file_id}",
    response_model=FileResponse,
)
async def get_file_metadata(
    file_id: UUID,
    request: Request,
    file_admin_service: Annotated[FileAdminService, Depends(get_file_admin_service)] = None,  # type: ignore[assignment]
    current_user: Annotated[User, Depends(get_current_user)] = None,  # type: ignore[assignment]
) -> FileResponse:
    try:
        db_file = await file_admin_service.get_file_by_id(file_id)
    except FileMetadataNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File metadata not found.",
        ) from e

    # Authorization check for private files
    if not db_file.is_public:
        is_owner = db_file.uploaded_by_id == current_user.id
        can_read_all = has_permission(current_user, "files.read_all")
        if not is_owner and not can_read_all:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to view this file metadata.",
            )

    return _build_file_response(db_file)


@router.get(
    "/{file_id}/download",
)
async def download_file(
    file_id: UUID,
    inline: bool = False,
    file_admin_service: Annotated[FileAdminService, Depends(get_file_admin_service)] = None,  # type: ignore[assignment]
    current_user: Annotated[User | None, Depends(get_optional_current_user)] = None,
) -> StreamingResponse:
    try:
        db_file = await file_admin_service.get_file_by_id(file_id)
    except FileMetadataNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found.",
        ) from e

    # Authorization check for private files
    if not db_file.is_public:
        if current_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication credentials are required for private files.",
            )
        is_owner = db_file.uploaded_by_id == current_user.id
        can_read_all = has_permission(current_user, "files.read_all")
        if not is_owner and not can_read_all:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this file.",
            )

    # Retrieve object stream from MinIO
    try:
        minio_response = file_admin_service.minio_client.get_object(
            bucket_name=db_file.bucket,
            object_name=db_file.storage_path,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve file from storage: {e}",
        ) from e

    def stream_file() -> typing.Generator[bytes, None, None]:
        try:
            # Read in 32KB chunks
            while chunk := minio_response.read(32 * 1024):
                yield chunk
        finally:
            minio_response.close()
            minio_response.release_conn()

    disposition = "inline" if inline else "attachment"
    headers = {
        "Content-Disposition": f'{disposition}; filename="{db_file.filename}"',
        "Content-Length": str(db_file.size_bytes),
    }

    return StreamingResponse(
        stream_file(),
        media_type=db_file.content_type,
        headers=headers,
    )


@router.delete(
    "/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_file(
    file_id: UUID,
    request: Request,
    file_admin_service: Annotated[FileAdminService, Depends(get_file_admin_service)] = None,  # type: ignore[assignment]
    audit_service: Annotated[AuditLogService, Depends(get_audit_log_service)] = None,  # type: ignore[assignment]
    current_user: Annotated[User, Depends(get_current_user)] = None,  # type: ignore[assignment]
) -> None:
    can_delete_all = has_permission(current_user, "files.delete")

    try:
        db_file = await file_admin_service.get_file_by_id(file_id)
    except FileMetadataNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File metadata not found.",
        ) from e

    try:
        await file_admin_service.delete_file(
            file_id=file_id,
            user_id=current_user.id,
            can_delete_all=can_delete_all,
        )
    except FilePermissionDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e

    # Emit Audit Log
    await audit_service.log_event(
        action="files.file_deleted",
        entity_type="file",
        context=AuditLogContext.from_request(
            request=request,
            current_user=current_user,
            entity_id=str(file_id),
            metadata_json={
                "filename": db_file.filename,
                "size_bytes": db_file.size_bytes,
                "is_public": db_file.is_public,
            },
        ),
    )
    # Commit changes on the request lifecycle
    await file_admin_service.session.commit()
