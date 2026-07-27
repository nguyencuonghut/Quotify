from __future__ import annotations

from datetime import UTC, date, datetime, time
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_permission
from app.db.session import get_db_session
from app.models import AuditLog, User
from app.schemas import AuditLogListResponse, AuditLogResponse
from app.services.audit_log import sanitize_audit_metadata
from app.services.audit_log_admin import (
    AuditLogAdminService,
    AuditLogListQuery,
    InvalidAuditLogCursorError,
)

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])
BUSINESS_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


def get_audit_log_admin_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuditLogAdminService:
    return AuditLogAdminService(session)


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    current_user: Annotated[User, Depends(require_permission("audit.read"))],
    audit_log_admin_service: Annotated[
        AuditLogAdminService,
        Depends(get_audit_log_admin_service),
    ],
    limit: int = Query(default=10, ge=1, le=100),
    cursor: str | None = None,
    actor_user_id: UUID | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    request_id: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
) -> AuditLogListResponse:
    del current_user
    query = AuditLogListQuery(
        limit=limit,
        cursor=cursor,
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        request_id=request_id,
        created_from=_parse_audit_log_boundary(created_from),
        created_to=_parse_audit_log_boundary(created_to),
    )

    try:
        result = await audit_log_admin_service.list_audit_logs(query)
    except InvalidAuditLogCursorError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid audit log cursor.",
        ) from exc

    return AuditLogListResponse(
        items=[_build_audit_log_response(item) for item in result.items],
        next_cursor=result.next_cursor,
        total=result.total,
    )


def _build_audit_log_response(audit_log: AuditLog) -> AuditLogResponse:
    actor = audit_log.actor_user
    return AuditLogResponse(
        id=audit_log.id,
        actor_user_id=audit_log.actor_user_id,
        actor_email=actor.email if actor else None,
        action=audit_log.action,
        entity_type=audit_log.entity_type,
        entity_id=audit_log.entity_id,
        request_id=audit_log.request_id,
        ip_address=audit_log.ip_address,
        metadata=sanitize_audit_metadata(audit_log.metadata_json),
        created_at=audit_log.created_at,
    )


def _parse_audit_log_boundary(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        parsed_date = date.fromisoformat(value)
        local_dt = datetime.combine(parsed_date, time.min, tzinfo=BUSINESS_TIMEZONE)
        return local_dt.astimezone(UTC)
    except ValueError:
        pass

    try:
        parsed_datetime = datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid audit log datetime boundary.",
        ) from exc

    if parsed_datetime.tzinfo is None:
        parsed_datetime = parsed_datetime.replace(tzinfo=BUSINESS_TIMEZONE)
    return parsed_datetime.astimezone(UTC)
