from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: UUID
    actor_user_id: UUID | None = None
    actor_email: str | None = None
    action: str
    entity_type: str
    entity_id: str | None = None
    request_id: str | None = None
    ip_address: str | None = None
    metadata: dict[str, Any] | None = None
    # Nhãn đối tượng tra từ DB (ví dụ "Phiếu #3599 · ADM0001"); None thì giao diện tự dựng.
    target_label: str | None = None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    next_cursor: str | None = None
    total: int
