from __future__ import annotations

from collections.abc import Generator
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.v1.roles import get_audit_log_service, get_role_admin_service
from app.auth.dependencies import get_current_user
from app.db.session import get_db_session
from app.models import Permission, Role, User, UserStatus
from app.services import (
    PermissionNotFoundError,
    RoleAlreadyExistsError,
    RoleNotFoundError,
    SystemRoleModificationError,
)


class MockSession:
    def add(self, instance: object) -> None:
        pass

    async def flush(self) -> None:
        pass

    async def commit(self) -> None:
        pass


class MockRoleAdminService:
    def __init__(self, roles: list[Role]) -> None:
        self.roles = {r.id: r for r in roles}

    async def list_roles(self, **kwargs: Any) -> tuple[list[Role], int]:
        return list(self.roles.values()), len(self.roles)

    async def get_role_by_id(self, role_id: UUID) -> Role:
        role = self.roles.get(role_id)
        if role is None:
            raise RoleNotFoundError(f"Role {role_id} does not exist.")
        return role

    async def create_role(self, **kwargs: Any) -> Role:
        name = kwargs["name"]
        for r in self.roles.values():
            if r.name == name:
                raise RoleAlreadyExistsError(f"Role with name '{name}' already exists.")

        permission_codes = kwargs.get("permission_codes", [])
        if "invalid" in permission_codes:
            raise PermissionNotFoundError("One or more permissions do not exist: invalid.")

        role = Role(
            id=uuid4(),
            name=name,
            description=kwargs.get("description"),
            is_system=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        role.permissions = [Permission(id=uuid4(), code=c) for c in permission_codes]
        self.roles[role.id] = role
        return role

    async def update_role(self, role_id: UUID, **kwargs: Any) -> Role:
        role = self.roles.get(role_id)
        if role is None:
            raise RoleNotFoundError(f"Role {role_id} does not exist.")
        name = kwargs["name"]
        if role.is_system and role.name != name:
            raise SystemRoleModificationError(f"System role '{role.name}' cannot be renamed.")
        for r in self.roles.values():
            if r.id != role_id and r.name == name:
                raise RoleAlreadyExistsError(f"Role with name '{name}' already exists.")

        permission_codes = kwargs.get("permission_codes", [])
        if "invalid" in permission_codes:
            raise PermissionNotFoundError("One or more permissions do not exist: invalid.")

        role.name = name
        role.description = kwargs.get("description", role.description)
        role.permissions = [Permission(id=uuid4(), code=c) for c in permission_codes]
        return role

    async def delete_role(self, role_id: UUID) -> None:
        role = self.roles.get(role_id)
        if role is None:
            raise RoleNotFoundError(f"Role {role_id} does not exist.")
        if role.is_system:
            raise SystemRoleModificationError(f"System role '{role.name}' cannot be deleted.")
        del self.roles[role_id]


class MockAuditLogService:
    async def log_event(self, **kwargs: Any) -> None:
        pass


@pytest.fixture
def override_dependencies(app: FastAPI) -> Generator[MockRoleAdminService, None, None]:
    p1 = Permission(id=uuid4(), code="users.read")
    role_admin = Role(
        id=uuid4(),
        name="admin",
        description="System Admin",
        is_system=True,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    role_admin.permissions = [p1]

    role_user = Role(
        id=uuid4(),
        name="user",
        description="System User",
        is_system=True,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    admin_user = User(id=uuid4(), email="admin@example.com", status=UserStatus.ACTIVE)
    admin_user.roles = [role_admin]

    mock_admin_service = MockRoleAdminService([role_admin, role_user])
    mock_audit_service = MockAuditLogService()

    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[get_role_admin_service] = lambda: mock_admin_service
    app.dependency_overrides[get_audit_log_service] = lambda: mock_audit_service
    app.dependency_overrides[get_db_session] = lambda: MockSession()

    yield mock_admin_service

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_roles_api(
    app: FastAPI, client: AsyncClient, override_dependencies: MockRoleAdminService
) -> None:
    response = await client.get("/api/v1/roles")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_get_role_api_success(
    app: FastAPI, client: AsyncClient, override_dependencies: MockRoleAdminService
) -> None:
    role_id = list(override_dependencies.roles.keys())[0]
    response = await client.get(f"/api/v1/roles/{role_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] in ("admin", "user")


@pytest.mark.asyncio
async def test_get_role_api_not_found(
    app: FastAPI, client: AsyncClient, override_dependencies: MockRoleAdminService
) -> None:
    response = await client.get(f"/api/v1/roles/{uuid4()}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_role_api_success(
    app: FastAPI, client: AsyncClient, override_dependencies: MockRoleAdminService
) -> None:
    payload = {
        "name": "custom_role",
        "description": "A custom role",
        "permissions": ["users.read"],
    }
    response = await client.post("/api/v1/roles", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "custom_role"
    assert data["description"] == "A custom role"
    assert "users.read" in data["permissions"]


@pytest.mark.asyncio
async def test_create_role_api_already_exists(
    app: FastAPI, client: AsyncClient, override_dependencies: MockRoleAdminService
) -> None:
    payload = {
        "name": "admin",
        "description": "Duplicate",
        "permissions": [],
    }
    response = await client.post("/api/v1/roles", json=payload)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_update_role_api_success(
    app: FastAPI, client: AsyncClient, override_dependencies: MockRoleAdminService
) -> None:
    # Update custom role
    # First, let's create a custom role
    custom = await override_dependencies.create_role(name="custom")
    payload = {
        "name": "custom_updated",
        "description": "Updated description",
        "permissions": [],
    }
    response = await client.put(f"/api/v1/roles/{custom.id}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "custom_updated"
    assert data["description"] == "Updated description"


@pytest.mark.asyncio
async def test_update_role_api_system_role_rename_rejected(
    app: FastAPI, client: AsyncClient, override_dependencies: MockRoleAdminService
) -> None:
    admin_role_id = [r.id for r in override_dependencies.roles.values() if r.name == "admin"][0]
    payload = {
        "name": "renamed_admin",
        "description": "System Admin",
        "permissions": [],
    }
    response = await client.put(f"/api/v1/roles/{admin_role_id}", json=payload)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_delete_role_api_success(
    app: FastAPI, client: AsyncClient, override_dependencies: MockRoleAdminService
) -> None:
    custom = await override_dependencies.create_role(name="custom")
    response = await client.delete(f"/api/v1/roles/{custom.id}")
    assert response.status_code == 204
    assert custom.id not in override_dependencies.roles


@pytest.mark.asyncio
async def test_delete_role_api_system_role_rejected(
    app: FastAPI, client: AsyncClient, override_dependencies: MockRoleAdminService
) -> None:
    admin_role_id = [r.id for r in override_dependencies.roles.values() if r.name == "admin"][0]
    response = await client.delete(f"/api/v1/roles/{admin_role_id}")
    assert response.status_code == 400
