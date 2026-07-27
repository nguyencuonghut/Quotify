from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.auth.dependencies import get_current_user
from app.db.session import get_db_session
from app.models import Permission, Role, User, UserStatus


class MockPermissionResult:
    def __init__(self, permissions: list[Permission]) -> None:
        self._permissions = permissions

    def scalars(self) -> MockPermissionResult:
        return self

    def all(self) -> list[Permission]:
        return self._permissions


class MockSession:
    def __init__(self, permissions: list[Permission]) -> None:
        self.permissions = permissions

    async def execute(self, statement: object) -> MockPermissionResult:
        return MockPermissionResult(self.permissions)


@pytest.mark.asyncio
async def test_list_permissions_success(app: FastAPI, client: AsyncClient) -> None:
    p1 = Permission(id=uuid4(), code="users.read", description="Read users")
    p2 = Permission(id=uuid4(), code="roles.read", description="Read roles")

    role_admin = Role(id=uuid4(), name="admin", is_system=True)
    admin_user = User(
        id=uuid4(),
        email="admin@example.com",
        status=UserStatus.ACTIVE,
    )
    admin_user.roles = [role_admin]

    mock_session = MockSession([p1, p2])
    app.dependency_overrides[get_db_session] = lambda: mock_session
    app.dependency_overrides[get_current_user] = lambda: admin_user

    try:
        response = await client.get("/api/v1/permissions")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["code"] == "users.read"
        assert data[1]["code"] == "roles.read"
    finally:
        app.dependency_overrides.clear()
