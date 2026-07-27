from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from app.models import ExportJob, File, ImportJob
from app.services.job_admin import JobAdminService, JobNotFoundError


class FakeRedisPool:
    def __init__(self) -> None:
        self.enqueued: list[tuple[str, tuple[Any, ...]]] = []

    async def enqueue_job(self, task_name: str, *args: Any, **kwargs: Any) -> None:
        self.enqueued.append((task_name, args))


class FakeScalarResult:
    def __init__(self, value: object | None) -> None:
        self._value = value

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
        files: dict[Any, File] | None = None,
        import_jobs: dict[Any, ImportJob] | None = None,
        export_jobs: dict[Any, ExportJob] | None = None,
    ) -> None:
        self.files = files or {}
        self.import_jobs = import_jobs or {}
        self.export_jobs = export_jobs or {}
        self.added: list[object] = []
        self.flush_count = 0

    async def execute(self, statement: object) -> FakeScalarResult:
        compiled = str(statement)
        params = statement.compile().params  # type: ignore[attr-defined]

        if "count" in compiled:
            if "import_jobs" in compiled:
                return FakeScalarResult(len(self.import_jobs))
            return FakeScalarResult(len(self.export_jobs))

        if "id_1" in params:
            obj_id = params["id_1"]
            if "FROM files" in compiled:
                return FakeScalarResult(self.files.get(obj_id))
            elif "FROM import_jobs" in compiled:
                return FakeScalarResult(self.import_jobs.get(obj_id))
            elif "FROM export_jobs" in compiled:
                return FakeScalarResult(self.export_jobs.get(obj_id))

        if "FROM import_jobs" in compiled:
            return FakeScalarResult(list(self.import_jobs.values()))

        if "FROM export_jobs" in compiled:
            return FakeScalarResult(list(self.export_jobs.values()))

        raise AssertionError(f"Unexpected statement: {compiled}")

    def add(self, instance: object) -> None:
        self.added.append(instance)

    async def flush(self) -> None:
        self.flush_count += 1


@pytest.mark.asyncio
async def test_create_import_job_success() -> None:
    file_id = uuid4()
    user_id = uuid4()
    db_file = File(
        id=file_id,
        filename="users.csv",
        bucket="app",
        storage_path="x/users.csv",
        content_type="text/csv",
        size_bytes=100,
    )
    session = FakeAsyncSession(files={file_id: db_file})
    redis_pool = FakeRedisPool()

    service = JobAdminService(session, redis_pool=redis_pool)  # type: ignore[arg-type]
    job = await service.create_import_job(file_id=file_id, user_id=user_id)

    assert job.file_id == file_id
    assert job.status == "pending"
    assert job.created_by_id == user_id
    assert len(session.added) == 1
    assert len(redis_pool.enqueued) == 1
    assert redis_pool.enqueued[0] == ("import_users_task", (job.id,))


@pytest.mark.asyncio
async def test_create_import_job_missing_file() -> None:
    file_id = uuid4()
    user_id = uuid4()
    session = FakeAsyncSession()

    service = JobAdminService(session)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="not found"):
        await service.create_import_job(file_id=file_id, user_id=user_id)


@pytest.mark.asyncio
async def test_create_export_job_success() -> None:
    user_id = uuid4()
    session = FakeAsyncSession()
    redis_pool = FakeRedisPool()

    service = JobAdminService(session, redis_pool=redis_pool)  # type: ignore[arg-type]
    filters = {"status": "active"}
    job = await service.create_export_job(filters=filters, user_id=user_id)

    assert job.status == "pending"
    assert job.filters == filters
    assert job.created_by_id == user_id
    assert len(session.added) == 1
    assert len(redis_pool.enqueued) == 1
    assert redis_pool.enqueued[0] == ("export_users_task", (job.id,))


@pytest.mark.asyncio
async def test_get_import_job_by_id_success() -> None:
    job_id = uuid4()
    job = ImportJob(id=job_id, file_id=uuid4(), status="completed")
    session = FakeAsyncSession(import_jobs={job_id: job})

    service = JobAdminService(session)  # type: ignore[arg-type]
    fetched = await service.get_import_job_by_id(job_id)
    assert fetched.id == job_id
    assert fetched.status == "completed"


@pytest.mark.asyncio
async def test_get_import_job_by_id_not_found() -> None:
    session = FakeAsyncSession()
    service = JobAdminService(session)  # type: ignore[arg-type]

    with pytest.raises(JobNotFoundError):
        await service.get_import_job_by_id(uuid4())


@pytest.mark.asyncio
async def test_list_import_jobs() -> None:
    j1 = ImportJob(id=uuid4(), file_id=uuid4(), status="completed")
    j2 = ImportJob(id=uuid4(), file_id=uuid4(), status="processing")
    session = FakeAsyncSession(import_jobs={j1.id: j1, j2.id: j2})

    service = JobAdminService(session)  # type: ignore[arg-type]
    jobs, total = await service.list_import_jobs()
    assert total == 2
    assert len(jobs) == 2


@pytest.mark.asyncio
async def test_list_export_jobs() -> None:
    j1 = ExportJob(id=uuid4(), status="completed")
    session = FakeAsyncSession(export_jobs={j1.id: j1})

    service = JobAdminService(session)  # type: ignore[arg-type]
    jobs, total = await service.list_export_jobs()
    assert total == 1
    assert len(jobs) == 1
