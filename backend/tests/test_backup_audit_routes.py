from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, time
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, HTTPException, status
from fastapi.routing import APIRoute
from starlette.requests import Request

from app.api.v1.backups import (
    create_backup_schedule,
    delete_backup_schedule,
    trigger_backup_now,
    update_backup_schedule,
)
from app.models import Permission, Role, User, UserStatus
from app.models.backup_log import BackupLog
from app.models.backup_schedule import BackupSchedule
from app.schemas.backup import BackupScheduleCreateRequest, BackupScheduleUpdateRequest
from app.services.audit_log import AuditLogContext
from app.services.backup_admin import BackupScheduleNotFoundError


class FakeSession:
    def __init__(self) -> None:
        self.commit_count = 0
        self.committed = False

    async def commit(self) -> None:
        self.commit_count += 1
        self.committed = True


class FakeAuditLogService:
    def __init__(self, *, fail: bool = False) -> None:
        self.events: list[dict[str, object]] = []
        self.fail = fail

    async def log_event(
        self,
        *,
        action: str,
        entity_type: str,
        context: AuditLogContext | None = None,
    ) -> None:
        if self.fail:
            raise RuntimeError("audit failed")
        self.events.append(
            {
                "action": action,
                "entity_type": entity_type,
                "context": context,
            }
        )


class FakeBackupAdminService:
    def __init__(self) -> None:
        self.logs: list[BackupLog] = []
        self.schedules: dict[UUID, BackupSchedule] = {}
        self.fail_next_schedule_lookup = False
        self.enqueued_backup_log_ids: list[UUID] = []
        self.enqueue_observed_committed_states: list[bool] = []
        self.session: FakeSession | None = None

    async def trigger_manual_backup(self, created_by_id: UUID) -> BackupLog:
        log = BackupLog(
            id=uuid4(),
            backup_type="manual",
            status="pending",
            created_by_id=created_by_id,
            started_at=datetime.now(UTC),
            created_at=datetime.now(UTC),
        )
        self.logs.append(log)
        return log

    async def enqueue_manual_backup(self, backup_log_id: UUID) -> bool:
        self.enqueued_backup_log_ids.append(backup_log_id)
        if self.session is not None:
            self.enqueue_observed_committed_states.append(self.session.committed)
        return True

    async def create_backup_schedule(self, **kwargs: Any) -> BackupSchedule:
        schedule = BackupSchedule(
            id=uuid4(),
            name=kwargs["name"],
            frequency=kwargs["frequency"],
            time_of_day=kwargs["time_of_day"],
            day_of_week=kwargs["day_of_week"],
            one_off_datetime=kwargs["one_off_datetime"],
            is_active=kwargs["is_active"],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self.schedules[schedule.id] = schedule
        return schedule

    async def update_backup_schedule(
        self,
        *,
        schedule_id: UUID,
        **kwargs: Any,
    ) -> BackupSchedule:
        schedule = self.schedules.get(schedule_id)
        if schedule is None:
            raise BackupScheduleNotFoundError(f"Backup schedule {schedule_id} not found.")

        schedule.name = kwargs["name"]
        schedule.frequency = kwargs["frequency"]
        schedule.time_of_day = kwargs["time_of_day"]
        schedule.day_of_week = kwargs["day_of_week"]
        schedule.one_off_datetime = kwargs["one_off_datetime"]
        schedule.is_active = kwargs["is_active"]
        schedule.updated_at = datetime.now(UTC)
        return schedule

    async def delete_backup_schedule(self, schedule_id: UUID) -> BackupSchedule:
        schedule = self.schedules.get(schedule_id)
        if schedule is None:
            raise BackupScheduleNotFoundError(f"Backup schedule {schedule_id} not found.")
        return self.schedules.pop(schedule_id)


def build_request(path: str = "/api/v1/backups/now") -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": path,
            "headers": [(b"x-forwarded-for", b"203.0.113.10")],
            "client": ("127.0.0.1", 12345),
        }
    )


def build_user() -> User:
    return User(
        id=uuid4(),
        email="admin@example.com",
        status=UserStatus.ACTIVE,
        full_name="System Administrator",
    )


def build_user_with_permissions(permission_codes: list[str]) -> User:
    permissions = [Permission(id=uuid4(), code=code) for code in permission_codes]
    role = Role(id=uuid4(), name="custom_role", is_system=False)
    role.permissions = permissions
    user = build_user()
    user.roles = [role]
    return user


