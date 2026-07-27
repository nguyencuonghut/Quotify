from __future__ import annotations

import typing
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.auth.dependencies import require_permission
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.backup import (
    BackupLogListResponse,
    BackupLogResponse,
    BackupScheduleCreateRequest,
    BackupScheduleResponse,
    BackupScheduleUpdateRequest,
)
from app.services.audit_log import AuditLogContext, AuditLogService
from app.services.backup_admin import BackupAdminService, BackupScheduleNotFoundError
from app.storage.minio import build_minio_client

router = APIRouter(prefix="/backups", tags=["backups"])


def get_backup_admin_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BackupAdminService:
    return BackupAdminService(session)


def get_audit_log_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuditLogService:
    return AuditLogService(session)


def _build_log_response(log: Any) -> BackupLogResponse:
    return BackupLogResponse(
        id=log.id,
        backup_type=log.backup_type,
        status=log.status,
        filename=log.filename,
        file_size=log.file_size,
        storage_path=log.storage_path,
        error_message=log.error_message,
        created_by_id=log.created_by_id,
        created_by_email=log.created_by.email if log.created_by else None,
        started_at=log.started_at,
        completed_at=log.completed_at,
        created_at=log.created_at,
    )


def _build_schedule_response(schedule: Any) -> BackupScheduleResponse:
    return BackupScheduleResponse(
        id=schedule.id,
        name=schedule.name,
        frequency=schedule.frequency,
        day_of_week=schedule.day_of_week,
        time_of_day=schedule.time_of_day,
        one_off_datetime=schedule.one_off_datetime,
        is_active=schedule.is_active,
        next_run_at=schedule.next_run_at,
        last_run_at=schedule.last_run_at,
        created_at=schedule.created_at,
        updated_at=schedule.updated_at,
    )


@router.get(
    "",
    response_model=BackupLogListResponse,
    dependencies=[Depends(require_permission("backups.read"))],
)
async def list_backup_logs(
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: Annotated[BackupAdminService, Depends(get_backup_admin_service)] = None,  # type: ignore[assignment]
) -> BackupLogListResponse:
    logs, total = await service.get_backup_logs(limit=limit, offset=offset)
    items = [_build_log_response(log) for log in logs]
    return BackupLogListResponse(items=items, total=total)


@router.post(
    "/now",
    response_model=BackupLogResponse,
    status_code=status.HTTP_201_CREATED,
)
async def trigger_backup_now(
    request: Request,
    service: Annotated[BackupAdminService, Depends(get_backup_admin_service)] = None,  # type: ignore[assignment]
    current_user: Annotated[User, Depends(require_permission("backups.write"))] = None,  # type: ignore[assignment]
    audit_log_service: Annotated[AuditLogService, Depends(get_audit_log_service)] = None,  # type: ignore[assignment]
    session: Annotated[AsyncSession, Depends(get_db_session)] = None,  # type: ignore[assignment]
) -> BackupLogResponse:
    log = await service.trigger_manual_backup(current_user.id)
    await audit_log_service.log_event(
        action="backups.manual_backup_triggered",
        entity_type="backup_log",
        context=AuditLogContext.from_request(
            request=request,
            current_user=current_user,
            entity_id=str(log.id),
            metadata_json={
                "backup_log_id": str(log.id),
                "status": log.status,
                "outcome": "triggered",
            },
        ),
    )
    await session.commit()
    await service.enqueue_manual_backup(log.id)
    return _build_log_response(log)


@router.get(
    "/schedules",
    response_model=list[BackupScheduleResponse],
    dependencies=[Depends(require_permission("backups.read"))],
)
async def list_backup_schedules(
    service: Annotated[BackupAdminService, Depends(get_backup_admin_service)] = None,  # type: ignore[assignment]
) -> list[BackupScheduleResponse]:
    schedules = await service.get_backup_schedules()
    return [_build_schedule_response(s) for s in schedules]


