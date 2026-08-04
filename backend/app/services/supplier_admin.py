from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import set_committed_value
from sqlalchemy.sql.elements import ColumnElement

from app.models import Material, Supplier, SupplierContact, SupplierMaterial
from app.schemas.supplier import SupplierContactRequest, SupplierType, normalize_supplier_types
from app.services.material_type_admin import normalize_catalog_code, normalize_optional_text


class SupplierAlreadyExistsError(Exception):
    """Raised when a supplier code already exists."""


class SupplierDuplicateMaterialError(Exception):
    """Raised when payload contains duplicate material assignments."""


class SupplierInUseError(Exception):
    """Raised when a supplier is referenced by downstream quote data."""


class SupplierMaterialUnavailableError(Exception):
    """Raised when assigning a missing or inactive material to a supplier."""


class SupplierNotFoundError(Exception):
    """Raised when the target supplier does not exist."""


class SupplierAdminService:
    SORT_COLUMNS = {
        "code": Supplier.code,
        "name": Supplier.name,
        "supplier_type": Supplier.supplier_type,
        "status": Supplier.status,
        "created_at": Supplier.created_at,
        "updated_at": Supplier.updated_at,
    }

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_supplier(
        self,
        *,
        code: str,
        name: str,
        supplier_type: Sequence[SupplierType],
        status: str,
        tax_code: str | None = None,
        address: str | None = None,
        note: str | None = None,
        contacts: Sequence[SupplierContactRequest] = (),
        material_ids: Sequence[UUID] = (),
    ) -> Supplier:
        normalized_code = normalize_catalog_code(code)
        if await self._get_by_code(normalized_code) is not None:
            raise SupplierAlreadyExistsError(f"NCC với mã '{normalized_code}' đã tồn tại.")

        materials = await self._get_assignable_materials(material_ids)
        supplier = Supplier(
            code=normalized_code,
            name=name.strip(),
            supplier_type=normalize_supplier_types(supplier_type),
            status=status,
            tax_code=normalize_optional_text(tax_code),
            address=normalize_optional_text(address),
            note=normalize_optional_text(note),
        )
        set_committed_value(supplier, "contacts", [])
        set_committed_value(supplier, "supplier_materials", [])
        supplier.contacts = self._build_contacts(contacts)
        supplier.supplier_materials = [
            SupplierMaterial(material_id=material.id) for material in materials
        ]
        self.session.add(supplier)
        await self.session.flush()
        return await self.get_supplier_by_id(supplier.id)

    async def get_supplier_by_id(self, supplier_id: UUID) -> Supplier:
        supplier = await self._get_by_id(supplier_id)
        if supplier is None:
            raise SupplierNotFoundError(f"NCC {supplier_id} không tồn tại.")
        return supplier

    async def list_suppliers(
        self,
        *,
        limit: int = 10,
        offset: int = 0,
        search: str | None = None,
        supplier_type: str | None = None,
        status: str | None = None,
        sort_by: str = "code",
        sort_order: str = "asc",
    ) -> tuple[Sequence[Supplier], int]:
        stmt = select(Supplier).options(
            selectinload(Supplier.contacts),
            selectinload(Supplier.supplier_materials).selectinload(SupplierMaterial.material),
        )

        if search:
            normalized_search = search.strip()
            stmt = stmt.where(
                Supplier.code.ilike(f"%{normalized_search}%")
                | Supplier.name.ilike(f"%{normalized_search}%"),
            )
        if supplier_type:
            stmt = stmt.where(_supplier_type_contains(supplier_type))
        if status:
            stmt = stmt.where(Supplier.status == status)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar_one()

        sort_attr = self.SORT_COLUMNS.get(sort_by, Supplier.code)
        stmt = stmt.order_by(sort_attr.desc() if sort_order.lower() == "desc" else sort_attr.asc())
        stmt = stmt.offset(offset).limit(limit)

        result = await self.session.execute(stmt)
        return result.scalars().all(), total

    async def lookup_suppliers_by_material(self, material_id: UUID) -> Sequence[Supplier]:
        stmt = (
            select(Supplier)
            .join(SupplierMaterial)
            .where(Supplier.status == "active", SupplierMaterial.material_id == material_id)
            .options(
                selectinload(Supplier.contacts),
                selectinload(Supplier.supplier_materials).selectinload(SupplierMaterial.material),
            )
            .order_by(Supplier.code.asc())
            .limit(100)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update_supplier(
        self,
        *,
        supplier_id: UUID,
        code: str,
        name: str,
        supplier_type: Sequence[SupplierType],
        status: str,
        tax_code: str | None = None,
        address: str | None = None,
        note: str | None = None,
        contacts: Sequence[SupplierContactRequest] = (),
        material_ids: Sequence[UUID] = (),
    ) -> Supplier:
        supplier = await self._get_by_id(supplier_id)
        if supplier is None:
            raise SupplierNotFoundError(f"NCC {supplier_id} không tồn tại.")

        normalized_code = normalize_catalog_code(code)
        if normalized_code != supplier.code:
            existing = await self._get_by_code(normalized_code)
            if existing is not None:
                raise SupplierAlreadyExistsError(
                    f"NCC với mã '{normalized_code}' đã tồn tại.",
                )
            supplier.code = normalized_code

        materials = await self._get_assignable_materials(material_ids)
        supplier.name = name.strip()
        supplier.supplier_type = normalize_supplier_types(supplier_type)
        supplier.status = status
        supplier.tax_code = normalize_optional_text(tax_code)
        supplier.address = normalize_optional_text(address)
        supplier.note = normalize_optional_text(note)
        supplier.contacts = self._build_contacts(contacts)
        self._sync_supplier_materials(supplier, materials)

        await self.session.flush()
        return await self.get_supplier_by_id(supplier.id)

    async def delete_supplier(self, supplier_id: UUID) -> None:
        supplier = await self._get_by_id(supplier_id)
        if supplier is None:
            raise SupplierNotFoundError(f"NCC {supplier_id} không tồn tại.")

        await self.session.delete(supplier)
        await self.session.flush()

    async def _get_assignable_materials(
        self,
        material_ids: Sequence[UUID],
    ) -> Sequence[Material]:
        unique_material_ids = list(dict.fromkeys(material_ids))
        if len(unique_material_ids) != len(material_ids):
            raise SupplierDuplicateMaterialError("Danh sách vật tư cung cấp bị trùng.")
        if not unique_material_ids:
            return []

        result = await self.session.execute(
            select(Material).where(
                Material.id.in_(unique_material_ids),
                Material.status == "active",
            ),
        )
        materials = result.scalars().all()
        found_ids = {material.id for material in materials}
        if set(unique_material_ids) != found_ids:
            raise SupplierMaterialUnavailableError(
                "Chỉ được gắn vật tư đang active vào NCC.",
            )
        return materials

    async def _get_by_id(self, supplier_id: UUID) -> Supplier | None:
        result = await self.session.execute(
            select(Supplier)
            .options(
                selectinload(Supplier.contacts),
                selectinload(Supplier.supplier_materials).selectinload(SupplierMaterial.material),
            )
            .where(Supplier.id == supplier_id),
        )
        return result.scalar_one_or_none()

    async def _get_by_code(self, code: str) -> Supplier | None:
        result = await self.session.execute(select(Supplier).where(Supplier.code == code))
        return result.scalar_one_or_none()

    def _build_contacts(
        self,
        contacts: Sequence[SupplierContactRequest],
    ) -> list[SupplierContact]:
        return [
            SupplierContact(
                name=contact.name.strip(),
                title=normalize_optional_text(contact.title),
                email=normalize_optional_text(contact.email),
                phone=normalize_optional_text(contact.phone),
                status=contact.status,
            )
            for contact in contacts
        ]

    def _sync_supplier_materials(
        self,
        supplier: Supplier,
        materials: Sequence[Material],
    ) -> None:
        existing_by_material_id = {
            supplier_material.material_id: supplier_material
            for supplier_material in supplier.supplier_materials
        }
        supplier.supplier_materials = [
            existing_by_material_id.get(material.id)
            or SupplierMaterial(material_id=material.id, material=material)
            for material in materials
        ]


def _supplier_type_contains(supplier_type: str) -> ColumnElement[bool]:
    return func.concat(",", Supplier.supplier_type, ",").like(f"%,{supplier_type},%")
