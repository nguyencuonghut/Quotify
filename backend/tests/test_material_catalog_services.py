from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.models import Material, MaterialType
from app.services.catalog_import import (
    CatalogImportHeaderError,
    build_catalog_import_error_report,
    build_catalog_import_template,
    get_catalog_import_config,
    parse_code_list,
    validate_catalog_import_headers,
)
from app.services.material_admin import (
    MaterialAdminService,
    MaterialAlreadyExistsError,
    MaterialTypeNotFoundForMaterialError,
)
from app.services.material_type_admin import (
    MaterialTypeAdminService,
    MaterialTypeAlreadyExistsError,
    MaterialTypeInUseError,
    normalize_catalog_code,
)


class FakeScalarResult:
    def __init__(self, value: object | None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object | None:
        return self._value

    def scalar_one(self) -> object:
        if self._value is None:
            raise AssertionError("Expected scalar value.")
        return self._value

    def scalars(self) -> FakeScalarResult:
        return self

    def all(self) -> list[object]:
        if isinstance(self._value, list):
            return self._value
        if self._value is None:
            return []
        return [self._value]


class FakeCatalogSession:
    def __init__(
        self,
        *,
        material_types_by_id: dict[UUID, MaterialType] | None = None,
        material_types_by_code: dict[str, MaterialType] | None = None,
        materials_by_id: dict[UUID, Material] | None = None,
        materials_by_code: dict[str, Material] | None = None,
        material_count_by_type_id: dict[UUID, int] | None = None,
    ) -> None:
        self.material_types_by_id = material_types_by_id or {}
        self.material_types_by_code = material_types_by_code or {}
        self.materials_by_id = materials_by_id or {}
        self.materials_by_code = materials_by_code or {}
        self.material_count_by_type_id = material_count_by_type_id or {}
        self.added: list[object] = []
        self.deleted: list[object] = []
        self.flush_count = 0

    async def execute(self, statement: object) -> FakeScalarResult:
        compiled = str(statement)
        params = statement.compile().params  # type: ignore[attr-defined]

        if "count" in compiled and "FROM materials" in compiled:
            material_type_id = params.get("material_type_id_1")
            return FakeScalarResult(self.material_count_by_type_id.get(material_type_id, 0))

        if "FROM material_types" in compiled:
            if "id_1" in params:
                return FakeScalarResult(self.material_types_by_id.get(params["id_1"]))
            if "code_1" in params:
                return FakeScalarResult(self.material_types_by_code.get(params["code_1"]))
            return FakeScalarResult(list(self.material_types_by_id.values()))

        if "FROM materials" in compiled:
            if "id_1" in params:
                return FakeScalarResult(self.materials_by_id.get(params["id_1"]))
            if "code_1" in params:
                return FakeScalarResult(self.materials_by_code.get(params["code_1"]))
            return FakeScalarResult(list(self.materials_by_id.values()))

        raise AssertionError(f"Unexpected statement: {compiled}")

    def add(self, instance: object) -> None:
        self.added.append(instance)
        if isinstance(instance, MaterialType):
            self.material_types_by_id[instance.id] = instance
            self.material_types_by_code[instance.code] = instance
        if isinstance(instance, Material):
            self.materials_by_id[instance.id] = instance
            self.materials_by_code[instance.code] = instance

    async def delete(self, instance: object) -> None:
        self.deleted.append(instance)

    async def flush(self) -> None:
        self.flush_count += 1


def test_normalize_catalog_code_trims_and_uppercases() -> None:
    assert normalize_catalog_code(" corn-01 ") == "CORN-01"


def test_catalog_import_template_contains_expected_headers() -> None:
    config = get_catalog_import_config("materials")

    content = build_catalog_import_template(config).decode("utf-8-sig")

    assert content.splitlines()[0] == "code,name,material_type_code,status,note"


def test_catalog_import_rejects_invalid_headers() -> None:
    config = get_catalog_import_config("material_types")

    with pytest.raises(CatalogImportHeaderError):
        validate_catalog_import_headers(config, ["code", "name"])


def test_catalog_import_error_report_contains_safe_row_summary() -> None:
    content = build_catalog_import_error_report(
        [{"row": 2, "code": "SUP-01", "errors": ["Tên NCC là bắt buộc."]}],
    ).decode("utf-8-sig")

    assert "row,code,errors" in content
    assert "SUP-01" in content
    assert "Tên NCC là bắt buộc." in content


def test_parse_code_list_accepts_comma_or_semicolon() -> None:
    assert parse_code_list(" corn; soybean_meal, ddgs ") == [
        "CORN",
        "SOYBEAN_MEAL",
        "DDGS",
    ]


@pytest.mark.asyncio
async def test_create_material_type_normalizes_code() -> None:
    session = FakeCatalogSession()
    service = MaterialTypeAdminService(session)  # type: ignore[arg-type]

    material_type = await service.create_material_type(
        code=" corn ",
        name=" Ngô ",
        status="active",
        note="  Ghi chú  ",
    )

    assert material_type.code == "CORN"
    assert material_type.name == "Ngô"
    assert material_type.note == "Ghi chú"
    assert session.flush_count == 1


@pytest.mark.asyncio
async def test_create_material_type_rejects_duplicate_normalized_code() -> None:
    existing = MaterialType(id=uuid4(), code="CORN", name="Ngô", status="active")
    session = FakeCatalogSession(material_types_by_code={"CORN": existing})
    service = MaterialTypeAdminService(session)  # type: ignore[arg-type]

    with pytest.raises(MaterialTypeAlreadyExistsError):
        await service.create_material_type(code=" corn ", name="Ngô", status="active")


@pytest.mark.asyncio
async def test_delete_material_type_rejects_type_with_materials() -> None:
    material_type = MaterialType(id=uuid4(), code="CORN", name="Ngô", status="active")
    session = FakeCatalogSession(
        material_types_by_id={material_type.id: material_type},
        material_count_by_type_id={material_type.id: 1},
    )
    service = MaterialTypeAdminService(session)  # type: ignore[arg-type]

    with pytest.raises(MaterialTypeInUseError):
        await service.delete_material_type(material_type.id)


@pytest.mark.asyncio
async def test_create_material_rejects_duplicate_normalized_code() -> None:
    material_type = MaterialType(id=uuid4(), code="CORN", name="Ngô", status="active")
    existing = Material(
        id=uuid4(),
        code="CORN-01",
        name="Ngô hạt",
        material_type_id=material_type.id,
        status="active",
    )
    session = FakeCatalogSession(
        material_types_by_id={material_type.id: material_type},
        materials_by_code={"CORN-01": existing},
    )
    service = MaterialAdminService(session)  # type: ignore[arg-type]

    with pytest.raises(MaterialAlreadyExistsError):
        await service.create_material(
            code=" corn-01 ",
            name="Ngô hạt",
            material_type_id=material_type.id,
            status="active",
        )


@pytest.mark.asyncio
async def test_create_material_rejects_missing_material_type() -> None:
    session = FakeCatalogSession()
    service = MaterialAdminService(session)  # type: ignore[arg-type]

    with pytest.raises(MaterialTypeNotFoundForMaterialError):
        await service.create_material(
            code="CORN-01",
            name="Ngô hạt",
            material_type_id=uuid4(),
            status="active",
        )
