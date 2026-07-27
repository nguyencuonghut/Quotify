from __future__ import annotations

from collections.abc import Sequence
from uuid import uuid4

import pytest

from app.models import Material, MaterialType
from app.quotify.seed_data import MATERIAL_SEEDS, MATERIAL_TYPE_SEEDS
from app.services.quotify_seed import QuotifySeedService


class FakeScalarResult:
    def __init__(self, value: Sequence[object]) -> None:
        self._value = value

    def scalars(self) -> FakeScalarResult:
        return self

    def all(self) -> list[object]:
        return list(self._value)


class FakeSeedSession:
    def __init__(
        self,
        *,
        material_types: list[MaterialType] | None = None,
        materials: list[Material] | None = None,
    ) -> None:
        self.material_types = material_types or []
        self.materials = materials or []
        self.flush_count = 0
        self.commit_count = 0

    async def execute(self, statement: object) -> FakeScalarResult:
        compiled = str(statement)
        if "FROM material_types" in compiled:
            return FakeScalarResult(self.material_types)
        if "FROM materials" in compiled:
            return FakeScalarResult(self.materials)

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

    async def flush(self) -> None:
        self.flush_count += 1

    async def commit(self) -> None:
        self.commit_count += 1


@pytest.mark.asyncio
async def test_quotify_seed_creates_material_types_and_materials() -> None:
    session = FakeSeedSession()
    service = QuotifySeedService(session)  # type: ignore[arg-type]

    summary = await service.seed()

    assert summary.created_material_types == len(MATERIAL_TYPE_SEEDS)
    assert summary.created_materials == len(MATERIAL_SEEDS)
    assert {material_type.name for material_type in session.material_types} == {
        "Nguyên liệu",
        "Vi lượng",
    }
    assert all(material.code == material.code.strip().upper() for material in session.materials)
    assert all(material.status == "active" for material in session.materials)
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
    session = FakeSeedSession(material_types=material_types, materials=materials)
    service = QuotifySeedService(session)  # type: ignore[arg-type]

    summary = await service.seed()

    assert summary.created_material_types == 0
    assert summary.created_materials == 0
    assert len(session.material_types) == len(MATERIAL_TYPE_SEEDS)
    assert len(session.materials) == len(MATERIAL_SEEDS)
    assert session.commit_count == 1
