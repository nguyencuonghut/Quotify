from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, time
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient

from app.api.v1.backups import get_audit_log_service, get_backup_admin_service
from app.auth.dependencies import get_current_user
from app.db.session import get_db_session
from app.models.backup_log import BackupLog
from app.models.backup_schedule import BackupSchedule
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User, UserStatus
from app.services.audit_log import AuditLogContext
from app.services.backup_admin import BackupScheduleNotFoundError


class MockSession:
    def __init__(self) -> None:
        self.commit_count = 0

    async def commit(self) -> None:
        self.commit_count += 1


class MockBackupAdminService:
    def __init__(
        self,
        logs: list[BackupLog] | None = None,
        schedules: list[BackupSchedule] | None = None,
    ) -> None:
        self.logs = logs or []
        self.schedules = {s.id: s for s in (schedules or [])}
        self.audit_events: list[dict[str, object]] = []
        self.enqueued_backup_log_ids: list[UUID] = []
        self.session = MockSession()

    async def get_backup_logs(
        self, limit: int = 10, offset: int = 0
    ) -> tuple[list[BackupLog], int]:
        return self.logs[offset : offset + limit], len(self.logs)

    async def get_backup_schedules(self) -> list[BackupSchedule]:
        return list(self.schedules.values())

    async def create_backup_schedule(
        self,
        name: str,
        frequency: str,
        time_of_day: time,
        day_of_week: int | None = None,
        one_off_datetime: datetime | None = None,
        is_active: bool = True,
    ) -> BackupSchedule:
        s = BackupSchedule(
            id=uuid4(),
            name=name,
            frequency=frequency,
            time_of_day=time_of_day,
            day_of_week=day_of_week,
            one_off_datetime=one_off_datetime,
            is_active=is_active,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self.schedules[s.id] = s
        return s

    async def update_backup_schedule(
        self,
        schedule_id: UUID,
        name: str,
        frequency: str,
        time_of_day: time,
        day_of_week: int | None = None,
        one_off_datetime: datetime | None = None,
        is_active: bool = True,
    ) -> BackupSchedule:
        s = self.schedules.get(schedule_id)
        if not s:
            raise BackupScheduleNotFoundError(f"Backup schedule {schedule_id} not found.")
        s.name = name
        s.frequency = frequency
        s.time_of_day = time_of_day
        s.day_of_week = day_of_week
        s.one_off_datetime = one_off_datetime
        s.is_active = is_active
        s.updated_at = datetime.now(UTC)
        return s

    async def delete_backup_schedule(self, schedule_id: UUID) -> BackupSchedule:
        if schedule_id not in self.schedules:
            raise BackupScheduleNotFoundError(f"Backup schedule {schedule_id} not found.")
        return self.schedules.pop(schedule_id)

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
        return True


class MockAuditLogService:
    def __init__(self, events: list[dict[str, object]]) -> None:
        self.events = events

    async def log_event(
        self,
        *,
        action: str,
        entity_type: str,
        context: AuditLogContext | None = None,
    ) -> None:
        self.events.append(
            {
                "action": action,
                "entity_type": entity_type,
                "context": context,
            }
        )


@pytest.fixture
def override_dependencies(app: FastAPI) -> Generator[MockBackupAdminService, None, None]:
    p1 = Permission(id=uuid4(), code="backups.read")
    p2 = Permission(id=uuid4(), code="backups.write")
    role_admin = Role(
        id=uuid4(),
        name="admin",
        is_system=True,
    )
    role_admin.permissions = [p1, p2]

    mock_user = User(
        id=uuid4(),
        email="admin@example.com",
        password_hash="hashed_password",
        full_name="System Administrator",
        status=UserStatus.ACTIVE,
    )
    mock_user.roles = [role_admin]
    mock_service = MockBackupAdminService()
    mock_audit_service = MockAuditLogService(mock_service.audit_events)

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_backup_admin_service] = lambda: mock_service
    app.dependency_overrides[get_audit_log_service] = lambda: mock_audit_service
    app.dependency_overrides[get_db_session] = lambda: mock_service.session

    yield mock_service

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_list_backup_logs(
    app: FastAPI, client: AsyncClient, override_dependencies: MockBackupAdminService
) -> None:
    log1 = BackupLog(
        id=uuid4(),
        backup_type="manual",
        status="completed",
        started_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )
    override_dependencies.logs.append(log1)

    response = await client.get("/api/v1/backups")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["backup_type"] == "manual"
    assert data["items"][0]["status"] == "completed"


@pytest.mark.asyncio
async def test_api_trigger_backup_now(
    app: FastAPI, client: AsyncClient, override_dependencies: MockBackupAdminService
) -> None:
    response = await client.post("/api/v1/backups/now")
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["backup_type"] == "manual"
    assert data["status"] == "pending"
    assert len(override_dependencies.logs) == 1
    assert override_dependencies.session.commit_count == 1
    assert override_dependencies.enqueued_backup_log_ids == [UUID(data["id"])]
    assert override_dependencies.audit_events[0]["action"] == ("backups.manual_backup_triggered")
    assert override_dependencies.audit_events[0]["entity_type"] == "backup_log"
    context = override_dependencies.audit_events[0]["context"]
    assert isinstance(context, AuditLogContext)
    assert context.entity_id == data["id"]
    assert context.metadata_json == {
        "backup_log_id": data["id"],
        "status": "pending",
        "outcome": "triggered",
    }


