from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException, status
from fastapi.routing import APIRoute

from app.api.v1.audit_logs import list_audit_logs
from app.auth.permissions import has_permission
from app.models import AuditLog, Permission, Role, User, UserStatus
from app.services.audit_log import REDACTED_METADATA_VALUE
from app.services.audit_log_admin import (
    AuditLogAdminService,
    AuditLogListQuery,
    AuditLogListResult,
)


class MockAuditLogAdminService:
    def __init__(self, audit_logs: Sequence[AuditLog]) -> None:
        self.audit_logs = audit_logs
        self.received_query: AuditLogListQuery | None = None

    async def list_audit_logs(self, query: AuditLogListQuery) -> AuditLogListResult:
        self.received_query = query
        return AuditLogListResult(
            items=self.audit_logs,
            next_cursor="next-cursor",
            total=len(self.audit_logs),
        )


def build_user_with_permissions(permission_codes: list[str]) -> User:
    permissions = [Permission(id=uuid4(), code=code) for code in permission_codes]
    role = Role(id=uuid4(), name="custom_role", is_system=False)
    role.permissions = permissions
    user = User(
        id=uuid4(),
        email="auditor@example.com",
        status=UserStatus.ACTIVE,
        full_name="Auditor",
    )
    user.roles = [role]
    return user


@pytest.fixture
def audit_log_service() -> MockAuditLogAdminService:
    actor = User(
        id=uuid4(),
        email="actor@example.com",
        status=UserStatus.ACTIVE,
        full_name="Actor",
    )
    audit_log = AuditLog(
        id=uuid4(),
        actor_user_id=actor.id,
        action="users.user_updated",
        entity_type="user",
        entity_id=str(uuid4()),
        request_id="req-123",
        ip_address="127.0.0.1",
        metadata_json={
            "email": "target@example.com",
            "access_token": "secret-token",
            "nested": {"authorization": "Bearer secret"},
            "items": [{"signed_url": "https://example.com/download?sig=secret"}],
        },
        created_at=datetime(2026, 7, 24, 8, 0, tzinfo=UTC),
    )
    audit_log.actor_user = actor
    return MockAuditLogAdminService([audit_log])


@pytest.mark.asyncio
async def test_list_audit_logs_api_success(
    audit_log_service: MockAuditLogAdminService,
) -> None:
    current_user = build_user_with_permissions(["audit.read"])

    response = await list_audit_logs(
        current_user=current_user,
        audit_log_admin_service=cast(AuditLogAdminService, audit_log_service),
    )

    assert response.total == 1
    assert response.next_cursor == "next-cursor"
    assert response.items[0].actor_email == "actor@example.com"
    assert response.items[0].action == "users.user_updated"
    assert response.items[0].metadata == {
        "email": "target@example.com",
        "access_token": REDACTED_METADATA_VALUE,
        "nested": {"authorization": REDACTED_METADATA_VALUE},
        "items": [{"signed_url": REDACTED_METADATA_VALUE}],
    }


@pytest.mark.asyncio
async def test_list_audit_logs_permission_policy_requires_audit_read() -> None:
    current_user = build_user_with_permissions(["users.read"])

    assert has_permission(current_user, "users.read") is True
    assert has_permission(current_user, "audit.read") is False


@pytest.mark.asyncio
async def test_list_audit_logs_maps_filters_to_query(
    audit_log_service: MockAuditLogAdminService,
) -> None:
    current_user = build_user_with_permissions(["audit.read"])
    actor_user_id = uuid4()
    response = await list_audit_logs(
        current_user=current_user,
        audit_log_admin_service=cast(AuditLogAdminService, audit_log_service),
        limit=20,
        cursor="cursor-value",
        actor_user_id=actor_user_id,
        action="users.user_updated",
        entity_type="user",
        entity_id="entity-123",
        request_id="req-123",
        created_from="2026-07-24",
        created_to="2026-07-25",
    )

    assert response.total == 1
    received_query = audit_log_service.received_query
    assert received_query is not None
    assert received_query.limit == 20
    assert received_query.cursor == "cursor-value"
    assert received_query.actor_user_id == actor_user_id
    assert received_query.action == "users.user_updated"
    assert received_query.entity_type == "user"
    assert received_query.entity_id == "entity-123"
    assert received_query.request_id == "req-123"
    assert received_query.created_from == datetime(2026, 7, 23, 17, 0, tzinfo=UTC)
    assert received_query.created_to == datetime(2026, 7, 24, 17, 0, tzinfo=UTC)


def test_audit_logs_route_is_read_only_and_permission_gated(app: FastAPI) -> None:
    audit_routes = [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path == "/api/v1/audit-logs"
    ]

    assert len(audit_routes) == 1
    assert audit_routes[0].methods == {"GET"}
    dependency_qualnames = {
        getattr(dependency.call, "__qualname__", "")
        for dependency in audit_routes[0].dependant.dependencies
    }
    assert "require_permission.<locals>.dependency" in dependency_qualnames
    permission_dependency = audit_routes[0].dependant.dependencies[0].call
    closure_values = {
        cell.cell_contents for cell in (getattr(permission_dependency, "__closure__", None) or ())
    }
    assert "audit.read" in closure_values


@pytest.mark.asyncio
async def test_audit_logs_permission_dependency_denies_user_without_audit_read(
    app: FastAPI,
) -> None:
    audit_route = next(
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path == "/api/v1/audit-logs"
    )
    permission_dependency = cast(
        Callable[..., Awaitable[User]],
        audit_route.dependant.dependencies[0].call,
    )
    user = build_user_with_permissions(["users.read"])

    with pytest.raises(HTTPException) as exc_info:
        await permission_dependency(current_user=user)

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
