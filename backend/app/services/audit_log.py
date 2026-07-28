from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.core.client_ip import resolve_client_ip
from app.core.config import get_settings
from app.core.request_id import request_id_context
from app.models import AuditLog, User

SENSITIVE_METADATA_KEY_PARTS = (
    "api_key",
    "password",
    "token",
    "secret",
    "cookie",
    "authorization",
    "session",
    "credential",
    "signed_url",
)
REDACTED_METADATA_VALUE = "[REDACTED]"
ALLOWED_AUDIT_METADATA_KEYS = frozenset(
    {
        "backup_log_id",
        "backup_schedule_id",
        "changes",
        "content_type",
        "description",
        "email",
        "error_category",
        "error_summary",
        "failed_rows",
        "file_id",
        "field",
        "filename",
        "filters",
        "has_refresh_cookie",
        "label",
        "backup_type",
        "address",
        "code",
        "conversion_cost_vnd_per_kg",
        "contact_count",
        "created_rows",
        "import_job_id",
        "import_entity_type",
        "export_job_id",
        "is_public",
        "items",
        "material_codes",
        "material_count",
        "material_names",
        "supplier_type",
        "tax_code",
        "name",
        "nested",
        "outcome",
        "permission_codes",
        "permissions",
        "processed_rows",
        "purpose",
        "role_names",
        "row_count",
        "rate",
        "retrieved_at",
        "search",
        "size_bytes",
        "status",
        "source",
        "summary",
        "total_rows",
        "updated_rows",
        "old_value",
        "new_value",
    }
)


@dataclass(slots=True, frozen=True)
class AuditLogContext:
    actor_user_id: UUID | None = None
    entity_id: str | None = None
    ip_address: str | None = None
    metadata_json: dict[str, object] | None = None
    request_id: str | None = None

    @classmethod
    def from_request(
        cls,
        *,
        request: Request,
        current_user: User | None = None,
        actor_user_id: UUID | None = None,
        entity_id: str | None = None,
        metadata_json: dict[str, object] | None = None,
        request_id: str | None = None,
    ) -> AuditLogContext:
        resolved_actor_user_id = actor_user_id
        if resolved_actor_user_id is None and current_user is not None:
            resolved_actor_user_id = current_user.id
        return cls(
            actor_user_id=resolved_actor_user_id,
            entity_id=entity_id,
            ip_address=get_client_ip_from_request(request),
            metadata_json=metadata_json,
            request_id=request_id or request_id_context.get() or None,
        )


class AuditLogService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def log_event(
        self,
        *,
        action: str,
        entity_type: str,
        context: AuditLogContext | None = None,
    ) -> AuditLog:
        resolved_context = context or AuditLogContext()
        audit_log = AuditLog(
            actor_user_id=resolved_context.actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=resolved_context.entity_id,
            request_id=resolved_context.request_id or request_id_context.get() or None,
            ip_address=resolved_context.ip_address,
            metadata_json=sanitize_audit_metadata(resolved_context.metadata_json),
        )
        self.session.add(audit_log)
        await self.session.flush()
        return audit_log


def sanitize_audit_metadata(metadata: Mapping[str, object] | None) -> dict[str, object] | None:
    if metadata is None:
        return None
    return {key: _sanitize_metadata_entry(key, value) for key, value in metadata.items()}


def get_client_ip_from_request(request: Request) -> str | None:
    settings = get_settings()
    return resolve_client_ip(
        request,
        trusted_proxy_cidrs=settings.trusted_proxy_cidrs,
    )


def _sanitize_metadata_entry(key: str, value: object) -> object:
    normalized_key = _normalize_metadata_key(key)
    if _is_sensitive_metadata_key(normalized_key):
        return REDACTED_METADATA_VALUE
    if normalized_key not in ALLOWED_AUDIT_METADATA_KEYS:
        return REDACTED_METADATA_VALUE
    return _sanitize_value(value)


def _sanitize_value(value: object) -> object:
    if isinstance(value, dict):
        return {
            str(key): _sanitize_metadata_entry(str(key), nested_value)
            for key, nested_value in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    return value


def _is_sensitive_metadata_key(key: str) -> bool:
    normalized_key = _normalize_metadata_key(key)
    return any(part in normalized_key for part in SENSITIVE_METADATA_KEY_PARTS)


def _normalize_metadata_key(key: str) -> str:
    return key.lower().replace("-", "_")
