from __future__ import annotations

from collections.abc import Sequence
from uuid import uuid4

import pytest

from app.auth.seed_data import USER_ROLE_NAME
from app.models import Material, MaterialType, Role, Supplier, SupplierMaterial, User, UserStatus
from app.quotify.seed_data import (
    MATERIAL_SEEDS,
    MATERIAL_TYPE_SEEDS,
    QUOTIFY_USER_SEEDS,
    SUPPLIER_SEEDS,
)
from app.services.quotify_seed import QuotifySeedService


class FakeScalarResult:
    def __init__(self, value: Sequence[object]) -> None:
        self._value = value

    def scalars(self) -> FakeScalarResult:
        return self

    def all(self) -> list[object]:
        return list(self._value)

    def scalar_one(self) -> object:
        if len(self._value) != 1:
            raise AssertionError(f"Expected exactly one row, got {len(self._value)}")
        return self._value[0]


class FakeSeedSession:
    def __init__(
        self,
        *,
        material_types: list[MaterialType] | None = None,
        materials: list[Material] | None = None,
        suppliers: list[Supplier] | None = None,
        supplier_materials: list[SupplierMaterial] | None = None,
        roles: list[Role] | None = None,
        users: list[User] | None = None,
    ) -> None:
        self.material_types = material_types or []
        self.materials = materials or []
        self.suppliers = suppliers or []
        self.supplier_materials = supplier_materials or []
        self.roles = roles or [Role(id=uuid4(), name=USER_ROLE_NAME, is_system=True)]
        self.users = users or []
        self.flush_count = 0
        self.commit_count = 0

    async def execute(self, statement: object) -> FakeScalarResult:
        compiled = str(statement)
        if "FROM material_types" in compiled:
            return FakeScalarResult(self.material_types)
        if "FROM materials" in compiled:
            return FakeScalarResult(self.materials)
        if "FROM suppliers" in compiled:
            return FakeScalarResult(self.suppliers)
        if "FROM supplier_materials" in compiled:
            return FakeScalarResult(self.supplier_materials)
        if "FROM roles" in compiled:
            return FakeScalarResult(self.roles)
        if "FROM users" in compiled:
            return FakeScalarResult(self.users)

        raise AssertionError(f"Unexpected statement: {compiled}")

    def add(self, instance: object) -> None:
        if isinstance(instance, MaterialType):
            if instance.id is None:
                instance.id = uuid4()
            self.material_types.append(instance)
        if isinstance(instance, Material):
            if instance.id is None:
                instance.id = uuid4()
            self.materials.append(instance)
        if isinstance(instance, Supplier):
            if instance.id is None:
                instance.id = uuid4()
            self.suppliers.append(instance)
        if isinstance(instance, SupplierMaterial):
            self.supplier_materials.append(instance)
        if isinstance(instance, User):
            if instance.id is None:
                instance.id = uuid4()
            self.users.append(instance)

    async def flush(self) -> None:
        self.flush_count += 1

    async def commit(self) -> None:
        self.commit_count += 1


@pytest.mark.asyncio
async def test_quotify_seed_creates_catalogs_suppliers_and_users() -> None:
    session = FakeSeedSession()
    service = QuotifySeedService(session)  # type: ignore[arg-type]

    summary = await service.seed()

    assert summary.created_material_types == len(MATERIAL_TYPE_SEEDS)
    assert summary.created_materials == len(MATERIAL_SEEDS)
    assert summary.created_suppliers == len(SUPPLIER_SEEDS)
    assert summary.created_users == len(QUOTIFY_USER_SEEDS)
    assert {material_type.name for material_type in session.material_types} == {
        material_type.name for material_type in MATERIAL_TYPE_SEEDS
    }
    assert all(material.code == material.code.strip().upper() for material in session.materials)
    assert all(material.status == "active" for material in session.materials)
    assert {supplier.code for supplier in session.suppliers} == {
        supplier.code for supplier in SUPPLIER_SEEDS
    }
    assert {user.email for user in session.users} == {
        user.email.rstrip(".").lower() for user in QUOTIFY_USER_SEEDS
    }
    assert all(user.status == UserStatus.ACTIVE for user in session.users)
    assert all(user.roles[0].name == USER_ROLE_NAME for user in session.users)
    assert session.commit_count == 1


