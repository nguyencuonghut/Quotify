from __future__ import annotations

import typing
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import decode_access_token
from app.auth.permissions import has_permission
from app.auth.service import AuthService
from app.db.session import get_db_session
from app.models import User
from app.services.file_admin import (
    FileAdminService,
    FileMetadataNotFoundError,
)

router = APIRouter(prefix="/files", tags=["files"])


def get_file_admin_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FileAdminService:
    return FileAdminService(session)


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
