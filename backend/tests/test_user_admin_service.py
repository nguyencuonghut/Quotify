from __future__ import annotations

from uuid import uuid4

import pytest

from app.auth.hashing import verify_password
from app.models import Permission, Role, User, UserStatus
from app.services.user_admin import (
    EmailAlreadyExistsError,
    RoleNotFoundError,
    UserAdminService,
    UserNotFoundError,
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
        users_by_email: dict[str, User] | None = None,
        users_by_id: dict[object, User] | None = None,
        roles_by_name: dict[str, Role] | None = None,
    ) -> None:
        self.users_by_email = users_by_email or {}
        self.users_by_id = users_by_id or {}
        self.roles_by_name = roles_by_name or {}
        self.added: list[object] = []
        self.deleted: list[object] = []
        self.flush_count = 0

    async def execute(self, statement: object) -> FakeScalarResult:
        compiled = str(statement)
        params = statement.compile().params  # type: ignore[attr-defined]

        if "count" in compiled:
            return FakeScalarResult(len(self.users_by_id))

        if "email_1" in params and "FROM users" in compiled:
            return FakeScalarResult(self.users_by_email.get(params["email_1"]))

        if "id_1" in params and "FROM users" in compiled:
            return FakeScalarResult(self.users_by_id.get(params["id_1"]))

        if "FROM users" in compiled:
            return FakeScalarResult(list(self.users_by_id.values()))

        if "FROM roles" in compiled:
            names: list[str] = []
            for key, value in sorted(params.items()):
                if not key.startswith("name_"):
                    continue
                if isinstance(value, list):
                    names.extend(value)
                else:
                    names.append(value)
            roles = [self.roles_by_name[name] for name in names if name in self.roles_by_name]
            return FakeScalarResult(roles)

        raise AssertionError(f"Unexpected statement: {compiled}")

    def add(self, instance: object) -> None:
        self.added.append(instance)

    async def delete(self, instance: object) -> None:
        self.deleted.append(instance)
        if isinstance(instance, User):
            self.users_by_id.pop(instance.id, None)
            self.users_by_email.pop(instance.email, None)

    async def flush(self) -> None:
        self.flush_count += 1


def build_role(name: str, permissions: list[str] | None = None) -> Role:
    role = Role(id=uuid4(), name=name)
    role.permissions = [
        Permission(id=uuid4(), code=permission_code) for permission_code in (permissions or [])
    ]
    return role


@pytest.mark.asyncio
async def test_create_user_hashes_password_and_assigns_roles() -> None:
    admin_role = build_role("admin", ["users.create"])
    session = FakeAsyncSession(roles_by_name={"admin": admin_role})
    service = UserAdminService(session)  # type: ignore[arg-type]

    user = await service.create_user(
        email="ops@example.com",
        password="Secret123!",
        status=UserStatus.ACTIVE,
        role_names=["admin"],
        full_name="Operations Manager",
        avatar_url="https://example.com/avatar.png",
    )

    assert user.email == "ops@example.com"
    assert verify_password("Secret123!", user.password_hash) is True
    assert [role.name for role in user.roles] == ["admin"]
    assert user.full_name == "Operations Manager"
    assert user.avatar_url == "https://example.com/avatar.png"
    assert len(session.added) == 1


@pytest.mark.asyncio
async def test_create_user_rejects_duplicate_email() -> None:
    existing_user = User(
        id=uuid4(),
        email="ops@example.com",
        password_hash="hashed",
        status=UserStatus.ACTIVE,
        full_name="Existing User",
    )
    session = FakeAsyncSession(users_by_email={existing_user.email: existing_user})
    service = UserAdminService(session)  # type: ignore[arg-type]

    with pytest.raises(EmailAlreadyExistsError):
        await service.create_user(
            email="ops@example.com",
            password="Secret123!",
            status=UserStatus.ACTIVE,
            role_names=[],
            full_name="Duplicate Test",
        )


@pytest.mark.asyncio
async def test_update_user_roles_rejects_missing_role() -> None:
    user = User(
        id=uuid4(),
        email="ops@example.com",
        password_hash="hashed",
        status=UserStatus.ACTIVE,
    )
    session = FakeAsyncSession(users_by_id={user.id: user})
    service = UserAdminService(session)  # type: ignore[arg-type]

    with pytest.raises(RoleNotFoundError):
        await service.update_user_roles(
            user_id=user.id,
            role_names=["missing-role"],
        )