def get_route_permission_dependency(
    app: FastAPI,
    *,
    path: str,
    method: str,
) -> Callable[..., Awaitable[User]]:
    route = next(
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path == path and method in route.methods
    )
    permission_dependencies = [
        dependency.call
        for dependency in route.dependant.dependencies
        if getattr(dependency.call, "__qualname__", "") == "require_permission.<locals>.dependency"
    ]
    assert len(permission_dependencies) == 1
    return cast(Callable[..., Awaitable[User]], permission_dependencies[0])


def assert_audit_context(
    context: object,
    *,
    actor_user_id: UUID,
    entity_id: str,
    metadata_json: dict[str, object],
) -> None:
    assert isinstance(context, AuditLogContext)
    assert context.actor_user_id == actor_user_id
    assert context.entity_id == entity_id
    assert context.ip_address == "203.0.113.10"
    assert context.metadata_json == metadata_json


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/v1/backups/now"),
        ("POST", "/api/v1/backups/schedules"),
        ("PUT", "/api/v1/backups/schedules/{schedule_id}"),
        ("DELETE", "/api/v1/backups/schedules/{schedule_id}"),
    ],
)
@pytest.mark.asyncio
async def test_backup_mutation_routes_require_backups_write_permission(
    app: FastAPI,
    method: str,
    path: str,
) -> None:
    permission_dependency = get_route_permission_dependency(app, path=path, method=method)
    closure_values = {
        cell.cell_contents for cell in (getattr(permission_dependency, "__closure__", None) or ())
    }

    assert "backups.write" in closure_values

    with pytest.raises(HTTPException) as exc_info:
        await permission_dependency(current_user=build_user_with_permissions(["backups.read"]))

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_trigger_backup_now_logs_audit_event_and_commits_once() -> None:
    service = FakeBackupAdminService()
    audit_service = FakeAuditLogService()
    session = FakeSession()
    current_user = build_user()
    service.session = session

    response = await trigger_backup_now(
        request=build_request(),
        service=service,  # type: ignore[arg-type]
        current_user=current_user,
        audit_log_service=audit_service,  # type: ignore[arg-type]
        session=session,  # type: ignore[arg-type]
    )

    assert response.backup_type == "manual"
    assert response.status == "pending"
    assert session.commit_count == 1
    assert service.enqueued_backup_log_ids == [response.id]
    assert service.enqueue_observed_committed_states == [True]
    assert audit_service.events[0]["action"] == "backups.manual_backup_triggered"
    assert audit_service.events[0]["entity_type"] == "backup_log"
    assert_audit_context(
        audit_service.events[0]["context"],
        actor_user_id=current_user.id,
        entity_id=str(response.id),
        metadata_json={
            "backup_log_id": str(response.id),
            "status": "pending",
            "outcome": "triggered",
        },
    )


@pytest.mark.asyncio
async def test_trigger_backup_now_does_not_enqueue_when_audit_fails() -> None:
    service = FakeBackupAdminService()
    audit_service = FakeAuditLogService(fail=True)
    session = FakeSession()

    with pytest.raises(RuntimeError, match="audit failed"):
        await trigger_backup_now(
            request=build_request(),
            service=service,  # type: ignore[arg-type]
            current_user=build_user(),
            audit_log_service=audit_service,  # type: ignore[arg-type]
            session=session,  # type: ignore[arg-type]
        )

    assert session.commit_count == 0
    assert service.enqueued_backup_log_ids == []


@pytest.mark.asyncio
async def test_create_backup_schedule_logs_audit_event_and_commits_once() -> None:
    service = FakeBackupAdminService()
    audit_service = FakeAuditLogService()
    session = FakeSession()
    current_user = build_user()

    response = await create_backup_schedule(
        request=build_request("/api/v1/backups/schedules"),
        payload=BackupScheduleCreateRequest(
            name="Daily backup",
            frequency="daily",
            time_of_day="02:00",
            is_active=True,
        ),
        service=service,  # type: ignore[arg-type]
        current_user=current_user,
        audit_log_service=audit_service,  # type: ignore[arg-type]
        session=session,  # type: ignore[arg-type]
    )

    assert response.name == "Daily backup"
    assert session.commit_count == 1
    assert audit_service.events[0]["action"] == "backups.schedule_created"
    assert audit_service.events[0]["entity_type"] == "backup_schedule"
    assert_audit_context(
        audit_service.events[0]["context"],
        actor_user_id=current_user.id,
        entity_id=str(response.id),
        metadata_json={
            "backup_schedule_id": str(response.id),
            "name": "Daily backup",
            "status": "active",
            "outcome": "created",
        },
    )


