from __future__ import annotations

from datetime import UTC, datetime, time
from uuid import UUID, uuid4

import pytest

from app.models.backup_log import BackupLog
from app.models.backup_schedule import BackupSchedule
from app.services.backup_admin import (
    BackupAdminService,
    BackupScheduleNotFoundError,
    calculate_next_run,
)


class FakeScalarResult:
    def __init__(self, value: object | None) -> None:
        self._value = value

    def scalar(self) -> object | None:
        return self._value

    def scalar_one_or_none(self) -> object | None:
        return self._value

    def scalar_one(self) -> object | None:
        return self._value

    def scalars(self) -> FakeScalarResult:
        return self

    def all(self) -> list[object]:
        if isinstance(self._value, list):
            return self._value
        if self._value is None:
            return []
        return [self._value]


class FakeAsyncSession:
    def __init__(
        self,
        *,
        logs: list[BackupLog] | None = None,
        schedules: list[BackupSchedule] | None = None,
    ) -> None:
        self.logs = logs or []
        self.schedules = schedules or []
        self.added: list[object] = []
        self.deleted: list[object] = []
        self.flush_count = 0
        self.committed = False

    async def execute(self, statement: object) -> FakeScalarResult:
        compiled = str(statement)

        if "count" in compiled:
            return FakeScalarResult(len(self.logs))

        if "FROM backup_logs" in compiled:
            return FakeScalarResult(self.logs)

        if "FROM backup_schedules" in compiled:
            if "WHERE" in compiled:
                compiled_stmt = getattr(statement, "compile", None)
                params = compiled_stmt().params if compiled_stmt else {}
                for val in params.values():
                    if isinstance(val, UUID):
                        for s in self.schedules:
                            if s.id == val:
                                return FakeScalarResult(s)
                return FakeScalarResult(None)
            return FakeScalarResult(self.schedules)

        raise AssertionError(f"Unexpected statement: {compiled}")

    def add(self, instance: object) -> None:
        self.added.append(instance)
        if isinstance(instance, BackupSchedule):
            self.schedules.append(instance)
        elif isinstance(instance, BackupLog):
            self.logs.append(instance)

    async def delete(self, instance: object) -> None:
        self.deleted.append(instance)
        if isinstance(instance, BackupSchedule) and instance in self.schedules:
            self.schedules.remove(instance)
        elif isinstance(instance, BackupLog) and instance in self.logs:
            self.logs.remove(instance)

    async def flush(self) -> None:
        self.flush_count += 1

    async def commit(self) -> None:
        self.committed = True


class FakeRedisPool:
    def __init__(self) -> None:
        self.jobs: list[tuple[str, UUID]] = []

    async def enqueue_job(self, job_name: str, backup_log_id: UUID) -> None:
        self.jobs.append((job_name, backup_log_id))


@pytest.mark.asyncio
async def test_get_backup_logs() -> None:
    log1 = BackupLog(id=uuid4(), backup_type="manual", status="completed")
    session = FakeAsyncSession(logs=[log1])
    service = BackupAdminService(session)  # type: ignore[arg-type]

    logs, total = await service.get_backup_logs()
    assert len(logs) == 1
    assert total == 1
    assert logs[0].backup_type == "manual"


@pytest.mark.asyncio
async def test_get_backup_schedules() -> None:
    sched1 = BackupSchedule(
        id=uuid4(), name="Daily night", frequency="daily", time_of_day=time(2, 0)
    )
    session = FakeAsyncSession(schedules=[sched1])
    service = BackupAdminService(session)  # type: ignore[arg-type]

    schedules = await service.get_backup_schedules()
    assert len(schedules) == 1
    assert schedules[0].frequency == "daily"


@pytest.mark.asyncio
async def test_create_backup_schedule() -> None:
    session = FakeAsyncSession()
    service = BackupAdminService(session)  # type: ignore[arg-type]

    schedule = await service.create_backup_schedule(
        name="Daily Backup",
        frequency="daily",
        time_of_day=time(3, 30),
        is_active=True,
    )

    assert schedule.name == "Daily Backup"
    assert schedule.frequency == "daily"
    assert schedule.time_of_day == time(3, 30)
    assert schedule.next_run_at is not None
    assert schedule.is_active is True
    assert schedule in session.schedules
    assert session.flush_count == 1
    assert session.committed is False


