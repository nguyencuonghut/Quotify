from __future__ import annotations

from collections.abc import Generator
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.v1.jobs import get_audit_log_service, get_file_admin_service, get_job_service
from app.auth.dependencies import get_current_user
from app.db.session import get_db_session
from app.models import ExportJob, File, ImportJob, User, UserStatus
from app.services.job_admin import JobNotFoundError


class MockSession:
    def add(self, instance: object) -> None:
        pass

    async def flush(self) -> None:
        pass

    async def commit(self) -> None:
        pass


class MockFileAdminService:
    async def upload_file(self, **kwargs: Any) -> File:
        return File(
            id=uuid4(),
            filename=kwargs["filename"],
            storage_path=f"path/{kwargs['filename']}",
            bucket="app-local",
            content_type=kwargs["content_type"],
            size_bytes=kwargs["size_bytes"],
            is_public=kwargs["is_public"],
            uploaded_by_id=kwargs["uploaded_by_id"],
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )


class MockJobAdminService:
    def __init__(
        self,
        import_jobs: list[ImportJob] | None = None,
        export_jobs: list[ExportJob] | None = None,
    ) -> None:
        self.import_jobs = {j.id: j for j in (import_jobs or [])}
        self.export_jobs = {j.id: j for j in (export_jobs or [])}
        self.session = MockSession()

    async def create_import_job(self, file_id: UUID, user_id: UUID) -> ImportJob:
        job_id = uuid4()
        f = File(
            id=file_id,
            filename="users.csv",
            bucket="app-local",
            storage_path=f"path/{file_id}",
            content_type="text/csv",
            size_bytes=100,
            is_public=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        job = ImportJob(
            id=job_id,
            file_id=file_id,
            status="pending",
            total_rows=0,
            processed_rows=0,
            failed_rows=0,
            created_by_id=user_id,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        job.file = f
        self.import_jobs[job_id] = job
        return job

    async def create_export_job(self, filters: dict[str, Any] | None, user_id: UUID) -> ExportJob:
        job_id = uuid4()
        job = ExportJob(
            id=job_id,
            status="pending",
            filters=filters,
            created_by_id=user_id,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        self.export_jobs[job_id] = job
        return job

    async def get_import_job_by_id(self, job_id: UUID) -> ImportJob:
        j = self.import_jobs.get(job_id)
        if j is None:
            raise JobNotFoundError()
        return j

    async def get_export_job_by_id(self, job_id: UUID) -> ExportJob:
        j = self.export_jobs.get(job_id)
        if j is None:
            raise JobNotFoundError()
        return j

    async def list_import_jobs(self, **kwargs: Any) -> tuple[list[ImportJob], int]:
        return list(self.import_jobs.values()), len(self.import_jobs)

    async def list_export_jobs(self, **kwargs: Any) -> tuple[list[ExportJob], int]:
        return list(self.export_jobs.values()), len(self.export_jobs)


class MockAuditLogService:
    async def log_event(self, **kwargs: Any) -> None:
        pass


@pytest.fixture
def override_dependencies(app: FastAPI) -> Generator[MockJobAdminService, None, None]:
    admin_user = User(id=uuid4(), email="admin@example.com", status=UserStatus.ACTIVE)
    from app.models import Role

    admin_role = Role(id=uuid4(), name="admin", is_system=True)
    admin_user.roles = [admin_role]

    mock_job_service = MockJobAdminService()
    mock_file_service = MockFileAdminService()
    mock_audit_service = MockAuditLogService()

    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[get_job_service] = lambda: mock_job_service
    app.dependency_overrides[get_file_admin_service] = lambda: mock_file_service
    app.dependency_overrides[get_audit_log_service] = lambda: mock_audit_service
    app.dependency_overrides[get_db_session] = lambda: MockSession()

    yield mock_job_service

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_import_users_api_success(
    app: FastAPI, client: AsyncClient, override_dependencies: MockJobAdminService
) -> None:
    files = {
        "file": (
            "users.csv",
            b"email,password,status,roles\nfoo@bar.com,pass1234,active,user",
            "text/csv",
        )
    }
    response = await client.post("/api/v1/users/import", files=files)
    assert response.status_code == 201
    res_data = response.json()
    assert res_data["status"] == "pending"
    assert "file" in res_data
    assert res_data["file"]["filename"] == "users.csv"


@pytest.mark.asyncio
async def test_import_users_api_invalid_extension(
    app: FastAPI, client: AsyncClient, override_dependencies: MockJobAdminService
) -> None:
    files = {"file": ("users.txt", b"plain text", "text/plain")}
    response = await client.post("/api/v1/users/import", files=files)
    assert response.status_code == 400
    assert "CSV" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_import_jobs_api(
    app: FastAPI, client: AsyncClient, override_dependencies: MockJobAdminService
) -> None:
    await override_dependencies.create_import_job(file_id=uuid4(), user_id=uuid4())
    response = await client.get("/api/v1/users/import/jobs")
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["total"] == 1
    assert len(res_data["items"]) == 1


@pytest.mark.asyncio
async def test_export_users_api_success(
    app: FastAPI, client: AsyncClient, override_dependencies: MockJobAdminService
) -> None:
    payload = {"search": "test", "status": "active"}
    response = await client.post("/api/v1/users/export", json=payload)
    assert response.status_code == 201
    res_data = response.json()
    assert res_data["status"] == "pending"
    assert res_data["filters"] == payload


@pytest.mark.asyncio
async def test_list_export_jobs_api(
    app: FastAPI, client: AsyncClient, override_dependencies: MockJobAdminService
) -> None:
    await override_dependencies.create_export_job(filters={}, user_id=uuid4())
    response = await client.get("/api/v1/users/export/jobs")
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["total"] == 1