@router.post(
    "/schedules",
    response_model=BackupScheduleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_backup_schedule(
    request: Request,
    payload: BackupScheduleCreateRequest,
    service: Annotated[BackupAdminService, Depends(get_backup_admin_service)] = None,  # type: ignore[assignment]
    current_user: Annotated[User, Depends(require_permission("backups.write"))] = None,  # type: ignore[assignment]
    audit_log_service: Annotated[AuditLogService, Depends(get_audit_log_service)] = None,  # type: ignore[assignment]
    session: Annotated[AsyncSession, Depends(get_db_session)] = None,  # type: ignore[assignment]
) -> BackupScheduleResponse:
    schedule = await service.create_backup_schedule(
        name=payload.name,
        frequency=payload.frequency,
        time_of_day=payload.time_of_day,  # type: ignore[arg-type]
        day_of_week=payload.day_of_week,
        one_off_datetime=payload.one_off_datetime,
        is_active=payload.is_active,
    )
    await audit_log_service.log_event(
        action="backups.schedule_created",
        entity_type="backup_schedule",
        context=AuditLogContext.from_request(
            request=request,
            current_user=current_user,
            entity_id=str(schedule.id),
            metadata_json={
                "backup_schedule_id": str(schedule.id),
                "name": schedule.name,
                "status": "active" if schedule.is_active else "inactive",
                "outcome": "created",
            },
        ),
    )
    await session.commit()
    return _build_schedule_response(schedule)


@router.put(
    "/schedules/{schedule_id}",
    response_model=BackupScheduleResponse,
)
async def update_backup_schedule(
    schedule_id: UUID,
    request: Request,
    payload: BackupScheduleUpdateRequest,
    service: Annotated[BackupAdminService, Depends(get_backup_admin_service)] = None,  # type: ignore[assignment]
    current_user: Annotated[User, Depends(require_permission("backups.write"))] = None,  # type: ignore[assignment]
    audit_log_service: Annotated[AuditLogService, Depends(get_audit_log_service)] = None,  # type: ignore[assignment]
    session: Annotated[AsyncSession, Depends(get_db_session)] = None,  # type: ignore[assignment]
) -> BackupScheduleResponse:
    try:
        schedule = await service.update_backup_schedule(
            schedule_id=schedule_id,
            name=payload.name,
            frequency=payload.frequency,
            time_of_day=payload.time_of_day,  # type: ignore[arg-type]
            day_of_week=payload.day_of_week,
            one_off_datetime=payload.one_off_datetime,
            is_active=payload.is_active,
        )
        await audit_log_service.log_event(
            action="backups.schedule_updated",
            entity_type="backup_schedule",
            context=AuditLogContext.from_request(
                request=request,
                current_user=current_user,
                entity_id=str(schedule.id),
                metadata_json={
                    "backup_schedule_id": str(schedule.id),
                    "name": schedule.name,
                    "status": "active" if schedule.is_active else "inactive",
                    "outcome": "updated",
                },
            ),
        )
        await session.commit()
        return _build_schedule_response(schedule)
    except BackupScheduleNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.delete(
    "/schedules/{schedule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_backup_schedule(
    schedule_id: UUID,
    request: Request,
    service: Annotated[BackupAdminService, Depends(get_backup_admin_service)] = None,  # type: ignore[assignment]
    current_user: Annotated[User, Depends(require_permission("backups.write"))] = None,  # type: ignore[assignment]
    audit_log_service: Annotated[AuditLogService, Depends(get_audit_log_service)] = None,  # type: ignore[assignment]
    session: Annotated[AsyncSession, Depends(get_db_session)] = None,  # type: ignore[assignment]
) -> None:
    try:
        schedule = await service.delete_backup_schedule(schedule_id)
        await audit_log_service.log_event(
            action="backups.schedule_deleted",
            entity_type="backup_schedule",
            context=AuditLogContext.from_request(
                request=request,
                current_user=current_user,
                entity_id=str(schedule_id),
                metadata_json={
                    "backup_schedule_id": str(schedule_id),
                    "name": schedule.name,
                    "status": "active" if schedule.is_active else "inactive",
                    "outcome": "deleted",
                },
            ),
        )
        await session.commit()
    except BackupScheduleNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.get(
    "/{backup_id}/download",
    dependencies=[Depends(require_permission("backups.read"))],
)
async def download_backup_file(
    backup_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> StreamingResponse:
    # 1. Fetch the log
    from sqlalchemy import select

    from app.core.config import get_settings
    from app.models.backup_log import BackupLog

    stmt = select(BackupLog).where(BackupLog.id == backup_id)
    res = await session.execute(stmt)
    log = res.scalar_one_or_none()

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backup log not found.",
        )

    if log.status != "completed" or not log.storage_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Backup file is not available or failed.",
        )

    # 2. Get object from MinIO
    settings = get_settings()
    minio_client = build_minio_client(settings)

    try:
        minio_response = minio_client.get_object(
            bucket_name=settings.minio_bucket,
            object_name=log.storage_path,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve backup from storage: {e}",
        ) from e

    def stream_file() -> typing.Generator[bytes, None, None]:
        try:
            # Read in 32KB chunks
            while chunk := minio_response.read(32 * 1024):
                yield chunk
        finally:
            minio_response.close()
            minio_response.release_conn()

    headers = {
        "Content-Disposition": f'attachment; filename="{log.filename}"',
        "Content-Length": str(log.file_size),
    }

    return StreamingResponse(
        stream_file(),
        media_type="application/x-gzip",
        headers=headers,
    )
