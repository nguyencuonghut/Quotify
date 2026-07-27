from __future__ import annotations

from collections.abc import Generator
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.v1.files import get_audit_log_service, get_file_admin_service
from app.auth.dependencies import get_current_user
from app.db.session import get_db_session
from app.models import File, User, UserStatus
from app.services.file_admin import (
    FileMetadataNotFoundError,
    FilePermissionDeniedError,
)


class MockSession:
    def add(self, instance: object) -> None:
        pass

    async def flush(self) -> None:
        pass

    async def commit(self) -> None:
        pass


class MockFileAdminService:
    def __init__(self, files: list[File]) -> None:
        self.files = {f.id: f for f in files}
        self.session = MockSession()
        self.minio_client = MagicMock()

        # Mock MinIO get_object stream response
        mock_stream = MagicMock()
        mock_stream.read.side_effect = [b"chunk data", b""]
        self.minio_client.get_object.return_value = mock_stream

    async def upload_file(self, **kwargs: Any) -> File:
        file_id = uuid4()
        db_file = File(
            id=file_id,
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
        self.files[file_id] = db_file
        return db_file

    async def get_file_by_id(self, file_id: UUID) -> File:
        f = self.files.get(file_id)
        if f is None:
            raise FileMetadataNotFoundError(f"File metadata {file_id} not found.")
        return f

    async def list_files(self, **kwargs: Any) -> tuple[list[File], int]:
        return list(self.files.values()), len(self.files)

    async def delete_file(self, file_id: UUID, **kwargs: Any) -> None:
        f = self.files.get(file_id)
        if f is None:
            raise FileMetadataNotFoundError(f"File metadata {file_id} not found.")

        user_id = kwargs.get("user_id")
        can_delete_all = kwargs.get("can_delete_all", False)
        if not can_delete_all and f.uploaded_by_id != user_id:
            raise FilePermissionDeniedError("Access denied.")

        del self.files[file_id]


class MockAuditLogService:
    async def log_event(self, **kwargs: Any) -> None:
        pass


@pytest.fixture
def override_dependencies(app: FastAPI) -> Generator[MockFileAdminService, None, None]:
    admin_user = User(id=uuid4(), email="admin@example.com", status=UserStatus.ACTIVE)
    # Give admin user permissions by mocking has_permission inside dependencies,
    # or rely on dependency_overrides.
    # Note: has_permission evaluates role=admin to True. Let's make sure roles contain admin.
    from app.models import Role

    admin_role = Role(id=uuid4(), name="admin", is_system=True)
    admin_user.roles = [admin_role]

    f1 = File(
        id=uuid4(),
        filename="public.txt",
        storage_path="path/public.txt",
        bucket="app-local",
        content_type="text/plain",
        size_bytes=100,
        is_public=True,
        uploaded_by_id=admin_user.id,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    f2 = File(
        id=uuid4(),
        filename="private.txt",
        storage_path="path/private.txt",
        bucket="app-local",
        content_type="text/plain",
        size_bytes=200,
        is_public=False,
        uploaded_by_id=admin_user.id,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    mock_file_service = MockFileAdminService([f1, f2])
    mock_audit_service = MockAuditLogService()

    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[get_file_admin_service] = lambda: mock_file_service
    app.dependency_overrides[get_audit_log_service] = lambda: mock_audit_service
    app.dependency_overrides[get_db_session] = lambda: MockSession()

    yield mock_file_service

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_upload_file_api_success(
    app: FastAPI, client: AsyncClient, override_dependencies: MockFileAdminService
) -> None:
    # Use Multipart Form
    files = {"file": ("document.pdf", b"pdf binary content", "application/pdf")}
    data = {"is_public": "true"}

    response = await client.post("/api/v1/files/upload", files=files, data=data)
    assert response.status_code == 201
    res_data = response.json()
    assert res_data["filename"] == "document.pdf"
    assert res_data["content_type"] == "application/pdf"
    assert res_data["is_public"] is True
    assert "url" in res_data


@pytest.mark.asyncio
async def test_list_files_api(
    app: FastAPI, client: AsyncClient, override_dependencies: MockFileAdminService
) -> None:
    response = await client.get("/api/v1/files")
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["total"] == 2
    assert len(res_data["items"]) == 2


@pytest.mark.asyncio
async def test_get_file_metadata_api(
    app: FastAPI, client: AsyncClient, override_dependencies: MockFileAdminService
) -> None:
    file_id = list(override_dependencies.files.keys())[0]
    response = await client.get(f"/api/v1/files/{file_id}")
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["id"] == str(file_id)


@pytest.mark.asyncio
async def test_download_file_api(
    app: FastAPI, client: AsyncClient, override_dependencies: MockFileAdminService
) -> None:
    # We bypass token dependency in tests since we override current_user,
    # but the download endpoint reads from optional token. If not provided it falls back.
    # If the file is public, it works without auth token header.
    # Our override_dependencies returns f1 (public) and f2 (private).
    # Let's get the public file first.
    pub_file = [f for f in override_dependencies.files.values() if f.is_public][0]
    response = await client.get(f"/api/v1/files/{pub_file.id}/download")
    assert response.status_code == 200
    assert response.read() == b"chunk data"


@pytest.mark.asyncio
async def test_delete_file_api_success(
    app: FastAPI, client: AsyncClient, override_dependencies: MockFileAdminService
) -> None:
    file_id = list(override_dependencies.files.keys())[0]
    response = await client.delete(f"/api/v1/files/{file_id}")
    assert response.status_code == 204
    assert file_id not in override_dependencies.files
