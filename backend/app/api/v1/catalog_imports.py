from __future__ import annotations

import io
import typing
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.auth.dependencies import get_current_user
from app.auth.permissions import has_permission
from app.db.session import get_db_session
from app.models import ImportJob, User
from app.schemas import ImportJobResponse
from app.services import (
    AuditLogContext,
    AuditLogService,
    FileAdminService,
    JobAdminService,
    JobNotFoundError,
    build_catalog_import_error_report,
    build_catalog_import_template,
    get_catalog_import_config,
)

router = APIRouter(prefix="/catalog-imports", tags=["catalog-imports"])


def get_file_admin_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FileAdminService:
    return FileAdminService(session)


def get_job_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> JobAdminService:
    return JobAdminService(session)


def get_audit_log_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuditLogService:
    return AuditLogService(session)


def _build_import_job_response(job: ImportJob) -> ImportJobResponse:
    from app.api.v1.jobs import _build_file_response

    return ImportJobResponse(
        id=job.id,
        file_id=job.file_id,
        entity_type=job.entity_type,
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


def _require_catalog_import_permission(entity_type: str, current_user: User) -> str:
    try:
        config = get_catalog_import_config(entity_type)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if not has_permission(current_user, config.permission):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền import danh mục này.",
        )
    return config.entity_type


@router.get("/templates/{entity_type}")
async def download_catalog_import_template(
    entity_type: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    entity_type = _require_catalog_import_permission(entity_type, current_user)
    config = get_catalog_import_config(entity_type)
    content = build_catalog_import_template(config)
    media_type = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if config.file_format == "xlsx"
        else "text/csv; charset=utf-8"
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{config.template_filename}"',
        },
    )


@router.post(
    "/{entity_type}",
    response_model=ImportJobResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_catalog(
    entity_type: str,
    request: Request,
    file: UploadFile,
    current_user: Annotated[User, Depends(get_current_user)],
    job_service: Annotated[JobAdminService, Depends(get_job_service)],
    file_service: Annotated[FileAdminService, Depends(get_file_admin_service)],
    audit_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
) -> ImportJobResponse:
    entity_type = _require_catalog_import_permission(entity_type, current_user)
    config = get_catalog_import_config(entity_type)
    required_extension = f".{config.file_format}"
    if not file.filename or not file.filename.endswith(required_extension):
        detail = (
            "Chỉ hỗ trợ file Excel (.xlsx) cho import danh mục."
            if config.file_format == "xlsx"
            else "Chỉ hỗ trợ file CSV cho import danh mục."
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

    file_size = file.size
    data_stream: io.BytesIO | typing.BinaryIO
    if file_size is None or file_size <= 0:
        file_content = await file.read()
        file_size = len(file_content)
        data_stream = io.BytesIO(file_content)
    else:
        data_stream = file.file

    default_content_type = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if config.file_format == "xlsx"
        else "text/csv"
    )
    try:
        db_file = await file_service.upload_file(
            filename=file.filename,
            content_type=file.content_type or default_content_type,
            size_bytes=file_size,
            data_stream=data_stream,
            is_public=False,
            uploaded_by_id=current_user.id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể tải file import lên hệ thống.",
        ) from exc

    db_job = await job_service.create_import_job(
        file_id=db_file.id,
        user_id=current_user.id,
        entity_type=config.entity_type,
        task_name=config.task_name,
    )
    await audit_service.log_event(
        action=config.started_action,
        entity_type="import_job",
        context=AuditLogContext.from_request(
            request=request,
            current_user=current_user,
            entity_id=str(db_job.id),
            metadata_json={
                "filename": db_file.filename,
                "file_id": str(db_file.id),
                "import_entity_type": db_job.entity_type,
            },
        ),
    )

    await job_service.session.commit()
    await job_service.enqueue_import_job(db_job)
    return _build_import_job_response(db_job)


@router.get("/{job_id}", response_model=ImportJobResponse)
async def get_catalog_import_job(
    job_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    job_service: Annotated[JobAdminService, Depends(get_job_service)],
) -> ImportJobResponse:
    try:
        job = await job_service.get_import_job_by_id(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job không tồn tại.",
        ) from exc

    _require_catalog_import_permission(job.entity_type, current_user)
    return _build_import_job_response(job)


@router.get("/{job_id}/error-file")
async def download_catalog_import_error_file(
    job_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    job_service: Annotated[JobAdminService, Depends(get_job_service)],
) -> Response:
    try:
        job = await job_service.get_import_job_by_id(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job không tồn tại.",
        ) from exc

    entity_type = _require_catalog_import_permission(job.entity_type, current_user)
    if not job.errors_json:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job này không có file lỗi.",
        )

    content = build_catalog_import_error_report(job.errors_json)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{entity_type}_{job.id}_errors.csv"',
        },
    )
