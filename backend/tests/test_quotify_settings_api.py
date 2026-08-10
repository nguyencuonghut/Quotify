from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.v1.quotify_settings import (
    get_audit_log_service,
    get_quotify_settings_service,
)
from app.auth.dependencies import get_current_user
from app.db.session import get_db_session
from app.models import Permission, QuotifySetting, Role, User, UserStatus


class MockSession:
    def __init__(self) -> None:
        self.committed = False

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, instance: object) -> None:
        pass


class MockAuditLogService:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def log_event(self, **kwargs: Any) -> None:
        self.events.append(kwargs)


class MockQuotifySettingsService:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.setting = QuotifySetting(
            id=uuid4(),
            singleton_key="default",
            import_tax_rate_percent=Decimal("0.00"),
            processing_cost_vnd_per_kg=Decimal("200.00"),
            created_at=now,
            updated_at=now,
        )

    async def get_or_create_settings(self) -> QuotifySetting:
        return self.setting

    async def update_quotify_settings(
        self,
        *,
        import_tax_rate_percent: Decimal,
        processing_cost_vnd_per_kg: Decimal,
        updated_by_id: object,
    ) -> QuotifySetting:
        self.setting.import_tax_rate_percent = import_tax_rate_percent
        self.setting.processing_cost_vnd_per_kg = processing_cost_vnd_per_kg
        self.setting.updated_by_id = updated_by_id  # type: ignore[assignment]
        return self.setting


@pytest.fixture
def override_dependencies(
    app: FastAPI,
) -> Generator[tuple[MockQuotifySettingsService, MockAuditLogService, MockSession], None, None]:
    permissions = [
        Permission(id=uuid4(), code="quotify_settings.read"),
        Permission(id=uuid4(), code="quotify_settings.update"),
    ]
    admin_role = Role(id=uuid4(), name="settings-admin", is_system=False)
    admin_role.permissions = permissions
    admin_user = User(id=uuid4(), email="admin@example.com", status=UserStatus.ACTIVE)
    admin_user.roles = [admin_role]

    settings_service = MockQuotifySettingsService()
    audit_service = MockAuditLogService()
    session = MockSession()

    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[get_quotify_settings_service] = lambda: settings_service
    app.dependency_overrides[get_audit_log_service] = lambda: audit_service
    app.dependency_overrides[get_db_session] = lambda: session

    yield settings_service, audit_service, session

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_quotify_settings_returns_both_parameters(
    client: AsyncClient,
    override_dependencies: tuple[MockQuotifySettingsService, MockAuditLogService, MockSession],
) -> None:
    _, _, session = override_dependencies

    response = await client.get("/api/v1/quotify-settings")

    assert response.status_code == 200
    body = response.json()
    assert body["import_tax_rate_percent"] == "0.00"
    assert body["processing_cost_vnd_per_kg"] == "200.00"
    assert session.committed is True


@pytest.mark.asyncio
async def test_update_quotify_settings_commits_and_logs_audit(
    client: AsyncClient,
    override_dependencies: tuple[MockQuotifySettingsService, MockAuditLogService, MockSession],
) -> None:
    _, audit_service, session = override_dependencies

    response = await client.put(
        "/api/v1/quotify-settings",
        json={"import_tax_rate_percent": "5.00", "processing_cost_vnd_per_kg": "250.50"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["import_tax_rate_percent"] == "5.00"
    assert body["processing_cost_vnd_per_kg"] == "250.50"
    assert session.committed is True
    assert audit_service.events[0]["action"] == "quotify_settings.updated"
    metadata = audit_service.events[0]["context"].metadata_json
    changes = {change["field"]: change for change in metadata["changes"]}
    assert changes["import_tax_rate_percent"]["old_value"] == "0.00"
    assert changes["import_tax_rate_percent"]["new_value"] == "5.00"
    assert changes["processing_cost_vnd_per_kg"]["old_value"] == "200.00"
    assert changes["processing_cost_vnd_per_kg"]["new_value"] == "250.50"
