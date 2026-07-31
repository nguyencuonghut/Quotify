from __future__ import annotations

from uuid import uuid4

import pytest
from starlette.requests import Request

from app.core.request_id import request_id_context
from app.services.audit_log import (
    REDACTED_METADATA_VALUE,
    AuditLogContext,
    AuditLogService,
    sanitize_audit_metadata,
)


class FakeAsyncSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.flush_count = 0

    def add(self, instance: object) -> None:
        self.added.append(instance)

    async def flush(self) -> None:
        self.flush_count += 1


@pytest.mark.asyncio
async def test_log_event_persists_audit_record() -> None:
    session = FakeAsyncSession()
    service = AuditLogService(session)  # type: ignore[arg-type]
    actor_user_id = uuid4()

    audit_log = await service.log_event(
        action="auth.login_succeeded",
        entity_type="user",
        context=AuditLogContext(
            actor_user_id=actor_user_id,
            entity_id=str(actor_user_id),
            ip_address="127.0.0.1",
            metadata_json={
                "email": "admin@example.com",
                "refresh_token": "secret-token",
                "nested": {"authorization": "Bearer secret"},
            },
            request_id="req-123",
        ),
    )

    assert audit_log.actor_user_id == actor_user_id
    assert audit_log.action == "auth.login_succeeded"
    assert audit_log.entity_type == "user"
    assert audit_log.request_id == "req-123"
    assert audit_log.metadata_json == {
        "email": "admin@example.com",
        "refresh_token": REDACTED_METADATA_VALUE,
        "nested": {"authorization": REDACTED_METADATA_VALUE},
    }
    assert len(session.added) == 1
    assert session.flush_count == 1


@pytest.mark.asyncio
async def test_log_event_uses_request_id_context_when_context_has_no_request_id() -> None:
    session = FakeAsyncSession()
    service = AuditLogService(session)  # type: ignore[arg-type]
    token = request_id_context.set("req-from-middleware")
    try:
        audit_log = await service.log_event(
            action="auth.logout",
            entity_type="user",
            context=AuditLogContext(metadata_json={"has_refresh_cookie": True}),
        )
    finally:
        request_id_context.reset(token)

    assert audit_log.request_id == "req-from-middleware"


def build_request(
    *,
    forwarded_for: str | None = None,
    client_host: str | None = "10.0.0.10",
) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if forwarded_for is not None:
        headers.append((b"x-forwarded-for", forwarded_for.encode("latin-1")))
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/users",
        "headers": headers,
        "client": (client_host, 12345) if client_host is not None else None,
    }
    return Request(scope)


def test_audit_context_from_request_prefers_forwarded_for_from_trusted_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor_user_id = uuid4()
    request = build_request(
        forwarded_for="203.0.113.9, 10.0.0.10",
        client_host="172.30.0.12",
    )
    monkeypatch.setattr(
        "app.services.audit_log.get_settings",
        lambda: type("Settings", (), {"trusted_proxy_cidrs": "172.30.0.0/24"})(),
    )
    token = request_id_context.set("req-from-context")
    try:
        context = AuditLogContext.from_request(
            request=request,
            actor_user_id=actor_user_id,
            entity_id="entity-123",
            metadata_json={"email": "admin@example.com"},
        )
    finally:
        request_id_context.reset(token)

    assert context.actor_user_id == actor_user_id
    assert context.entity_id == "entity-123"
    assert context.ip_address == "203.0.113.9"
    assert context.request_id == "req-from-context"
    assert context.metadata_json == {"email": "admin@example.com"}


def test_audit_context_from_request_ignores_forwarded_for_from_untrusted_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = build_request(
        forwarded_for="203.0.113.9",
        client_host="192.168.10.25",
    )
    monkeypatch.setattr(
        "app.services.audit_log.get_settings",
        lambda: type("Settings", (), {"trusted_proxy_cidrs": "172.30.0.0/24"})(),
    )

    context = AuditLogContext.from_request(request=request)

    assert context.ip_address == "192.168.10.25"


