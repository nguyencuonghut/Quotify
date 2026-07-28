from __future__ import annotations

import io
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.models import AuditLog, ExportJob, File, ImportJob, Role, User, UserStatus
from app.models.backup_log import BackupLog
from app.services.catalog_import import CatalogImportSummary
from app.worker import export_users_task, import_catalog_task, import_users_task, run_backup_task


class FakeMinioResponse:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self._offset = 0
        self.read_sizes: list[int] = []

    def read(self, size: int = -1) -> bytes:
        self.read_sizes.append(size)
        if size is None or size < 0:
            size = len(self.data) - self._offset
        chunk = self.data[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk

    def close(self) -> None:
        pass

    def release_conn(self) -> None:
        pass


class FakeCompletedProcess:
    returncode = 0

    async def communicate(self) -> tuple[bytes, bytes]:
        return b"postgres dump", b""


class FakeEmailService:
    sent_notifications: list[dict[str, object]] = []
    fail_success = False

    def __init__(self, settings: object) -> None:
        self.settings = settings

    async def send_backup_notification(self, **kwargs: object) -> None:
        if self.fail_success and kwargs.get("status") == "success":
            raise RuntimeError("smtp secret failure")
        self.sent_notifications.append(kwargs)


class FakeNestedTransaction:
    async def __aenter__(self) -> FakeNestedTransaction:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is not None:
            raise exc_val


class FakeAsyncSession:
    def __init__(
        self,
        *,
        import_job: ImportJob | None = None,
        export_job: ExportJob | None = None,
        backup_log: BackupLog | None = None,
        roles: list[Any] | None = None,
        users: list[User] | None = None,
    ) -> None:
        self.import_job = import_job
        self.export_job = export_job
        self.backup_log = backup_log
        self.roles = roles or []
        self.users = users or []
        self.added: list[object] = []
        self.commit_count = 0
        self.flush_count = 0

    async def execute(self, statement: object) -> MagicMock:
        compiled = str(statement)
        result = MagicMock()

        if "FROM import_jobs" in compiled:
            result.scalar_one_or_none.return_value = self.import_job
        elif "FROM export_jobs" in compiled:
            result.scalar_one_or_none.return_value = self.export_job
        elif "FROM backup_logs" in compiled:
            result.scalar_one_or_none.return_value = self.backup_log
        elif "FROM roles" in compiled:
            result.scalars.return_value.all.return_value = self.roles
        elif "FROM users" in compiled:
            # Simple mock for get_user_by_email
            params = statement.compile().params  # type: ignore[attr-defined]
            email = params.get("email_1")
            existing = None
            if email:
                for u in self.users:
                    if u.email == email:
                        existing = u
            result.scalar_one_or_none.return_value = existing
            result.scalars.return_value.all.return_value = self.users

        return result

    def add(self, instance: object) -> None:
        self.added.append(instance)

    async def commit(self) -> None:
        self.commit_count += 1

    async def flush(self) -> None:
        self.flush_count += 1

    def begin_nested(self) -> FakeNestedTransaction:
        return FakeNestedTransaction()

    async def __aenter__(self) -> FakeAsyncSession:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass


class FakeCatalogImportService:
    next_summary = CatalogImportSummary(
        total_rows=2,
        processed_rows=1,
        failed_rows=1,
        created_rows=1,
        updated_rows=0,
        errors=[{"row": 2, "code": "BAD", "errors": ["Tên là bắt buộc."]}],
    )
    received_fieldnames: list[str] | None = None

    def __init__(self, session: FakeAsyncSession) -> None:
        self.session = session

    async def import_rows(
        self,
        *,
        entity_type: str,
        rows: object,
        fieldnames: list[str] | None,
    ) -> CatalogImportSummary:
        self.received_fieldnames = fieldnames
        return self.next_summary


@pytest.mark.asyncio
async def test_import_users_task_success() -> None:
    job_id = uuid4()
    db_file = File(
        id=uuid4(),
        filename="import.csv",
        bucket="bucket",
        storage_path="x/import.csv",
        content_type="text/csv",
        size_bytes=100,
    )
    job = ImportJob(id=job_id, file_id=db_file.id, status="pending")
    job.file = db_file

    session = FakeAsyncSession(import_job=job, roles=[Role(id=uuid4(), name="user")])
    session_factory = MagicMock()
    session_factory.return_value = session

    minio_client = MagicMock()
    # CSV with 1 header, 2 rows (1 success, 1 failure due to short password)
    csv_data = (
        b"email,password,status,roles,full_name\n"
        b"success@example.com,pass12345,active,user,Success User\n"
        b"fail@example.com,short,active,user,Fail User"
    )
    minio_response = FakeMinioResponse(csv_data)
    minio_client.get_object.return_value = minio_response

    ctx = {
        "session_factory": session_factory,
        "minio_client": minio_client,
    }

    await import_users_task(ctx, job_id)

    assert job.status == "completed"
    assert job.total_rows == 2
    assert job.processed_rows == 1
    assert job.failed_rows == 1
    assert job.errors_json is not None
    assert len(job.errors_json) == 1
    assert job.errors_json[0]["email"] == "fail@example.com"
    assert "Password must be at least 8 characters" in job.errors_json[0]["errors"][0]
    audit_logs = [item for item in session.added if isinstance(item, AuditLog)]
    assert len(audit_logs) == 1
    assert audit_logs[0].action == "users.import_completed"
    assert audit_logs[0].entity_type == "import_job"
    assert audit_logs[0].entity_id == str(job_id)
    assert audit_logs[0].actor_user_id == job.created_by_id
    assert audit_logs[0].metadata_json == {
        "import_job_id": str(job_id),
        "file_id": str(db_file.id),
        "status": "completed",
        "outcome": "completed",
        "total_rows": 2,
        "processed_rows": 1,
        "failed_rows": 1,
    }
    assert minio_response.read_sizes
    assert all(size != -1 for size in minio_response.read_sizes)


@pytest.mark.asyncio
async def test_import_catalog_task_completes_with_partial_row_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = uuid4()
    db_file = File(
        id=uuid4(),
        filename="material_types.csv",
        bucket="bucket",
        storage_path="x/material_types.csv",
        content_type="text/csv",
        size_bytes=100,
    )
    job = ImportJob(
        id=job_id,
        file_id=db_file.id,
        entity_type="material_types",
        task_name="import_catalog_task",
        status="pending",
        created_by_id=uuid4(),
    )
    job.file = db_file

    session = FakeAsyncSession(import_job=job)
    session_factory = MagicMock()
    session_factory.return_value = session

    minio_client = MagicMock()
    minio_response = FakeMinioResponse(
        b"code,name,status,note\nGOOD,Hop le,active,\nBAD,,active,"
    )
    minio_client.get_object.return_value = minio_response
    monkeypatch.setattr("app.worker.CatalogImportService", FakeCatalogImportService)

    await import_catalog_task(
        {
            "session_factory": session_factory,
            "minio_client": minio_client,
        },
        job_id,
    )

    assert job.status == "completed"
    assert job.total_rows == 2
    assert job.processed_rows == 1
    assert job.failed_rows == 1
    assert job.errors_json == [{"row": 2, "code": "BAD", "errors": ["Tên là bắt buộc."]}]
    assert all(size != -1 for size in minio_response.read_sizes)
    audit_logs = [item for item in session.added if isinstance(item, AuditLog)]
    assert len(audit_logs) == 1
    assert audit_logs[0].action == "catalog.material_types_import_completed"
    assert audit_logs[0].metadata_json == {
        "import_job_id": str(job_id),
        "file_id": str(db_file.id),
        "import_entity_type": "material_types",
        "status": "completed",
        "outcome": "completed",
        "total_rows": 2,
        "processed_rows": 1,
        "failed_rows": 1,
        "created_rows": 1,
        "updated_rows": 0,
    }


@pytest.mark.asyncio
async def test_import_users_task_parse_failure_logs_audit_without_raw_error() -> None:
    job_id = uuid4()
    db_file = File(
        id=uuid4(),
        filename="import.csv",
        bucket="bucket",
        storage_path="x/import.csv",
        content_type="text/csv",
        size_bytes=100,
    )
    job = ImportJob(id=job_id, file_id=db_file.id, status="pending", created_by_id=uuid4())
    job.file = db_file

    session = FakeAsyncSession(import_job=job)
    session_factory = MagicMock()
    session_factory.return_value = session

    minio_client = MagicMock()
    minio_client.get_object.return_value = FakeMinioResponse(b"\xff")

    ctx = {
        "session_factory": session_factory,
        "minio_client": minio_client,
    }

    await import_users_task(ctx, job_id)

    assert job.status == "failed"
    assert job.error_summary is not None
    audit_logs = [item for item in session.added if isinstance(item, AuditLog)]
    assert len(audit_logs) == 1
    assert audit_logs[0].action == "users.import_failed"
    assert audit_logs[0].actor_user_id == job.created_by_id
    assert audit_logs[0].metadata_json == {
        "import_job_id": str(job_id),
        "file_id": str(db_file.id),
        "status": "failed",
        "outcome": "failed",
        "error_category": "csv_read_parse_failed",
        "error_summary": "Failed to read or parse import CSV.",
    }


@pytest.mark.asyncio
async def test_import_users_task_all_rows_failed_logs_failed_audit() -> None:
    job_id = uuid4()
    db_file = File(
        id=uuid4(),
        filename="import.csv",
        bucket="bucket",
        storage_path="x/import.csv",
        content_type="text/csv",
        size_bytes=100,
    )
    job = ImportJob(id=job_id, file_id=db_file.id, status="pending", created_by_id=uuid4())
    job.file = db_file

    session = FakeAsyncSession(import_job=job)
    session_factory = MagicMock()
    session_factory.return_value = session

    minio_client = MagicMock()
    minio_client.get_object.return_value = FakeMinioResponse(
        b"email,password,status,roles,full_name\ninvalid@example.com,short,active,user,"
    )

    ctx = {
        "session_factory": session_factory,
        "minio_client": minio_client,
    }

    await import_users_task(ctx, job_id)

    assert job.status == "failed"
    audit_logs = [item for item in session.added if isinstance(item, AuditLog)]
    assert len(audit_logs) == 1
    assert audit_logs[0].action == "users.import_failed"
    assert audit_logs[0].metadata_json == {
        "import_job_id": str(job_id),
        "file_id": str(db_file.id),
        "status": "failed",
        "outcome": "failed",
        "total_rows": 1,
        "processed_rows": 0,
        "failed_rows": 1,
        "error_category": "all_rows_failed",
        "error_summary": "All rows failed to import.",
    }


@pytest.mark.asyncio
async def test_import_users_task_processing_retry_can_complete_and_log_audit() -> None:
    job_id = uuid4()
    db_file = File(
        id=uuid4(),
        filename="import.csv",
        bucket="bucket",
        storage_path="x/import.csv",
        content_type="text/csv",
        size_bytes=100,
    )
    job = ImportJob(id=job_id, file_id=db_file.id, status="processing", created_by_id=uuid4())
    job.file = db_file

    session = FakeAsyncSession(import_job=job, roles=[Role(id=uuid4(), name="user")])
    session_factory = MagicMock()
    session_factory.return_value = session

    minio_client = MagicMock()
    minio_client.get_object.return_value = FakeMinioResponse(
        b"email,password,status,roles,full_name\n"
        b"success@example.com,pass12345,active,user,Success User"
    )

    ctx = {
        "session_factory": session_factory,
        "minio_client": minio_client,
    }

    await import_users_task(ctx, job_id)

    assert job.status == "completed"
    audit_logs = [item for item in session.added if isinstance(item, AuditLog)]
    assert [audit_log.action for audit_log in audit_logs] == ["users.import_completed"]


@pytest.mark.asyncio
async def test_export_users_task_success() -> None:
    job_id = uuid4()
    job = ExportJob(
        id=job_id,
        status="pending",
        created_by_id=uuid4(),
        filters={"status": "active"},
    )

    u1 = User(
        id=uuid4(),
        email="u1@example.com",
        status=UserStatus.ACTIVE,
        full_name="User One",
        created_at=MagicMock(),
    )
    u1.roles = []
    session = FakeAsyncSession(export_job=job, users=[u1])
    session_factory = MagicMock()
    session_factory.return_value = session

    minio_client = MagicMock()
    ctx = {
        "session_factory": session_factory,
        "minio_client": minio_client,
    }

    await export_users_task(ctx, job_id)

    assert job.status == "completed"
    assert job.file_id is not None
    # Verify minio upload was called
    assert minio_client.put_object.call_count == 1
    audit_logs = [item for item in session.added if isinstance(item, AuditLog)]
    assert len(audit_logs) == 1
    assert audit_logs[0].action == "users.export_completed"
    assert audit_logs[0].entity_type == "export_job"
    assert audit_logs[0].entity_id == str(job_id)
    assert audit_logs[0].actor_user_id == job.created_by_id
    assert audit_logs[0].metadata_json is not None
    assert audit_logs[0].metadata_json["export_job_id"] == str(job_id)
    assert audit_logs[0].metadata_json["file_id"] == str(job.file_id)
    assert audit_logs[0].metadata_json["status"] == "completed"
    assert audit_logs[0].metadata_json["outcome"] == "completed"
    assert audit_logs[0].metadata_json["total_rows"] == 1
    assert isinstance(audit_logs[0].metadata_json["size_bytes"], int)
    assert audit_logs[0].metadata_json["size_bytes"] > 0


@pytest.mark.asyncio
async def test_export_users_task_processing_retry_can_complete_and_log_audit() -> None:
    job_id = uuid4()
    job = ExportJob(
        id=job_id,
        status="processing",
        created_by_id=uuid4(),
        filters={"status": "active"},
    )
    user = User(
        id=uuid4(),
        email="u1@example.com",
        status=UserStatus.ACTIVE,
        full_name="User One",
        created_at=MagicMock(),
    )
    user.roles = []
    session = FakeAsyncSession(export_job=job, users=[user])
    session_factory = MagicMock()
    session_factory.return_value = session

    ctx = {
        "session_factory": session_factory,
        "minio_client": MagicMock(),
    }

    await export_users_task(ctx, job_id)

    assert job.status == "completed"
    audit_logs = [item for item in session.added if isinstance(item, AuditLog)]
    assert [audit_log.action for audit_log in audit_logs] == ["users.export_completed"]


@pytest.mark.asyncio
async def test_export_users_task_failure_logs_audit_without_raw_error() -> None:
    job_id = uuid4()
    job = ExportJob(
        id=job_id,
        status="pending",
        created_by_id=uuid4(),
        filters={"search": "nguyen"},
    )

    session = FakeAsyncSession(export_job=job)
    session_factory = MagicMock()
    session_factory.return_value = session

    minio_client = MagicMock()
    minio_client.put_object.side_effect = RuntimeError(
        "failed with token=secret at /tmp/private.csv"
    )
    ctx = {
        "session_factory": session_factory,
        "minio_client": minio_client,
    }

    await export_users_task(ctx, job_id)

    assert job.status == "failed"
    assert "token=secret" in (job.error_summary or "")
    audit_logs = [item for item in session.added if isinstance(item, AuditLog)]
    assert len(audit_logs) == 1
    assert audit_logs[0].action == "users.export_failed"
    assert audit_logs[0].metadata_json == {
        "export_job_id": str(job_id),
        "status": "failed",
        "outcome": "failed",
        "error_category": "export_failed",
        "error_summary": "Failed to export users.",
    }


@pytest.mark.asyncio
async def test_export_users_task_terminal_job_does_not_duplicate_audit() -> None:
    job_id = uuid4()
    job = ExportJob(
        id=job_id,
        status="completed",
        created_by_id=uuid4(),
        filters={"status": "active"},
    )
    session = FakeAsyncSession(export_job=job)
    session_factory = MagicMock()
    session_factory.return_value = session

    ctx = {
        "session_factory": session_factory,
        "minio_client": MagicMock(),
    }

    await export_users_task(ctx, job_id)

    audit_logs = [item for item in session.added if isinstance(item, AuditLog)]
    assert audit_logs == []
    assert session.commit_count == 0


@pytest.mark.asyncio
async def test_run_backup_task_success_logs_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    backup_log_id = uuid4()
    backup_log = BackupLog(
        id=backup_log_id,
        backup_type="manual",
        status="pending",
        created_by_id=uuid4(),
        started_at=datetime.now(UTC),
    )
    session = FakeAsyncSession(backup_log=backup_log)
    session_factory = MagicMock()
    session_factory.return_value = session
    minio_client = MagicMock()
    minio_client.bucket_exists.return_value = True
    FakeEmailService.sent_notifications = []
    FakeEmailService.fail_success = False

    async def fake_create_subprocess_exec(*args: object, **kwargs: object) -> FakeCompletedProcess:
        return FakeCompletedProcess()

    monkeypatch.setattr(
        "app.worker.asyncio.create_subprocess_exec",
        fake_create_subprocess_exec,
    )
    monkeypatch.setattr("os.makedirs", lambda *args, **kwargs: None)
    monkeypatch.setattr("os.path.getsize", lambda path: 123)
    monkeypatch.setattr("gzip.open", lambda *args, **kwargs: io.BytesIO())
    monkeypatch.setattr("app.worker.EmailService", FakeEmailService)

    ctx = {
        "session_factory": session_factory,
        "minio_client": minio_client,
    }

    await run_backup_task(ctx, backup_log_id)

    assert backup_log.status == "completed"
    assert backup_log.file_size == 123
    audit_logs = [item for item in session.added if isinstance(item, AuditLog)]
    assert len(audit_logs) == 1
    assert audit_logs[0].action == "backups.run_completed"
    assert audit_logs[0].entity_type == "backup_log"
    assert audit_logs[0].entity_id == str(backup_log_id)
    assert audit_logs[0].actor_user_id == backup_log.created_by_id
    assert audit_logs[0].metadata_json == {
        "backup_log_id": str(backup_log_id),
        "backup_type": "manual",
        "filename": backup_log.filename,
        "size_bytes": 123,
        "status": "completed",
        "outcome": "completed",
    }
    assert FakeEmailService.sent_notifications[0]["status"] == "success"


@pytest.mark.asyncio
async def test_run_backup_task_success_keeps_completed_status_when_email_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backup_log_id = uuid4()
    backup_log = BackupLog(
        id=backup_log_id,
        backup_type="manual",
        status="pending",
        created_by_id=uuid4(),
        started_at=datetime.now(UTC),
    )
    session = FakeAsyncSession(backup_log=backup_log)
    session_factory = MagicMock()
    session_factory.return_value = session
    minio_client = MagicMock()
    minio_client.bucket_exists.return_value = True
    FakeEmailService.sent_notifications = []
    FakeEmailService.fail_success = True

    async def fake_create_subprocess_exec(*args: object, **kwargs: object) -> FakeCompletedProcess:
        return FakeCompletedProcess()

    monkeypatch.setattr(
        "app.worker.asyncio.create_subprocess_exec",
        fake_create_subprocess_exec,
    )
    monkeypatch.setattr("os.makedirs", lambda *args, **kwargs: None)
    monkeypatch.setattr("os.path.getsize", lambda path: 123)
    monkeypatch.setattr("gzip.open", lambda *args, **kwargs: io.BytesIO())
    monkeypatch.setattr("app.worker.EmailService", FakeEmailService)

    ctx = {
        "session_factory": session_factory,
        "minio_client": minio_client,
    }

    await run_backup_task(ctx, backup_log_id)

    assert backup_log.status == "completed"
    audit_logs = [item for item in session.added if isinstance(item, AuditLog)]
    assert [audit_log.action for audit_log in audit_logs] == ["backups.run_completed"]


@pytest.mark.asyncio
async def test_run_backup_task_running_retry_can_complete_and_log_audit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backup_log_id = uuid4()
    backup_log = BackupLog(
        id=backup_log_id,
        backup_type="manual",
        status="running",
        created_by_id=uuid4(),
        started_at=datetime.now(UTC),
    )
    session = FakeAsyncSession(backup_log=backup_log)
    session_factory = MagicMock()
    session_factory.return_value = session
    minio_client = MagicMock()
    minio_client.bucket_exists.return_value = True
    FakeEmailService.sent_notifications = []
    FakeEmailService.fail_success = False

    async def fake_create_subprocess_exec(*args: object, **kwargs: object) -> FakeCompletedProcess:
        return FakeCompletedProcess()

    monkeypatch.setattr(
        "app.worker.asyncio.create_subprocess_exec",
        fake_create_subprocess_exec,
    )
    monkeypatch.setattr("os.makedirs", lambda *args, **kwargs: None)
    monkeypatch.setattr("os.path.getsize", lambda path: 123)
    monkeypatch.setattr("gzip.open", lambda *args, **kwargs: io.BytesIO())
    monkeypatch.setattr("app.worker.EmailService", FakeEmailService)

    ctx = {
        "session_factory": session_factory,
        "minio_client": minio_client,
    }

    await run_backup_task(ctx, backup_log_id)

    assert backup_log.status == "completed"
    audit_logs = [item for item in session.added if isinstance(item, AuditLog)]
    assert [audit_log.action for audit_log in audit_logs] == ["backups.run_completed"]


@pytest.mark.asyncio
async def test_run_backup_task_failure_logs_audit_without_raw_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backup_log_id = uuid4()
    backup_log = BackupLog(
        id=backup_log_id,
        backup_type="scheduled",
        status="pending",
        created_by_id=None,
        started_at=datetime.now(UTC),
    )
    session = FakeAsyncSession(backup_log=backup_log)
    session_factory = MagicMock()
    session_factory.return_value = session
    minio_client = MagicMock()
    FakeEmailService.sent_notifications = []
    FakeEmailService.fail_success = False

    async def fake_create_subprocess_exec(*args: object, **kwargs: object) -> object:
        raise RuntimeError("pg_dump failed with PGPASSWORD=secret at /app/backups/raw.sql")

    monkeypatch.setattr(
        "app.worker.asyncio.create_subprocess_exec",
        fake_create_subprocess_exec,
    )
    monkeypatch.setattr("os.makedirs", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.worker.EmailService", FakeEmailService)

    ctx = {
        "session_factory": session_factory,
        "minio_client": minio_client,
    }

    await run_backup_task(ctx, backup_log_id)

    assert backup_log.status == "failed"
    assert "PGPASSWORD=secret" in (backup_log.error_message or "")
    audit_logs = [item for item in session.added if isinstance(item, AuditLog)]
    assert len(audit_logs) == 1
    assert audit_logs[0].action == "backups.run_failed"
    assert audit_logs[0].metadata_json == {
        "backup_log_id": str(backup_log_id),
        "backup_type": "scheduled",
        "status": "failed",
        "outcome": "failed",
        "error_category": "backup_failed",
        "error_summary": "Backup task failed.",
    }
    assert FakeEmailService.sent_notifications[0]["status"] == "failed"


@pytest.mark.asyncio
async def test_run_backup_task_terminal_log_does_not_duplicate_audit() -> None:
    backup_log_id = uuid4()
    backup_log = BackupLog(
        id=backup_log_id,
        backup_type="manual",
        status="completed",
        created_by_id=uuid4(),
        started_at=datetime.now(UTC),
    )
    session = FakeAsyncSession(backup_log=backup_log)
    session_factory = MagicMock()
    session_factory.return_value = session

    ctx = {
        "session_factory": session_factory,
        "minio_client": MagicMock(),
    }

    await run_backup_task(ctx, backup_log_id)

    audit_logs = [item for item in session.added if isinstance(item, AuditLog)]
    assert audit_logs == []
    assert session.commit_count == 0
