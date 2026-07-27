from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.models import Material, Supplier, SupplierMaterial
from app.schemas.supplier import SupplierContactRequest
from app.services.supplier_admin import (
    SupplierAdminService,
    SupplierDuplicateMaterialError,
    SupplierMaterialUnavailableError,
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


class FakeSupplierSession:
    def __init__(
        self,
        *,
        suppliers_by_id: dict[UUID, Supplier] | None = None,
        suppliers_by_code: dict[str, Supplier] | None = None,
        materials_by_id: dict[UUID, Material] | None = None,
    ) -> None:
        self.suppliers_by_id = suppliers_by_id or {}
        self.suppliers_by_code = suppliers_by_code or {}
        self.materials_by_id = materials_by_id or {}
        self.added: list[object] = []
        self.deleted: list[object] = []
        self.flush_count = 0

    async def execute(self, statement: object) -> FakeScalarResult:
        compiled = str(statement)
        params = statement.compile().params  # type: ignore[attr-defined]

        if "FROM suppliers" in compiled and "JOIN supplier_materials" in compiled:
            material_id = params.get("material_id_1")
            return FakeScalarResult(
                [
                    supplier
                    for supplier in self.suppliers_by_id.values()
                    if supplier.status == "active"
                    and any(
                        supplier_material.material_id == material_id
                        for supplier_material in supplier.supplier_materials
                    )
                ],
            )

        if "FROM suppliers" in compiled:
            if "id_1" in params:
                return FakeScalarResult(self.suppliers_by_id.get(params["id_1"]))
            if "code_1" in params:
                return FakeScalarResult(self.suppliers_by_code.get(params["code_1"]))
            return FakeScalarResult(list(self.suppliers_by_id.values()))

        if "FROM materials" in compiled:
            return FakeScalarResult(
                [
                    material
                    for material in self.materials_by_id.values()
                    if material.status == "active"
                ],
            )

        if "count" in compiled:
            return FakeScalarResult(len(self.suppliers_by_id))

        raise AssertionError(f"Unexpected statement: {compiled}")

    def add(self, instance: object) -> None:
        self.added.append(instance)
        if isinstance(instance, Supplier):
            if instance.id is None:
                instance.id = uuid4()
            self.suppliers_by_id[instance.id] = instance
            self.suppliers_by_code[instance.code] = instance

    async def delete(self, instance: object) -> None:
        self.deleted.append(instance)

    async def flush(self) -> None:
        self.flush_count += 1


@pytest.mark.asyncio
async def test_create_supplier_with_contacts_and_materials() -> None:
    material = Material(id=uuid4(), code="CORN", name="Ngô hạt", status="active")
    session = FakeSupplierSession(materials_by_id={material.id: material})
    service = SupplierAdminService(session)  # type: ignore[arg-type]

    supplier = await service.create_supplier(
        code=" sup-01 ",
        name=" Nhà cung cấp A ",
        supplier_type="domestic",
        status="active",
        contacts=[
            SupplierContactRequest(
                name=" Nguyễn Văn A ",
                email="a@example.com",
                phone=" 0900000000 ",
                status="active",
            ),
        ],
        material_ids=[material.id],
    )

    assert supplier.code == "SUP-01"
    assert supplier.name == "Nhà cung cấp A"
    assert supplier.contacts[0].name == "Nguyễn Văn A"
    assert supplier.contacts[0].phone == "0900000000"
    assert supplier.supplier_materials[0].material_id == material.id
    assert session.flush_count == 1


@pytest.mark.asyncio
async def test_create_supplier_rejects_duplicate_material_ids() -> None:
    material_id = uuid4()
    service = SupplierAdminService(FakeSupplierSession())  # type: ignore[arg-type]

    with pytest.raises(SupplierDuplicateMaterialError):
        await service.create_supplier(
            code="SUP-01",
            name="Nhà cung cấp A",
            supplier_type="domestic",
            status="active",
            material_ids=[material_id, material_id],
        )


@pytest.mark.asyncio
async def test_create_supplier_rejects_inactive_or_missing_materials() -> None:
    inactive_material = Material(
        id=uuid4(),
        code="CORN",
        name="Ngô hạt",
        status="inactive",
    )
    session = FakeSupplierSession(materials_by_id={inactive_material.id: inactive_material})
    service = SupplierAdminService(session)  # type: ignore[arg-type]

    with pytest.raises(SupplierMaterialUnavailableError):
        await service.create_supplier(
            code="SUP-01",
            name="Nhà cung cấp A",
            supplier_type="domestic",
            status="active",
            material_ids=[inactive_material.id],
        )


@pytest.mark.asyncio
async def test_lookup_suppliers_by_material_returns_active_suppliers() -> None:
    material_id = uuid4()
    active_supplier = Supplier(
        id=uuid4(),
        code="SUP-01",
        name="Nhà cung cấp A",
        supplier_type="domestic",
        status="active",
    )
    active_supplier.supplier_materials = [SupplierMaterial(material_id=material_id)]
    inactive_supplier = Supplier(
        id=uuid4(),
        code="SUP-02",
        name="Nhà cung cấp B",
        supplier_type="domestic",
        status="inactive",
    )
    inactive_supplier.supplier_materials = [SupplierMaterial(material_id=material_id)]
    session = FakeSupplierSession(
        suppliers_by_id={
            active_supplier.id: active_supplier,
            inactive_supplier.id: inactive_supplier,
        },
    )
    service = SupplierAdminService(session)  # type: ignore[arg-type]

    suppliers = await service.lookup_suppliers_by_material(material_id)

    assert [supplier.code for supplier in suppliers] == ["SUP-01"]