def test_audit_context_from_request_uses_explicit_request_id() -> None:
    request = build_request(forwarded_for=None, client_host="10.0.0.11")

    context = AuditLogContext.from_request(
        request=request,
        request_id="req-explicit",
    )

    assert context.ip_address == "10.0.0.11"
    assert context.request_id == "req-explicit"


def test_sanitize_audit_metadata_redacts_sensitive_and_unapproved_keys() -> None:
    metadata = {
        "email": "admin@example.com",
        "password": "secret",
        "nested": {
            "status": "active",
            "api_key": "secret",
            "unexpected": "not allowed",
        },
        "filters": {
            "search": "nguyen",
            "authorization": "Bearer secret",
        },
        "items": [{"filename": "users.csv", "signed_url": "https://example.com?sig=secret"}],
        "unexpected": "not allowed",
    }

    assert sanitize_audit_metadata(metadata) == {
        "email": "admin@example.com",
        "password": REDACTED_METADATA_VALUE,
        "nested": {
            "status": "active",
            "api_key": REDACTED_METADATA_VALUE,
            "unexpected": REDACTED_METADATA_VALUE,
        },
        "filters": {
            "search": "nguyen",
            "authorization": REDACTED_METADATA_VALUE,
        },
        "items": [{"filename": "users.csv", "signed_url": REDACTED_METADATA_VALUE}],
        "unexpected": REDACTED_METADATA_VALUE,
    }


def test_sanitize_audit_metadata_preserves_backup_event_keys() -> None:
    metadata = {
        "backup_log_id": "log-1",
        "backup_schedule_id": "schedule-1",
        "backup_type": "manual",
        "name": "Nightly backup",
        "status": "pending",
        "outcome": "triggered",
    }

    assert sanitize_audit_metadata(metadata) == metadata


def test_sanitize_audit_metadata_preserves_user_change_summary_keys() -> None:
    metadata = {
        "email": "user@example.com",
        "outcome": "updated",
        "changes": [
            {
                "field": "avatar_url",
                "label": "Ảnh đại diện",
                "old_value": "/api/v1/files/old/download",
                "new_value": "/api/v1/files/new/download",
            }
        ],
    }

    assert sanitize_audit_metadata(metadata) == metadata


def test_sanitize_audit_metadata_preserves_supplier_catalog_keys() -> None:
    metadata = {
        "code": "SUP-001",
        "name": "Nhà cung cấp A",
        "supplier_type": "domestic",
        "tax_code": "0100100100",
        "address": "Hải Phòng",
        "contact_count": 2,
        "material_count": 3,
        "material_codes": ["CORN", "SOYBEAN_MEAL"],
        "material_names": ["Ngô hạt", "Khô dầu đậu nành"],
    }

    assert sanitize_audit_metadata(metadata) == metadata


def test_sanitize_audit_metadata_preserves_worker_lifecycle_keys() -> None:
    metadata = {
        "import_job_id": "import-1",
        "export_job_id": "export-1",
        "file_id": "file-1",
        "total_rows": 10,
        "processed_rows": 8,
        "failed_rows": 2,
        "size_bytes": 1024,
        "error_category": "export_failed",
        "error_summary": "Failed to export users.",
    }

    assert sanitize_audit_metadata(metadata) == metadata


def test_sanitize_audit_metadata_preserves_quote_draft_delete_keys() -> None:
    metadata = {
        "quote_id": "quote-1",
        "version_id": "version-1",
        "version_number": 2,
        "version_status": "draft",
        "received_date": "2026-07-31",
        "correction_reason": "Nhập sai giá.",
        "line_count": 5,
        "deleted_scope": "draft_version",
        "deleted_quote": False,
        "deleted_quote_id": None,
        "source_file_id": "file-1",
        "source_file_cleanup": "deleted",
    }

    assert sanitize_audit_metadata(metadata) == metadata