@pytest.mark.asyncio
async def test_update_backup_schedule() -> None:
    schedule_id = uuid4()
    sched1 = BackupSchedule(
        id=schedule_id,
        name="Old Name",
        frequency="daily",
        time_of_day=time(2, 0),
        is_active=True,
    )
    session = FakeAsyncSession(schedules=[sched1])
    service = BackupAdminService(session)  # type: ignore[arg-type]

    updated = await service.update_backup_schedule(
        schedule_id=schedule_id,
        name="New Name",
        frequency="weekly",
        time_of_day=time(4, 0),
        day_of_week=0,
        is_active=False,
    )

    assert updated.name == "New Name"
    assert updated.frequency == "weekly"
    assert updated.time_of_day == time(4, 0)
    assert updated.day_of_week == 0
    assert updated.is_active is False
    assert updated.next_run_at is not None
    assert session.flush_count == 1
    assert session.committed is False


@pytest.mark.asyncio
async def test_update_backup_schedule_not_found() -> None:
    session = FakeAsyncSession()
    service = BackupAdminService(session)  # type: ignore[arg-type]

    with pytest.raises(BackupScheduleNotFoundError):
        await service.update_backup_schedule(
            schedule_id=uuid4(),
            name="New Name",
            frequency="daily",
            time_of_day=time(4, 0),
        )


@pytest.mark.asyncio
async def test_delete_backup_schedule() -> None:
    schedule_id = uuid4()
    sched1 = BackupSchedule(
        id=schedule_id,
        name="To Delete",
        frequency="daily",
        time_of_day=time(2, 0),
    )
    session = FakeAsyncSession(schedules=[sched1])
    service = BackupAdminService(session)  # type: ignore[arg-type]

    await service.delete_backup_schedule(schedule_id)
    assert len(session.schedules) == 0
    assert session.flush_count == 1
    assert session.committed is False


@pytest.mark.asyncio
async def test_delete_backup_schedule_not_found() -> None:
    session = FakeAsyncSession()
    service = BackupAdminService(session)  # type: ignore[arg-type]

    with pytest.raises(BackupScheduleNotFoundError):
        await service.delete_backup_schedule(uuid4())


@pytest.mark.asyncio
async def test_trigger_manual_backup() -> None:
    session = FakeAsyncSession()
    redis_pool = FakeRedisPool()
    service = BackupAdminService(session, redis_pool=redis_pool)  # type: ignore[arg-type]

    user_id = uuid4()
    log = await service.trigger_manual_backup(user_id)

    assert log.backup_type == "manual"
    assert log.status == "pending"
    assert log.created_by_id == user_id
    assert log in session.logs
    assert session.flush_count == 1
    assert session.committed is False
    assert redis_pool.jobs == []

    queued = await service.enqueue_manual_backup(log.id)

    assert queued is True
    assert redis_pool.jobs == [("run_backup_task", log.id)]


def test_calculate_next_run_daily() -> None:
    tz_name = "Asia/Ho_Chi_Minh"
    current = datetime(2026, 6, 11, 10, 0, 0, tzinfo=UTC)  # local 17:00:00

    # Scheduled for 18:00 today (local) -> should run today
    next_run = calculate_next_run("daily", time(18, 0), current_time=current, tz_name=tz_name)
    assert next_run is not None
    # 18:00 local is 11:00 UTC
    assert next_run.hour == 11
    assert next_run.day == 11

    # Scheduled for 16:00 today (local) -> has passed, should run tomorrow 16:00 local
    next_run = calculate_next_run("daily", time(16, 0), current_time=current, tz_name=tz_name)
    assert next_run is not None
    # 16:00 local is 9:00 UTC next day
    assert next_run.hour == 9
    assert next_run.day == 12