@pytest.mark.asyncio
async def test_update_user_roles_rejects_missing_user() -> None:
    session = FakeAsyncSession()
    service = UserAdminService(session)  # type: ignore[arg-type]

    with pytest.raises(UserNotFoundError):
        await service.update_user_roles(
            user_id=uuid4(),
            role_names=[],
        )


@pytest.mark.asyncio
async def test_get_user_by_id_success() -> None:
    user = User(
        id=uuid4(),
        email="test@example.com",
        password_hash="hashed",
        status=UserStatus.ACTIVE,
    )
    session = FakeAsyncSession(users_by_id={user.id: user})
    service = UserAdminService(session)  # type: ignore[arg-type]

    fetched = await service.get_user_by_id(user.id)
    assert fetched.id == user.id
    assert fetched.email == "test@example.com"


@pytest.mark.asyncio
async def test_get_user_by_id_not_found() -> None:
    session = FakeAsyncSession()
    service = UserAdminService(session)  # type: ignore[arg-type]

    with pytest.raises(UserNotFoundError):
        await service.get_user_by_id(uuid4())


@pytest.mark.asyncio
async def test_list_users() -> None:
    u1 = User(id=uuid4(), email="test1@example.com", password_hash="h1", status=UserStatus.ACTIVE)
    u2 = User(id=uuid4(), email="test2@example.com", password_hash="h2", status=UserStatus.INACTIVE)
    session = FakeAsyncSession(users_by_id={u1.id: u1, u2.id: u2})
    service = UserAdminService(session)  # type: ignore[arg-type]

    users, total = await service.list_users()
    assert total == 2
    assert len(users) == 2


@pytest.mark.asyncio
async def test_update_user_details_and_password() -> None:
    user = User(
        id=uuid4(),
        email="old@example.com",
        password_hash="old-hash",
        status=UserStatus.ACTIVE,
        full_name="Old Name",
        avatar_url="https://old.url",
    )
    admin_role = build_role("admin")
    session = FakeAsyncSession(
        users_by_id={user.id: user},
        users_by_email={user.email: user},
        roles_by_name={"admin": admin_role},
    )
    service = UserAdminService(session)  # type: ignore[arg-type]

    updated = await service.update_user(
        user_id=user.id,
        email="new@example.com",
        status=UserStatus.LOCKED,
        password="NewPassword123!",
        role_names=["admin"],
        full_name="New Name",
        avatar_url="https://new.url",
    )

    assert updated.email == "new@example.com"
    assert updated.status == UserStatus.LOCKED
    assert verify_password("NewPassword123!", updated.password_hash) is True
    assert [r.name for r in updated.roles] == ["admin"]
    assert updated.full_name == "New Name"
    assert updated.avatar_url == "https://new.url"


@pytest.mark.asyncio
async def test_update_user_rejects_duplicate_email() -> None:
    u1 = User(
        id=uuid4(),
        email="user1@example.com",
        password_hash="h1",
        status=UserStatus.ACTIVE,
        full_name="User One",
    )
    u2 = User(
        id=uuid4(),
        email="user2@example.com",
        password_hash="h2",
        status=UserStatus.ACTIVE,
        full_name="User Two",
    )
    session = FakeAsyncSession(
        users_by_id={u1.id: u1, u2.id: u2},
        users_by_email={u1.email: u1, u2.email: u2},
    )
    service = UserAdminService(session)  # type: ignore[arg-type]

    with pytest.raises(EmailAlreadyExistsError):
        await service.update_user(
            user_id=u1.id,
            email="user2@example.com",
            status=UserStatus.ACTIVE,
            role_names=[],
            full_name="User One Updated",
        )


@pytest.mark.asyncio
async def test_delete_user() -> None:
    user = User(
        id=uuid4(),
        email="delete-me@example.com",
        password_hash="h",
        status=UserStatus.ACTIVE,
    )
    session = FakeAsyncSession(users_by_id={user.id: user})
    service = UserAdminService(session)  # type: ignore[arg-type]

    await service.delete_user(user.id)
    assert len(session.deleted) == 1
    assert session.deleted[0] is user
