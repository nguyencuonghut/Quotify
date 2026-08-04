from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.v1.users import (
    get_audit_log_service,
    get_file_admin_service,
    get_user_admin_service,
)
from app.auth.dependencies import get_current_user
from app.auth.hashing import hash_password, verify_password
from app.db.session import get_db_session
from app.models import File, Role, User, UserStatus
from app.services import UserNotFoundError


class MockSession:
    def add(self, instance: object) -> None:
        pass

    async def flush(self) -> None:
        pass

    async def commit(self) -> None:
        pass


class MockUserAdminService:
    def __init__(self, users: list[User]) -> None:
        self.users = {u.id: u for u in users}
        self.audit_service: MockAuditLogService | None = None

    async def list_users(self, **kwargs: Any) -> tuple[list[User], int]:
        return list(self.users.values()), len(self.users)

    async def get_user_by_id(self, user_id: UUID) -> User:
        user = self.users.get(user_id)
        if user is None:
            raise UserNotFoundError(f"User {user_id} does not exist.")
        return user

    async def update_user(self, user_id: UUID, **kwargs: Any) -> User:
        user = self.users.get(user_id)
        if user is None:
            raise UserNotFoundError(f"User {user_id} does not exist.")
        user.email = kwargs.get("email", user.email)
        user.status = kwargs.get("status", user.status)
        user.full_name = kwargs.get("full_name", user.full_name)
        user.avatar_url = kwargs.get("avatar_url", user.avatar_url)
        return user

    async def delete_user(self, user_id: UUID) -> None:
        if user_id not in self.users:
            raise UserNotFoundError(f"User {user_id} does not exist.")
        del self.users[user_id]


class MockAuditLogService:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def log_event(self, **kwargs: Any) -> None:
        self.events.append(kwargs)


class MockFileAdminService:
    def __init__(self) -> None:
        self.session = MockSession()

    async def upload_file(self, **kwargs: Any) -> File:
        return File(
            id=uuid4(),
            filename=kwargs["filename"],
            storage_path=f"avatars/{uuid4()}-{kwargs['filename']}",
            bucket="quotify",
            content_type=kwargs["content_type"],
            size_bytes=kwargs["size_bytes"],
            is_public=kwargs["is_public"],
            uploaded_by_id=kwargs["uploaded_by_id"],
            created_at=datetime.now(UTC),
        )


