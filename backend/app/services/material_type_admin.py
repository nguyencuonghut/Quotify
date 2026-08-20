from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Material, MaterialType


class MaterialTypeAlreadyExistsError(Exception):
    """Raised when a material type code already exists."""


class MaterialTypeInUseError(Exception):
    """Raised when a material type is referenced by materials."""


class MaterialTypeNotFoundError(Exception):
    """Raised when the target material type does not exist."""


class MaterialTypeAdminService:
    SORT_COLUMNS = {
        "code": MaterialType.code,
        "name": MaterialType.name,
        "status": MaterialType.status,
        "created_at": MaterialType.created_at,
        "updated_at": MaterialType.updated_at,
    }

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_material_type(
        self,
        *,
        code: str,
        name: str,
        status: str,
        note: str | None = None,
    ) -> MaterialType:
        normalized_code = normalize_catalog_code(code)
        existing = await self._get_by_code(normalized_code)
        if existing is not None:
            raise MaterialTypeAlreadyExistsError(
                f"Loại vật tư với mã '{normalized_code}' đã tồn tại.",
            )

        material_type = MaterialType(
            code=normalized_code,
            name=name.strip(),
            status=status,
            note=normalize_optional_text(note),
        )
        self.session.add(material_type)
        await self.session.flush()
        return material_type

    async def get_material_type_by_id(self, material_type_id: UUID) -> MaterialType:
        material_type = await self._get_by_id(material_type_id)
        if material_type is None:
            raise MaterialTypeNotFoundError(f"Loại vật tư {material_type_id} không tồn tại.")
        return material_type

    async def list_material_types(
        self,
        *,
        limit: int = 10,
        offset: int = 0,
        search: str | None = None,
        status: str | None = None,
        sort_by: str = "code",
        sort_order: str = "asc",
    ) -> tuple[Sequence[MaterialType], int]:
        stmt = select(MaterialType)

        if search:
            normalized_search = search.strip()
            stmt = stmt.where(
                MaterialType.code.ilike(f"%{normalized_search}%")
                | MaterialType.name.ilike(f"%{normalized_search}%"),
            )
        if status:
            stmt = stmt.where(MaterialType.status == status)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar_one()

        sort_attr = self.SORT_COLUMNS.get(sort_by, MaterialType.code)
        stmt = stmt.order_by(sort_attr.desc() if sort_order.lower() == "desc" else sort_attr.asc())
        stmt = stmt.offset(offset).limit(limit)

        result = await self.session.execute(stmt)
        return result.scalars().all(), total

    async def lookup_active_material_types(self) -> Sequence[MaterialType]:
        """Toàn bộ loại vật tư active, không phân trang — dùng cho dropdown
        lọc/gán loại vật tư, khác `list_material_types` (có phân trang, dùng
        cho bảng quản trị). Xem cùng lý do ở
        `SupplierAdminService.lookup_suppliers_by_material`."""
        stmt = (
            select(MaterialType)
            .where(MaterialType.status == "active")
            .order_by(MaterialType.name.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update_material_type(
        self,
        *,
        material_type_id: UUID,
        code: str,
        name: str,
        status: str,
        note: str | None = None,
    ) -> MaterialType:
        material_type = await self._get_by_id(material_type_id)
        if material_type is None:
            raise MaterialTypeNotFoundError(f"Loại vật tư {material_type_id} không tồn tại.")

        normalized_code = normalize_catalog_code(code)
        if normalized_code != material_type.code:
            existing = await self._get_by_code(normalized_code)
            if existing is not None:
                raise MaterialTypeAlreadyExistsError(
                    f"Loại vật tư với mã '{normalized_code}' đã tồn tại.",
                )
            material_type.code = normalized_code

        material_type.name = name.strip()
        material_type.status = status
        material_type.note = normalize_optional_text(note)

        await self.session.flush()
        return material_type

    async def delete_material_type(self, material_type_id: UUID) -> None:
        material_type = await self._get_by_id(material_type_id)
        if material_type is None:
            raise MaterialTypeNotFoundError(f"Loại vật tư {material_type_id} không tồn tại.")

        count_result = await self.session.execute(
            select(func.count()).select_from(Material).where(
                Material.material_type_id == material_type_id,
            ),
        )
        if count_result.scalar_one() > 0:
            raise MaterialTypeInUseError(
                "Không thể xóa loại vật tư đang có vật tư. Hãy chuyển trạng thái inactive.",
            )

        await self.session.delete(material_type)
        await self.session.flush()

    async def _get_by_id(self, material_type_id: UUID) -> MaterialType | None:
        result = await self.session.execute(
            select(MaterialType).where(MaterialType.id == material_type_id),
        )
        return result.scalar_one_or_none()

    async def _get_by_code(self, code: str) -> MaterialType | None:
        result = await self.session.execute(select(MaterialType).where(MaterialType.code == code))
        return result.scalar_one_or_none()


def normalize_catalog_code(code: str) -> str:
    return code.strip().upper()


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None
