from __future__ import annotations

import base64
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import AuditLog


@dataclass(slots=True, frozen=True)
class AuditLogListQuery:
    limit: int = 10
    cursor: str | None = None
    actor_user_id: UUID | None = None
    action: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    request_id: str | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None


@dataclass(slots=True, frozen=True)
class AuditLogListResult:
    items: Sequence[AuditLog]
    next_cursor: str | None
    total: int


class InvalidAuditLogCursorError(Exception):
    """Raised when an audit log cursor cannot be decoded."""


class AuditLogAdminService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_audit_logs(self, query: AuditLogListQuery) -> AuditLogListResult:
        limit = min(max(query.limit, 1), 100)
        stmt = select(AuditLog).options(selectinload(AuditLog.actor_user))
        stmt = self._apply_filters(stmt, query)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_stmt)
        total = int(total_result.scalar_one())

        if query.cursor:
            cursor_created_at, cursor_id = decode_audit_log_cursor(query.cursor)
            stmt = stmt.where(
                or_(
                    AuditLog.created_at < cursor_created_at,
                    and_(
                        AuditLog.created_at == cursor_created_at,
                        AuditLog.id < cursor_id,
                    ),
                ),
            )

        stmt = stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit + 1)
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())

        next_cursor = None
        if len(rows) > limit:
            rows = rows[:limit]
            last_row = rows[-1]
            next_cursor = encode_audit_log_cursor(
                created_at=last_row.created_at,
                audit_log_id=last_row.id,
            )

        return AuditLogListResult(items=rows, next_cursor=next_cursor, total=total)

    def _apply_filters(
        self,
        stmt: Select[tuple[AuditLog]],
        query: AuditLogListQuery,
    ) -> Select[tuple[AuditLog]]:
        if query.actor_user_id:
            stmt = stmt.where(AuditLog.actor_user_id == query.actor_user_id)
        if query.action:
            stmt = stmt.where(AuditLog.action == query.action)
        if query.entity_type:
            stmt = stmt.where(AuditLog.entity_type == query.entity_type)
        if query.entity_id:
            stmt = stmt.where(AuditLog.entity_id == query.entity_id)
        if query.request_id:
            stmt = stmt.where(AuditLog.request_id == query.request_id)
        if query.created_from:
            stmt = stmt.where(AuditLog.created_at >= query.created_from)
        if query.created_to:
            stmt = stmt.where(AuditLog.created_at < query.created_to)
        return stmt


def encode_audit_log_cursor(*, created_at: datetime, audit_log_id: UUID) -> str:
    payload = {
        "created_at": created_at.isoformat(),
        "id": str(audit_log_id),
    }
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8"))
    return encoded.decode("ascii").rstrip("=")


def decode_audit_log_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        padding = "=" * (-len(cursor) % 4)
        decoded = base64.urlsafe_b64decode(f"{cursor}{padding}".encode("ascii"))
        payload = json.loads(decoded.decode("utf-8"))
        created_at = datetime.fromisoformat(payload["created_at"])
        if created_at.tzinfo is None:
            raise ValueError("Audit log cursor created_at must include timezone.")
        return created_at, UUID(payload["id"])
    except Exception as exc:
        raise InvalidAuditLogCursorError("Invalid audit log cursor.") from exc