@pytest.mark.asyncio
async def test_update_backup_schedule_logs_audit_event_and_commits_once() -> None:
    schedule_id = uuid4()
    service = FakeBackupAdminService()
    service.schedules[schedule_id] = BackupSchedule(
        id=schedule_id,
        name="Old schedule",
        frequency="daily",
        time_of_day=time(1, 0),
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    audit_service = FakeAuditLogService()
    session = FakeSession()
    current_user = build_user()

    response = await update_backup_schedule(
        schedule_id=schedule_id,
        request=build_request(f"/api/v1/backups/schedules/{schedule_id}"),
        payload=BackupScheduleUpdateRequest(
            name="Updated schedule",
            frequency="weekly",
            day_of_week=5,
            time_of_day="04:30",
            is_active=False,
        ),
        service=service,  # type: ignore[arg-type]
        current_user=current_user,
        audit_log_service=audit_service,  # type: ignore[arg-type]
        session=session,  # type: ignore[arg-type]
    )

    assert response.name == "Updated schedule"
    assert response.is_active is False
    assert session.commit_count == 1
    assert audit_service.events[0]["action"] == "backups.schedule_updated"
    assert audit_service.events[0]["entity_type"] == "backup_schedule"
    assert_audit_context(
        audit_service.events[0]["context"],
        actor_user_id=current_user.id,
        entity_id=str(schedule_id),
        metadata_json={
            "backup_schedule_id": str(schedule_id),
            "name": "Updated schedule",
            "status": "inactive",
            "outcome": "updated",
        },
    )


@pytest.mark.asyncio
async def test_update_backup_schedule_not_found_does_not_log_success_event() -> None:
    missing_schedule_id = uuid4()
    service = FakeBackupAdminService()
    audit_service = FakeAuditLogService()
    session = FakeSession()

    with pytest.raises(HTTPException) as exc_info:
        await update_backup_schedule(
            schedule_id=missing_schedule_id,
            request=build_request(f"/api/v1/backups/schedules/{missing_schedule_id}"),
            payload=BackupScheduleUpdateRequest(
                name="Missing schedule",
                frequency="daily",
                time_of_day="04:30",
                is_active=True,
            ),
            service=service,  # type: ignore[arg-type]
            current_user=build_user(),
            audit_log_service=audit_service,  # type: ignore[arg-type]
            session=session,  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert audit_service.events == []
    assert session.commit_count == 0


@pytest.mark.asyncio
async def test_delete_backup_schedule_logs_audit_event_and_returns_none() -> None:
    schedule_id = uuid4()
    service = FakeBackupAdminService()
    service.schedules[schedule_id] = BackupSchedule(
        id=schedule_id,
        name="Nightly backup",
        frequency="daily",
        time_of_day=time(2, 0),
        is_active=True,
    )
    audit_service = FakeAuditLogService()
    session = FakeSession()
    current_user = build_user()

    await delete_backup_schedule(
        schedule_id=schedule_id,
        request=build_request(f"/api/v1/backups/schedules/{schedule_id}"),
        service=service,  # type: ignore[arg-type]
        current_user=current_user,
        audit_log_service=audit_service,  # type: ignore[arg-type]
        session=session,  # type: ignore[arg-type]
    )

    assert schedule_id not in service.schedules
    assert session.commit_count == 1
    assert audit_service.events[0]["action"] == "backups.schedule_deleted"
    assert audit_service.events[0]["entity_type"] == "backup_schedule"
    assert_audit_context(
        audit_service.events[0]["context"],
        actor_user_id=current_user.id,
        entity_id=str(schedule_id),
        metadata_json={
            "backup_schedule_id": str(schedule_id),
            "name": "Nightly backup",
            "status": "active",
            "outcome": "deleted",
        },
    )


@pytest.mark.asyncio
async def test_delete_backup_schedule_not_found_does_not_log_success_event() -> None:
    missing_schedule_id = uuid4()
    service = FakeBackupAdminService()
    audit_service = FakeAuditLogService()
    session = FakeSession()

    with pytest.raises(HTTPException) as exc_info:
        await delete_backup_schedule(
            schedule_id=missing_schedule_id,
            request=build_request(f"/api/v1/backups/schedules/{missing_schedule_id}"),
            service=service,  # type: ignore[arg-type]
            current_user=build_user(),
            audit_log_service=audit_service,  # type: ignore[arg-type]
            session=session,  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert audit_service.events == []
    assert session.commit_count == 0
