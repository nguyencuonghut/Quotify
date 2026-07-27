from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.models import Permission, Role
from app.services.role_admin import (
    PermissionNotFoundError,
    RoleAdminService,
    RoleAlreadyExistsError,
    RoleNotFoundError,
    SystemRoleModificationError,
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
    def __init__(
        self,
        *,
        roles_by_name: dict[str, Role] | None = None,
        roles_by_id: dict[UUID, Role] | None = None,
        permissions_by_code: dict[str, Permission] | None = None,
    ) -> None:
        self.roles_by_name = roles_by_name or {}
        self.roles_by_id = roles_by_id or {}
        self.permissions_by_code = permissions_by_code or {}
        self.added: list[object] = []
        self.deleted: list[object] = []
        self.flush_count = 0

    async def execute(self, statement: object) -> FakeScalarResult:
        compiled = str(statement)
        params = statement.compile().params  # type: ignore[attr-defined]

        if "count" in compiled:
            return FakeScalarResult(len(self.roles_by_id))

        if "id_1" in params and "FROM roles" in compiled:
            return FakeScalarResult(self.roles_by_id.get(params["id_1"]))

        if "name_1" in params and "FROM roles" in compiled:
            return FakeScalarResult(self.roles_by_name.get(params["name_1"]))

        if "FROM roles" in compiled:
            return FakeScalarResult(list(self.roles_by_id.values()))

        if "FROM permissions" in compiled:
            codes: list[str] = []
            for val in params.values():
                if isinstance(val, (list, tuple)):
                    codes.extend(val)
                else:
                    codes.append(val)
            found = [self.permissions_by_code[c] for c in codes if c in self.permissions_by_code]
            return FakeScalarResult(found)

        raise AssertionError(f"Unexpected statement: {compiled}")

    def add(self, instance: object) -> None:
        self.added.append(instance)

    async def delete(self, instance: object) -> None:
        self.deleted.append(instance)
        if isinstance(instance, Role):
            self.roles_by_id.pop(instance.id, None)
            self.roles_by_name.pop(instance.name, None)

    async def flush(self) -> None:
        self.flush_count += 1


@pytest.mark.asyncio
async def test_create_role_success() -> None:
    p1 = Permission(id=uuid4(), code="users.read")
    session = FakeAsyncSession(permissions_by_code={"users.read": p1})
    service = RoleAdminService(session)  # type: ignore[arg-type]

    role = await service.create_role(
        name="custom_manager",
        description="Manager role",
        permission_codes=["users.read"],
    )

    assert role.name == "custom_manager"
    assert role.description == "Manager role"
    assert role.is_system is False
    assert role.permissions == [p1]
    assert len(session.added) == 1
    assert session.flush_count == 1


@pytest.mark.asyncio
async def test_create_role_already_exists() -> None:
    existing = Role(id=uuid4(), name="existing")
    session = FakeAsyncSession(roles_by_name={"existing": existing})
    service = RoleAdminService(session)  # type: ignore[arg-type]

    with pytest.raises(RoleAlreadyExistsError):
        await service.create_role(name="existing")


@pytest.mark.asyncio
async def test_create_role_permission_not_found() -> None:
    session = FakeAsyncSession()
    service = RoleAdminService(session)  # type: ignore[arg-type]

    with pytest.raises(PermissionNotFoundError):
        await service.create_role(name="new_role", permission_codes=["invalid"])


@pytest.mark.asyncio
async def test_get_role_by_id_success() -> None:
    role = Role(id=uuid4(), name="test_role", is_system=False)
    session = FakeAsyncSession(roles_by_id={role.id: role})
    service = RoleAdminService(session)  # type: ignore[arg-type]

    fetched = await service.get_role_by_id(role.id)
    assert fetched.id == role.id
    assert fetched.name == "test_role"


@pytest.mark.asyncio
async def test_get_role_by_id_not_found() -> None:
    session = FakeAsyncSession()
    service = RoleAdminService(session)  # type: ignore[arg-type]

    with pytest.raises(RoleNotFoundError):
        await service.get_role_by_id(uuid4())


@pytest.mark.asyncio
async def test_list_roles() -> None:
    r1 = Role(id=uuid4(), name="r1")
    r2 = Role(id=uuid4(), name="r2")
    session = FakeAsyncSession(roles_by_id={r1.id: r1, r2.id: r2})
    service = RoleAdminService(session)  # type: ignore[arg-type]

    roles, total = await service.list_roles()
    assert total == 2
    assert len(roles) == 2


@pytest.mark.asyncio
async def test_update_role_details_and_permissions() -> None:
    role = Role(id=uuid4(), name="old_name", description="old description", is_system=False)
    p1 = Permission(id=uuid4(), code="users.read")
    session = FakeAsyncSession(
        roles_by_id={role.id: role},
        roles_by_name={role.name: role},
        permissions_by_code={"users.read": p1},
    )
    service = RoleAdminService(session)  # type: ignore[arg-type]

    updated = await service.update_role(
        role_id=role.id,
        name="new_name",
        description="new description",
        permission_codes=["users.read"],
    )

    assert updated.name == "new_name"
    assert updated.description == "new description"
    assert updated.permissions == [p1]
    assert session.flush_count == 1


@pytest.mark.asyncio
async def test_update_role_rejects_duplicate_name() -> None:
    r1 = Role(id=uuid4(), name="r1", is_system=False)
    r2 = Role(id=uuid4(), name="r2", is_system=False)
    session = FakeAsyncSession(
        roles_by_id={r1.id: r1, r2.id: r2},
        roles_by_name={"r1": r1, "r2": r2},
    )
    service = RoleAdminService(session)  # type: ignore[arg-type]

    with pytest.raises(RoleAlreadyExistsError):
        await service.update_role(role_id=r1.id, name="r2")


@pytest.mark.asyncio
async def test_update_role_guardrails_system_role_rename() -> None:
    system_role = Role(id=uuid4(), name="admin", is_system=True)
    session = FakeAsyncSession(
        roles_by_id={system_role.id: system_role},
        roles_by_name={system_role.name: system_role},
    )
    service = RoleAdminService(session)  # type: ignore[arg-type]

    with pytest.raises(SystemRoleModificationError):
        await service.update_role(role_id=system_role.id, name="super_admin")


@pytest.mark.asyncio
async def test_delete_role_success() -> None:
    role = Role(id=uuid4(), name="custom", is_system=False)
    session = FakeAsyncSession(
        roles_by_id={role.id: role},
        roles_by_name={role.name: role},
    )
    service = RoleAdminService(session)  # type: ignore[arg-type]

    await service.delete_role(role.id)
    assert len(session.deleted) == 1
    assert session.deleted[0] is role
    assert role.id not in session.roles_by_id


@pytest.mark.asyncio
async def test_delete_role_guardrails_system_role() -> None:
    system_role = Role(id=uuid4(), name="admin", is_system=True)
    session = FakeAsyncSession(
        roles_by_id={system_role.id: system_role},
        roles_by_name={system_role.name: system_role},
    )
    service = RoleAdminService(session)  # type: ignore[arg-type]

    with pytest.raises(SystemRoleModificationError):
        await service.delete_role(system_role.id)
