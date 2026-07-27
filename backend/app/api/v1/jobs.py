from __future__ import annotations

import io
import typing
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.url_utils import build_api_file_download_path
from app.auth.dependencies import get_current_user, require_permission
from app.auth.permissions import has_permission
from app.core.rate_limit import build_rate_limit_dependency
from app.db.session import get_db_session
from app.models import ExportJob, File, ImportJob, User
from app.schemas.file import FileResponse
from app.schemas.job import (
    ExportJobListResponse,
    ExportJobResponse,
    ImportJobListResponse,
    ImportJobResponse,
)
from app.services.audit_log import AuditLogContext, AuditLogService
from app.services.file_admin import FileAdminService
from app.services.job_admin import JobAdminService, JobNotFoundError

router = APIRouter(tags=["jobs"])

limit_users_import = build_rate_limit_dependency(
    scope="users.import",
    limit_setting="rate_limit_users_import",
)
limit_users_export = build_rate_limit_dependency(
    scope="users.export",
    limit_setting="rate_limit_users_export",
)


def get_job_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> JobAdminService:
    return JobAdminService(session)


def get_file_admin_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FileAdminService:
    return FileAdminService(session)


def get_audit_log_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuditLogService:
    return AuditLogService(session)


class ExportRequest(BaseModel):
    search: str | None = None
    status: str | None = None


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


def _build_import_job_response(job: ImportJob) -> ImportJobResponse:
    return ImportJobResponse(
        id=job.id,
        file_id=job.file_id,
        status=job.status,
        total_rows=job.total_rows,
        processed_rows=job.processed_rows,
        failed_rows=job.failed_rows,
        error_summary=job.error_summary,
        errors_json=job.errors_json,
        created_by_id=job.created_by_id,
        created_at=job.created_at,
        updated_at=job.updated_at,
        file=_build_file_response(job.file) if job.file else None,
    )


def _build_export_job_response(job: ExportJob) -> ExportJobResponse:
    return ExportJobResponse(
        id=job.id,
        status=job.status,
        file_id=job.file_id,
        filters=job.filters,
        error_summary=job.error_summary,
        created_by_id=job.created_by_id,
        created_at=job.created_at,
        updated_at=job.updated_at,
        file=_build_file_response(job.file) if job.file else None,
    )


@router.post(
    "/users/import",
    response_model=ImportJobResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(require_permission("users.import")),
        Depends(limit_users_import),
    ],
)
async def import_users(
    request: Request,
    file: UploadFile,
    job_service: Annotated[JobAdminService, Depends(get_job_service)] = None,  # type: ignore[assignment]
    file_service: Annotated[FileAdminService, Depends(get_file_admin_service)] = None,  # type: ignore[assignment]
    audit_service: Annotated[AuditLogService, Depends(get_audit_log_service)] = None,  # type: ignore[assignment]
    current_user: Annotated[User, Depends(get_current_user)] = None,  # type: ignore[assignment]
) -> ImportJobResponse:
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are supported for import.",
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
        db_file = await file_service.upload_file(
            filename=file.filename,
            content_type=file.content_type or "text/csv",
            size_bytes=file_size,
            data_stream=data_stream,
            is_public=False,  # Import files are always private
            uploaded_by_id=current_user.id,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload import file: {e}",
        ) from e

    db_job = await job_service.create_import_job(
        file_id=db_file.id,
        user_id=current_user.id,
    )

    # Emit Audit Log
    await audit_service.log_event(
        action="users.import_started",
        entity_type="import_job",
        context=AuditLogContext.from_request(
            request=request,
            current_user=current_user,
            entity_id=str(db_job.id),
            metadata_json={
                "filename": db_file.filename,
                "file_id": str(db_file.id),
            },
        ),
    )

    await job_service.session.commit()
    return _build_import_job_response(db_job)