@pytest.mark.asyncio
async def test_quotify_seed_material_catalog_skips_suppliers_and_users() -> None:
    session = FakeSeedSession()
    service = QuotifySeedService(session)  # type: ignore[arg-type]

    summary = await service.seed_material_catalog()

    assert summary.created_material_types == len(MATERIAL_TYPE_SEEDS)
    assert summary.created_materials == len(MATERIAL_SEEDS)
    assert session.suppliers == []
    assert session.users == []
    assert session.commit_count == 1


@pytest.mark.asyncio
async def test_quotify_seed_material_types_skips_materials_suppliers_and_users() -> None:
    session = FakeSeedSession()
    service = QuotifySeedService(session)  # type: ignore[arg-type]

    summary = await service.seed_material_types()

    assert summary.created_material_types == len(MATERIAL_TYPE_SEEDS)
    assert session.materials == []
    assert session.suppliers == []
    assert session.users == []
    assert session.commit_count == 1


@pytest.mark.asyncio
async def test_quotify_seed_is_idempotent() -> None:
    material_type_ids = {seed.code: uuid4() for seed in MATERIAL_TYPE_SEEDS}
    material_types = [
        MaterialType(
            id=material_type_ids[seed.code],
            code=seed.code,
            name=seed.name,
            status="active",
            note=seed.note,
        )
        for seed in MATERIAL_TYPE_SEEDS
    ]
    materials = [
        Material(
            id=uuid4(),
            code=seed.code,
            name=seed.name,
            material_type_id=material_type_ids[seed.material_type_code],
            status="active",
            note=seed.note,
        )
        for seed in MATERIAL_SEEDS
    ]
    suppliers = [
        Supplier(
            id=uuid4(),
            code=seed.code,
            name=seed.name,
            supplier_type=seed.supplier_type,
            status=seed.status,
            note=seed.note,
        )
        for seed in SUPPLIER_SEEDS
    ]
    users = [
        User(
            id=uuid4(),
            email=seed.email.rstrip(".").lower(),
            password_hash="existing-hash",
            status=UserStatus.ACTIVE,
            full_name=seed.full_name,
        )
        for seed in QUOTIFY_USER_SEEDS
    ]
    session = FakeSeedSession(
        material_types=material_types,
        materials=materials,
        suppliers=suppliers,
        users=users,
    )
    service = QuotifySeedService(session)  # type: ignore[arg-type]

    summary = await service.seed()

    assert summary.created_material_types == 0
    assert summary.created_materials == 0
    assert summary.created_suppliers == 0
    assert summary.created_users == 0
    assert len(session.material_types) == len(MATERIAL_TYPE_SEEDS)
    assert len(session.materials) == len(MATERIAL_SEEDS)
    assert len(session.suppliers) == len(SUPPLIER_SEEDS)
    assert len(session.users) == len(QUOTIFY_USER_SEEDS)
    assert all(user.password_hash == "existing-hash" for user in session.users)
    assert session.commit_count == 1


@pytest.mark.asyncio
async def test_quotify_seed_renames_legacy_user_email() -> None:
    legacy_user = User(
        id=uuid4(),
        email="phamthitrang@honghafeed.com",
        password_hash="existing-hash",
        status=UserStatus.INACTIVE,
        full_name="Phạm Thị Trang",
    )
    session = FakeSeedSession(users=[legacy_user])
    service = QuotifySeedService(session)  # type: ignore[arg-type]

    await service._ensure_users()

    assert len(session.users) == len(QUOTIFY_USER_SEEDS)
    assert legacy_user.email == "phamthitrang@honghafeed.com.vn"
    assert legacy_user.password_hash == "existing-hash"
    assert legacy_user.status == UserStatus.ACTIVE
    assert "phamthitrang@honghafeed.com" not in {user.email for user in session.users}