@pytest.mark.asyncio
async def test_api_list_backup_schedules(
    app: FastAPI, client: AsyncClient, override_dependencies: MockBackupAdminService
) -> None:
    sched = BackupSchedule(
        id=uuid4(),
        name="Nightly backup",
        frequency="daily",
        time_of_day=time(2, 0),
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    override_dependencies.schedules[sched.id] = sched

    response = await client.get("/api/v1/backups/schedules")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Nightly backup"
    assert data[0]["frequency"] == "daily"


@pytest.mark.asyncio
async def test_api_create_backup_schedule(
    app: FastAPI, client: AsyncClient, override_dependencies: MockBackupAdminService
) -> None:
    payload = {
        "name": "Weekly Saturday Backup",
        "frequency": "weekly",
        "day_of_week": 5,
        "time_of_day": "23:00",
        "is_active": True,
    }

    response = await client.post("/api/v1/backups/schedules", json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["name"] == "Weekly Saturday Backup"
    assert data["frequency"] == "weekly"
    assert data["day_of_week"] == 5
    assert data["time_of_day"] == "23:00:00"
    assert len(override_dependencies.schedules) == 1
    assert override_dependencies.session.commit_count == 1
    assert override_dependencies.audit_events[0]["action"] == "backups.schedule_created"
    assert override_dependencies.audit_events[0]["entity_type"] == "backup_schedule"
    context = override_dependencies.audit_events[0]["context"]
    assert isinstance(context, AuditLogContext)
    assert context.entity_id == data["id"]
    assert context.metadata_json == {
        "backup_schedule_id": data["id"],
        "name": "Weekly Saturday Backup",
        "status": "active",
        "outcome": "created",
    }


@pytest.mark.asyncio
async def test_api_update_backup_schedule(
    app: FastAPI, client: AsyncClient, override_dependencies: MockBackupAdminService
) -> None:
    schedule_id = uuid4()
    sched = BackupSchedule(
        id=schedule_id,
        name="Weekly Saturday Backup",
        frequency="weekly",
        day_of_week=5,
        time_of_day=time(23, 0),
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    override_dependencies.schedules[schedule_id] = sched

    payload = {
        "name": "Updated Schedule Name",
        "frequency": "daily",
        "time_of_day": "04:30",
        "is_active": False,
    }

    response = await client.put(f"/api/v1/backups/schedules/{schedule_id}", json=payload)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["name"] == "Updated Schedule Name"
    assert data["frequency"] == "daily"
    assert data["day_of_week"] is None
    assert data["time_of_day"] == "04:30:00"
    assert data["is_active"] is False
    assert override_dependencies.session.commit_count == 1
    assert override_dependencies.audit_events[0]["action"] == "backups.schedule_updated"
    assert override_dependencies.audit_events[0]["entity_type"] == "backup_schedule"
    context = override_dependencies.audit_events[0]["context"]
    assert isinstance(context, AuditLogContext)
    assert context.entity_id == str(schedule_id)
    assert context.metadata_json == {
        "backup_schedule_id": str(schedule_id),
        "name": "Updated Schedule Name",
        "status": "inactive",
        "outcome": "updated",
    }


@pytest.mark.asyncio
async def test_api_update_backup_schedule_not_found(
    app: FastAPI, client: AsyncClient, override_dependencies: MockBackupAdminService
) -> None:
    payload = {
        "name": "Updated Schedule Name",
        "frequency": "daily",
        "time_of_day": "04:30",
        "is_active": False,
    }

    random_id = uuid4()
    response = await client.put(f"/api/v1/backups/schedules/{random_id}", json=payload)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert override_dependencies.audit_events == []
    assert override_dependencies.session.commit_count == 0


@pytest.mark.asyncio
async def test_api_delete_backup_schedule(
    app: FastAPI, client: AsyncClient, override_dependencies: MockBackupAdminService
) -> None:
    schedule_id = uuid4()
    sched = BackupSchedule(
        id=schedule_id,
        name="Nightly backup",
        frequency="daily",
        time_of_day=time(2, 0),
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    override_dependencies.schedules[schedule_id] = sched

    response = await client.delete(f"/api/v1/backups/schedules/{schedule_id}")
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert response.content == b""
    assert len(override_dependencies.schedules) == 0
    assert override_dependencies.session.commit_count == 1
    assert override_dependencies.audit_events[0]["action"] == "backups.schedule_deleted"
    assert override_dependencies.audit_events[0]["entity_type"] == "backup_schedule"
    context = override_dependencies.audit_events[0]["context"]
    assert isinstance(context, AuditLogContext)
    assert context.entity_id == str(schedule_id)
    assert context.metadata_json == {
        "backup_schedule_id": str(schedule_id),
        "name": "Nightly backup",
        "status": "active",
        "outcome": "deleted",
    }


@pytest.mark.asyncio
async def test_api_delete_backup_schedule_not_found(
    app: FastAPI, client: AsyncClient, override_dependencies: MockBackupAdminService
) -> None:
    random_id = uuid4()
    response = await client.delete(f"/api/v1/backups/schedules/{random_id}")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert override_dependencies.audit_events == []
    assert override_dependencies.session.commit_count == 0
