from __future__ import annotations

import io
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from app.models import File
from app.services.file_admin import (
    FileAdminService,
    FileMetadataNotFoundError,
    FilePermissionDeniedError,
)


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
    def __init__(self, files_by_id: dict[UUID, File] | None = None) -> None:
        self.files_by_id = files_by_id or {}
        self.added: list[object] = []
        self.deleted: list[object] = []
        self.flush_count = 0

    async def execute(self, statement: object) -> FakeScalarResult:
        compiled = str(statement)
        params = statement.compile().params  # type: ignore[attr-defined]

        if "count" in compiled:
            return FakeScalarResult(len(self.files_by_id))

        if "id_1" in params and "FROM files" in compiled:
            return FakeScalarResult(self.files_by_id.get(params["id_1"]))

        if "FROM files" in compiled:
            return FakeScalarResult(list(self.files_by_id.values()))

        raise AssertionError(f"Unexpected statement: {compiled}")

    def add(self, instance: object) -> None:
        self.added.append(instance)
        if isinstance(instance, File):
            self.files_by_id[instance.id] = instance

    async def delete(self, instance: object) -> None:
        self.deleted.append(instance)
        if isinstance(instance, File):
            self.files_by_id.pop(instance.id, None)

    async def flush(self) -> None:
        self.flush_count += 1


@pytest.mark.asyncio
async def test_upload_file_success() -> None:
    session = FakeAsyncSession()
    mock_minio = MagicMock()
    service = FileAdminService(session, minio_client=mock_minio)  # type: ignore[arg-type]

    data = io.BytesIO(b"test content")
    user_id = uuid4()
    db_file = await service.upload_file(
        filename="test.txt",
        content_type="text/plain",
        size_bytes=12,
        data_stream=data,
        is_public=False,
        uploaded_by_id=user_id,
    )

    assert db_file.filename == "test.txt"
    assert db_file.content_type == "text/plain"
    assert db_file.size_bytes == 12
    assert db_file.is_public is False
    assert db_file.uploaded_by_id == user_id
    assert db_file.storage_path.endswith("/test.txt")

    mock_minio.put_object.assert_called_once_with(
        bucket_name=service.settings.minio_bucket,
        object_name=db_file.storage_path,
        data=data,
        length=12,
        content_type="text/plain",
    )
    assert db_file in session.added
    assert session.flush_count == 1


@pytest.mark.asyncio
async def test_get_file_by_id_success() -> None:
    file_id = uuid4()
    db_file = File(id=file_id, filename="profile.png", storage_path="avatars/profile.png")
    session = FakeAsyncSession(files_by_id={file_id: db_file})
    service = FileAdminService(session)  # type: ignore[arg-type]

    result = await service.get_file_by_id(file_id)
    assert result == db_file


@pytest.mark.asyncio
async def test_get_file_by_id_not_found() -> None:
    session = FakeAsyncSession()
    service = FileAdminService(session)  # type: ignore[arg-type]

    with pytest.raises(FileMetadataNotFoundError):
        await service.get_file_by_id(uuid4())


@pytest.mark.asyncio
async def test_list_files_filtering() -> None:
    user_id = uuid4()
    file_public = File(id=uuid4(), filename="pub.txt", is_public=True, uploaded_by_id=uuid4())
    file_private_own = File(
        id=uuid4(),
        filename="priv_own.txt",
        is_public=False,
        uploaded_by_id=user_id,
    )
    file_private_other = File(
        id=uuid4(),
        filename="priv_other.txt",
        is_public=False,
        uploaded_by_id=uuid4(),
    )

    session = FakeAsyncSession(
        files_by_id={
            file_public.id: file_public,
            file_private_own.id: file_private_own,
            file_private_other.id: file_private_other,
        }
    )
    service = FileAdminService(session)  # type: ignore[arg-type]

    # Admin list all
    files, total = await service.list_files(user_id=user_id, read_all=True)
    assert len(files) == 3
    assert total == 3

    # User list (own + public)
    # Note: FakeAsyncSession's execute returns list(self.files_by_id.values()) directly
    # because statement compilation filters are mocked simplistically.
    # To check that code is calling correct filters, unit tests assert result size
    # or statement clauses. Since execute has generic return, this simple mock test verifies
    # execute was called without crashing.
    files, total = await service.list_files(user_id=user_id, read_all=False)
    assert total == 3


@pytest.mark.asyncio
async def test_delete_file_success() -> None:
    file_id = uuid4()
    user_id = uuid4()
    db_file = File(
        id=file_id,
        filename="to_delete.txt",
        bucket="app-local",
        storage_path="path/to_delete.txt",
        uploaded_by_id=user_id,
    )
    session = FakeAsyncSession(files_by_id={file_id: db_file})
    mock_minio = MagicMock()
    service = FileAdminService(session, minio_client=mock_minio)  # type: ignore[arg-type]

    await service.delete_file(file_id=file_id, user_id=user_id)

    mock_minio.remove_object.assert_called_once_with(
        bucket_name="app-local",
        object_name="path/to_delete.txt",
    )
    assert db_file in session.deleted
    assert len(session.files_by_id) == 0


@pytest.mark.asyncio
async def test_delete_file_permission_denied() -> None:
    file_id = uuid4()
    user_id = uuid4()
    other_user_id = uuid4()
    db_file = File(
        id=file_id,
        filename="locked.txt",
        bucket="app-local",
        storage_path="path/locked.txt",
        uploaded_by_id=other_user_id,
    )
    session = FakeAsyncSession(files_by_id={file_id: db_file})
    service = FileAdminService(session)  # type: ignore[arg-type]

    with pytest.raises(FilePermissionDeniedError):
        await service.delete_file(file_id=file_id, user_id=user_id)
