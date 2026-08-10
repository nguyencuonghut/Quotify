from __future__ import annotations

import io
import typing
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.auth.dependencies import require_permission
from app.db.session import get_db_session
from app.models import ImportJob, User
from app.schemas import ImportJobResponse
from app.services import (
    QUOTE_BACKFILL_IMPORT_TEMPLATE_FILENAME,
    AuditLogContext,
    AuditLogService,
    FileAdminService,
    JobAdminService,
    JobNotFoundError,
    build_quote_backfill_import_error_report,
    build_quote_backfill_import_template,
)

router = APIRouter(prefix="/quote-backfill-imports", tags=["quote-backfill-imports"])

QUOTE_BACKFILL_IMPORT_ENTITY_TYPE = "quote_backfill"
QUOTE_BACKFILL_IMPORT_TASK_NAME = "import_quote_backfill_task"
QUOTE_BACKFILL_IMPORT_STARTED_ACTION = "quotes.backfill_import_started"


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


@router.get("/template")
async def download_quote_backfill_import_template(
    current_user: Annotated[User, Depends(require_permission("quotes.backfill_import"))],
) -> Response:
    content = build_quote_backfill_import_template()
    disposition = f'attachment; filename="{QUOTE_BACKFILL_IMPORT_TEMPLATE_FILENAME}"'
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": disposition},
    )


@router.post("", response_model=ImportJobResponse, status_code=status.HTTP_201_CREATED)
async def import_quote_backfill(
    request: Request,
    file: UploadFile,
    current_user: Annotated[User, Depends(require_permission("quotes.backfill_import"))],
    job_service: Annotated[JobAdminService, Depends(get_job_service)],
    file_service: Annotated[FileAdminService, Depends(get_file_admin_service)],
    audit_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
) -> ImportJobResponse:
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chỉ hỗ trợ file CSV cho import báo giá cũ.",
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
        entity_type=QUOTE_BACKFILL_IMPORT_ENTITY_TYPE,
        task_name=QUOTE_BACKFILL_IMPORT_TASK_NAME,
    )
    await audit_service.log_event(
        action=QUOTE_BACKFILL_IMPORT_STARTED_ACTION,
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
async def get_quote_backfill_import_job(
    job_id: UUID,
    current_user: Annotated[User, Depends(require_permission("quotes.backfill_import"))],
    job_service: Annotated[JobAdminService, Depends(get_job_service)],
) -> ImportJobResponse:
    try:
        job = await job_service.get_import_job_by_id(
            job_id,
            entity_type=QUOTE_BACKFILL_IMPORT_ENTITY_TYPE,
        )
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job không tồn tại.",
        ) from exc

    return _build_import_job_response(job)


@router.get("/{job_id}/error-file")
async def download_quote_backfill_import_error_file(
    job_id: UUID,
    current_user: Annotated[User, Depends(require_permission("quotes.backfill_import"))],
    job_service: Annotated[JobAdminService, Depends(get_job_service)],
) -> Response:
    try:
        job = await job_service.get_import_job_by_id(
            job_id,
            entity_type=QUOTE_BACKFILL_IMPORT_ENTITY_TYPE,
        )
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job không tồn tại.",
        ) from exc

    if not job.errors_json:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job này không có file lỗi.",
        )

    content = build_quote_backfill_import_error_report(job.errors_json)
    disposition = f'attachment; filename="quote_backfill_import_{job.id}_errors.csv"'
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": disposition},
    )