@router.get(
    "/users/import/jobs",
    response_model=ImportJobListResponse,
    dependencies=[Depends(require_permission("users.import"))],
)
async def list_import_jobs(
    request: Request,
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    job_service: Annotated[JobAdminService, Depends(get_job_service)] = None,  # type: ignore[assignment]
    current_user: Annotated[User, Depends(get_current_user)] = None,  # type: ignore[assignment]
) -> ImportJobListResponse:
    is_admin = has_permission(current_user, "users.read")  # or read_all equivalent
    jobs, total = await job_service.list_import_jobs(
        limit=limit,
        offset=offset,
        user_id=current_user.id,
        is_admin=is_admin,
    )

    items = [_build_import_job_response(j) for j in jobs]
    return ImportJobListResponse(items=items, total=total)


@router.get(
    "/users/import/jobs/{job_id}",
    response_model=ImportJobResponse,
    dependencies=[Depends(require_permission("users.import"))],
)
async def get_import_job(
    job_id: UUID,
    request: Request,
    job_service: Annotated[JobAdminService, Depends(get_job_service)] = None,  # type: ignore[assignment]
    current_user: Annotated[User, Depends(get_current_user)] = None,  # type: ignore[assignment]
) -> ImportJobResponse:
    try:
        job = await job_service.get_import_job_by_id(job_id)
    except JobNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import job not found.",
        ) from e

    # Access check: admin or owner
    is_admin = has_permission(current_user, "users.read")
    if not is_admin and job.created_by_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this import job.",
        )

    return _build_import_job_response(job)


@router.post(
    "/users/export",
    response_model=ExportJobResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(require_permission("users.export")),
        Depends(limit_users_export),
    ],
)
async def export_users(
    request: Request,
    payload: ExportRequest,
    job_service: Annotated[JobAdminService, Depends(get_job_service)] = None,  # type: ignore[assignment]
    audit_service: Annotated[AuditLogService, Depends(get_audit_log_service)] = None,  # type: ignore[assignment]
    current_user: Annotated[User, Depends(get_current_user)] = None,  # type: ignore[assignment]
) -> ExportJobResponse:
    filters = payload.model_dump(exclude_none=True)

    db_job = await job_service.create_export_job(
        filters=filters,
        user_id=current_user.id,
    )

    # Emit Audit Log
    await audit_service.log_event(
        action="users.export_started",
        entity_type="export_job",
        context=AuditLogContext.from_request(
            request=request,
            current_user=current_user,
            entity_id=str(db_job.id),
            metadata_json={
                "filters": filters,
            },
        ),
    )

    await job_service.session.commit()
    return _build_export_job_response(db_job)


@router.get(
    "/users/export/jobs",
    response_model=ExportJobListResponse,
    dependencies=[Depends(require_permission("users.export"))],
)
async def list_export_jobs(
    request: Request,
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    job_service: Annotated[JobAdminService, Depends(get_job_service)] = None,  # type: ignore[assignment]
    current_user: Annotated[User, Depends(get_current_user)] = None,  # type: ignore[assignment]
) -> ExportJobListResponse:
    is_admin = has_permission(current_user, "users.read")
    jobs, total = await job_service.list_export_jobs(
        limit=limit,
        offset=offset,
        user_id=current_user.id,
        is_admin=is_admin,
    )

    items = [_build_export_job_response(j) for j in jobs]
    return ExportJobListResponse(items=items, total=total)


@router.get(
    "/users/export/jobs/{job_id}",
    response_model=ExportJobResponse,
    dependencies=[Depends(require_permission("users.export"))],
)
async def get_export_job(
    job_id: UUID,
    request: Request,
    job_service: Annotated[JobAdminService, Depends(get_job_service)] = None,  # type: ignore[assignment]
    current_user: Annotated[User, Depends(get_current_user)] = None,  # type: ignore[assignment]
) -> ExportJobResponse:
    try:
        job = await job_service.get_export_job_by_id(job_id)
    except JobNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export job not found.",
        ) from e

    is_admin = has_permission(current_user, "users.read")
    if not is_admin and job.created_by_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this export job.",
        )

    return _build_export_job_response(job)
