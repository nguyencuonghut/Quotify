from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.v1.suppliers import get_audit_log_service, get_supplier_admin_service
from app.auth.dependencies import get_current_user
from app.db.session import get_db_session
from app.models import (
    Material,
    Permission,
    Role,
    Supplier,
    SupplierContact,
    SupplierMaterial,
    User,
    UserStatus,
)
from app.services import SupplierAlreadyExistsError, SupplierNotFoundError


class MockSession:
    async def commit(self) -> None:
        pass


class MockAuditLogService:
    async def log_event(self, **kwargs: Any) -> None:
        pass


class MockSupplierAdminService:
    def __init__(self, supplier: Supplier) -> None:
        self.supplier = supplier

    async def list_suppliers(self, **kwargs: Any) -> tuple[list[Supplier], int]:
        return [self.supplier], 1

    async def lookup_suppliers_by_material(self, material_id: UUID) -> list[Supplier]:
        if self.supplier.supplier_materials[0].material_id == material_id:
            return [self.supplier]
        return []

    async def get_supplier_by_id(self, supplier_id: UUID) -> Supplier:
        if supplier_id != self.supplier.id:
            raise SupplierNotFoundError("NCC không tồn tại.")
        return self.supplier

    async def create_supplier(self, **kwargs: Any) -> Supplier:
        if kwargs["code"] == self.supplier.code:
            raise SupplierAlreadyExistsError("Mã NCC đã tồn tại.")
        return self.supplier

    async def update_supplier(self, **kwargs: Any) -> Supplier:
        return self.supplier

    async def delete_supplier(self, supplier_id: UUID) -> None:
        if supplier_id != self.supplier.id:
            raise SupplierNotFoundError("NCC không tồn tại.")


@pytest.fixture
def override_dependencies(app: FastAPI) -> Generator[MockSupplierAdminService, None, None]:
    now = datetime.now(UTC)
    material = Material(
        id=uuid4(),
        code="CORN",
        name="Ngô hạt",
        status="active",
        created_at=now,
        updated_at=now,
    )
    supplier = Supplier(
        id=uuid4(),
        code="SUP-01",
        name="Nhà cung cấp A",
        supplier_type="domestic",
        status="active",
        tax_code="0100000000",
        address="Hà Nội",
        note=None,
        created_at=now,
        updated_at=now,
    )
    supplier.contacts = [
        SupplierContact(
            id=uuid4(),
            name="Nguyễn Văn A",
            title="Sales",
            email="sales@example.com",
            phone="0900000000",
            status="active",
            created_at=now,
            updated_at=now,
        ),
    ]
    supplier.supplier_materials = [
        SupplierMaterial(
            supplier_id=supplier.id,
            material_id=material.id,
            material=material,
            created_at=now,
        ),
    ]

    permission = Permission(id=uuid4(), code="suppliers.read")
    admin_role = Role(id=uuid4(), name="admin", is_system=True)
    admin_role.permissions = [permission]
    admin_user = User(id=uuid4(), email="admin@example.com", status=UserStatus.ACTIVE)
    admin_user.roles = [admin_role]

    mock_service = MockSupplierAdminService(supplier)
    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[get_supplier_admin_service] = lambda: mock_service
    app.dependency_overrides[get_audit_log_service] = lambda: MockAuditLogService()
    app.dependency_overrides[get_db_session] = lambda: MockSession()

    yield mock_service

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_suppliers_api_returns_child_data(
    client: AsyncClient,
    override_dependencies: MockSupplierAdminService,
) -> None:
    response = await client.get("/api/v1/suppliers")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["code"] == "SUP-01"
    assert data["items"][0]["contacts"][0]["name"] == "Nguyễn Văn A"
    assert data["items"][0]["materials"][0]["material_name"] == "Ngô hạt"


@pytest.mark.asyncio
async def test_lookup_suppliers_api_filters_by_material(
    client: AsyncClient,
    override_dependencies: MockSupplierAdminService,
) -> None:
    material_id = override_dependencies.supplier.supplier_materials[0].material_id

    response = await client.get(f"/api/v1/suppliers/lookup?material_id={material_id}")

    assert response.status_code == 200
    assert response.json()["items"][0]["code"] == "SUP-01"


@pytest.mark.asyncio
async def test_create_supplier_api_rejects_duplicate_code(
    client: AsyncClient,
    override_dependencies: MockSupplierAdminService,
) -> None:
    payload = {
        "code": "SUP-01",
        "name": "Nhà cung cấp A",
        "supplier_type": "domestic",
        "status": "active",
        "contacts": [],
        "material_ids": [],
    }

    response = await client.post("/api/v1/suppliers", json=payload)

    assert response.status_code == 409
