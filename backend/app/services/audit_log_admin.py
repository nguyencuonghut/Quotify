from __future__ import annotations

import base64
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import AuditLog, Quote, Supplier, TelegramAccount, User


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
    # Nhãn "Đối tượng" tra từ DB cho dòng chỉ có id (phiếu, liên kết Telegram), khóa theo log.id.
    target_labels: dict[UUID, str] = field(default_factory=dict)


_QUOTE_ENTITY_TYPES = frozenset({"quote", "quote_version", "quote_line"})


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

        return AuditLogListResult(
            items=rows,
            next_cursor=next_cursor,
            total=total,
            target_labels=await self.resolve_target_labels(rows),
        )

    async def resolve_target_labels(self, rows: Sequence[AuditLog]) -> dict[UUID, str]:
        """Người đọc cần thấy "Phiếu #3599 · ADM0001" hoặc email, không phải id (1 truy vấn mỗi loại).

        Chỉ trả nhãn cho dòng tra được; dòng không tra được (đã xóa, id lạ) để giao diện tự xử lý.
        """
        quote_of: dict[UUID, UUID] = {}
        link_of: dict[UUID, UUID] = {}
        for row in rows:
            if row.entity_type in _QUOTE_ENTITY_TYPES:
                quote_id = _uuid(row.entity_id if row.entity_type == "quote" else None) or _uuid(
                    (row.metadata_json or {}).get("quote_id"),
                )
                if quote_id is not None:
                    quote_of[row.id] = quote_id
            elif row.entity_type == "telegram_account":
                account_id = _uuid(row.entity_id)
                if account_id is not None:
                    link_of[row.id] = account_id

        labels: dict[UUID, str] = {}
        if quote_of:
            found = {
                quote_id: f"Phiếu #{number} · {code}"
                for quote_id, number, code in (
                    await self.session.execute(
                        select(Quote.id, Quote.sequence_number, Supplier.code)
                        .join(Supplier, Supplier.id == Quote.supplier_id)
                        .where(Quote.id.in_(set(quote_of.values()))),
                    )
                ).all()
            }
            labels.update({log_id: found[q] for log_id, q in quote_of.items() if q in found})
        if link_of:
            emails = dict(
                (
                    await self.session.execute(
                        select(TelegramAccount.id, User.email)
                        .join(User, User.id == TelegramAccount.user_id)
                        .where(TelegramAccount.id.in_(set(link_of.values()))),
                    )
                ).all(),
            )
            labels.update({log_id: emails[a] for log_id, a in link_of.items() if a in emails})
        return labels

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


def _uuid(value: object) -> UUID | None:
    if not isinstance(value, str):
        return None
    try:
        return UUID(value)
    except ValueError:
        return None


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