@pytest.fixture
def override_dependencies(app: FastAPI) -> Generator[MockUserAdminService, None, None]:
    role = Role(id=uuid4(), name="admin", is_system=True)
    role.permissions = []
    admin_user = User(
        id=uuid4(),
        email="admin@example.com",
        password_hash=hash_password("OldPassword123!"),
        status=UserStatus.ACTIVE,
        full_name="Admin",
    )
    admin_user.roles = [role]

    u1 = User(
        id=uuid4(),
        email="u1@example.com",
        password_hash=hash_password("OldPassword123!"),
        status=UserStatus.ACTIVE,
        full_name="User One",
        avatar_url="https://old.avatar/image.png",
    )
    u1.roles = []

    mock_admin_service = MockUserAdminService([admin_user, u1])
    mock_audit_service = MockAuditLogService()
    mock_admin_service.audit_service = mock_audit_service
    mock_file_service = MockFileAdminService()

    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[get_user_admin_service] = lambda: mock_admin_service
    app.dependency_overrides[get_audit_log_service] = lambda: mock_audit_service
    app.dependency_overrides[get_file_admin_service] = lambda: mock_file_service
    app.dependency_overrides[get_db_session] = lambda: MockSession()

    yield mock_admin_service

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_users_api(
    app: FastAPI, client: AsyncClient, override_dependencies: MockUserAdminService
) -> None:
    response = await client.get("/api/v1/users")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_get_user_api_success(
    app: FastAPI, client: AsyncClient, override_dependencies: MockUserAdminService
) -> None:
    user_id = list(override_dependencies.users.keys())[1]  # u1 user id
    response = await client.get(f"/api/v1/users/{user_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "u1@example.com"


@pytest.mark.asyncio
async def test_get_user_api_not_found(
    app: FastAPI, client: AsyncClient, override_dependencies: MockUserAdminService
) -> None:
    random_id = uuid4()
    response = await client.get(f"/api/v1/users/{random_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_user_api(
    app: FastAPI, client: AsyncClient, override_dependencies: MockUserAdminService
) -> None:
    user_id = list(override_dependencies.users.keys())[1]  # u1 user id
    payload = {
        "email": "u1-updated@example.com",
        "status": "locked",
        "password": "NewPassword123!",
        "role_names": [],
        "full_name": "Updated Full Name",
        "avatar_url": "https://new.avatar/image.png",
    }
    response = await client.put(f"/api/v1/users/{user_id}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "u1-updated@example.com"
    assert data["status"] == "locked"
    assert data["full_name"] == "Updated Full Name"
    assert data["avatar_url"] == "https://new.avatar/image.png"

    assert override_dependencies.audit_service is not None
    assert len(override_dependencies.audit_service.events) == 1
    audit_event = override_dependencies.audit_service.events[0]
    assert audit_event["action"] == "users.user_updated"
    metadata = audit_event["context"].metadata_json
    assert metadata["outcome"] == "updated"
    assert metadata["email"] == "u1-updated@example.com"
    assert metadata["changes"] == [
        {
            "field": "email",
            "label": "Email",
            "old_value": "u1@example.com",
            "new_value": "u1-updated@example.com",
        },
        {
            "field": "full_name",
            "label": "Họ và tên",
            "old_value": "User One",
            "new_value": "Updated Full Name",
        },
        {
            "field": "status",
            "label": "Trạng thái",
            "old_value": "active",
            "new_value": "locked",
        },
        {
            "field": "avatar_url",
            "label": "Ảnh đại diện",
            "old_value": "https://old.avatar/image.png",
            "new_value": "https://new.avatar/image.png",
        },
        {
            "field": "login_information",
            "label": "Thông tin đăng nhập",
            "old_value": "[HIDDEN]",
            "new_value": "Đã cập nhật",
        },
    ]


@pytest.mark.asyncio
async def test_upload_user_avatar_api_success(
    app: FastAPI, client: AsyncClient, override_dependencies: MockUserAdminService
) -> None:
    files = {"file": ("avatar.png", b"fake-image-content", "image/png")}
    response = await client.post("/api/v1/users/avatar-upload", files=files)

    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "avatar.png"
    assert "/api/v1/files/" in data["avatar_url"]
    assert data["avatar_url"].endswith("/download")


@pytest.mark.asyncio
async def test_upload_user_avatar_rejects_non_image_files(
    app: FastAPI, client: AsyncClient, override_dependencies: MockUserAdminService
) -> None:
    files = {"file": ("avatar.txt", b"plain-text", "text/plain")}
    response = await client.post("/api/v1/users/avatar-upload", files=files)

    assert response.status_code == 422
    assert response.json()["detail"] == "Only image uploads are supported for user avatars."


@pytest.mark.asyncio
async def test_current_user_can_update_own_avatar(
    app: FastAPI, client: AsyncClient, override_dependencies: MockUserAdminService
) -> None:
    current_user = list(override_dependencies.users.values())[0]

    files = {"file": ("me.png", b"fake-image-content", "image/png")}
    response = await client.post("/api/v1/users/me/avatar", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(current_user.id)
    assert data["avatar_url"].startswith("/api/v1/files/")
    assert data["avatar_url"].endswith("/download")
    assert current_user.avatar_url == data["avatar_url"]

    assert override_dependencies.audit_service is not None
    audit_event = override_dependencies.audit_service.events[-1]
    assert audit_event["action"] == "users.avatar_uploaded"
    assert audit_event["entity_type"] == "user"
    metadata = audit_event["context"].metadata_json
    assert metadata["email"] == current_user.email
    assert metadata["changes"] == [
        {
            "field": "avatar_url",
            "label": "Ảnh đại diện",
            "old_value": None,
            "new_value": current_user.avatar_url,
        }
    ]


@pytest.mark.asyncio
async def test_current_user_can_change_own_password(
    app: FastAPI, client: AsyncClient, override_dependencies: MockUserAdminService
) -> None:
    current_user = list(override_dependencies.users.values())[0]

    response = await client.put(
        "/api/v1/users/me/password",
        json={
            "current_password": "OldPassword123!",
            "new_password": "NewPassword123!",
        },
    )

    assert response.status_code == 204
    assert verify_password("NewPassword123!", current_user.password_hash) is True
    assert verify_password("OldPassword123!", current_user.password_hash) is False

    assert override_dependencies.audit_service is not None
    audit_event = override_dependencies.audit_service.events[-1]
    assert audit_event["action"] == "users.password_changed"
    metadata = audit_event["context"].metadata_json
    assert metadata["email"] == current_user.email
    assert metadata["outcome"] == "updated"
    assert "password" not in metadata


@pytest.mark.asyncio
async def test_current_user_password_change_rejects_wrong_current_password(
    app: FastAPI, client: AsyncClient, override_dependencies: MockUserAdminService
) -> None:
    current_user = list(override_dependencies.users.values())[0]

    response = await client.put(
        "/api/v1/users/me/password",
        json={
            "current_password": "WrongPassword123!",
            "new_password": "NewPassword123!",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Current password is incorrect."
    assert verify_password("OldPassword123!", current_user.password_hash) is True


@pytest.mark.asyncio
async def test_delete_user_api_success(
    app: FastAPI, client: AsyncClient, override_dependencies: MockUserAdminService
) -> None:
    user_id = list(override_dependencies.users.keys())[1]  # u1 user id
    response = await client.delete(f"/api/v1/users/{user_id}")
    assert response.status_code == 204
    assert user_id not in override_dependencies.users


@pytest.mark.asyncio
async def test_delete_user_api_self_deletion(
    app: FastAPI, client: AsyncClient, override_dependencies: MockUserAdminService
) -> None:
    # admin id (current user)
    admin_id = list(override_dependencies.users.keys())[0]
    response = await client.delete(f"/api/v1/users/{admin_id}")
    assert response.status_code == 400
    assert response.json()["detail"] == "You cannot delete yourself."
