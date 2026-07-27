from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Material, MaterialType
from app.services.material_type_admin import normalize_catalog_code, normalize_optional_text


class MaterialAlreadyExistsError(Exception):
    """Raised when a material code already exists."""


class MaterialInUseError(Exception):
    """Raised when a material is referenced by downstream quote data."""


class MaterialNotFoundError(Exception):
    """Raised when the target material does not exist."""


class MaterialTypeNotFoundForMaterialError(Exception):
    """Raised when assigning a material to a missing material type."""


class MaterialAdminService:
    SORT_COLUMNS = {
        "code": Material.code,
        "name": Material.name,
        "status": Material.status,
        "created_at": Material.created_at,
        "updated_at": Material.updated_at,
    }

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_material(
        self,
        *,
        code: str,
        name: str,
        material_type_id: UUID,
        status: str,
        note: str | None = None,
    ) -> Material:
        normalized_code = normalize_catalog_code(code)
        if await self._get_by_code(normalized_code) is not None:
            raise MaterialAlreadyExistsError(f"Vật tư với mã '{normalized_code}' đã tồn tại.")

        await self._ensure_material_type_exists(material_type_id)
        material = Material(
            code=normalized_code,
            name=name.strip(),
            material_type_id=material_type_id,
            status=status,
            note=normalize_optional_text(note),
        )
        self.session.add(material)
        await self.session.flush()
        return await self.get_material_by_id(material.id)

    async def get_material_by_id(self, material_id: UUID) -> Material:
        material = await self._get_by_id(material_id)
        if material is None:
            raise MaterialNotFoundError(f"Vật tư {material_id} không tồn tại.")
        return material

    async def list_materials(
        self,
        *,
        limit: int = 10,
        offset: int = 0,
        search: str | None = None,
        status: str | None = None,
        material_type_id: UUID | None = None,
        sort_by: str = "code",
        sort_order: str = "asc",
    ) -> tuple[Sequence[Material], int]:
        stmt = select(Material).options(selectinload(Material.material_type))

        if search:
            normalized_search = search.strip()
            stmt = stmt.where(
                Material.code.ilike(f"%{normalized_search}%")
                | Material.name.ilike(f"%{normalized_search}%"),
            )
        if status:
            stmt = stmt.where(Material.status == status)
        if material_type_id:
            stmt = stmt.where(Material.material_type_id == material_type_id)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar_one()

        sort_attr = self.SORT_COLUMNS.get(sort_by, Material.code)
        stmt = stmt.order_by(sort_attr.desc() if sort_order.lower() == "desc" else sort_attr.asc())
        stmt = stmt.offset(offset).limit(limit)

        result = await self.session.execute(stmt)
        return result.scalars().all(), total

    async def update_material(
        self,
        *,
        material_id: UUID,
        code: str,
        name: str,
        material_type_id: UUID,
        status: str,
        note: str | None = None,
    ) -> Material:
        material = await self._get_by_id(material_id)
        if material is None:
            raise MaterialNotFoundError(f"Vật tư {material_id} không tồn tại.")

        normalized_code = normalize_catalog_code(code)
        if normalized_code != material.code:
            existing = await self._get_by_code(normalized_code)
            if existing is not None:
                raise MaterialAlreadyExistsError(f"Vật tư với mã '{normalized_code}' đã tồn tại.")
            material.code = normalized_code

        await self._ensure_material_type_exists(material_type_id)
        material.name = name.strip()
        material.material_type_id = material_type_id
        material.status = status
        material.note = normalize_optional_text(note)

        await self.session.flush()
        return await self.get_material_by_id(material.id)

    async def delete_material(self, material_id: UUID) -> None:
        material = await self._get_by_id(material_id)
        if material is None:
            raise MaterialNotFoundError(f"Vật tư {material_id} không tồn tại.")

        await self.session.delete(material)
        await self.session.flush()

    async def _ensure_material_type_exists(self, material_type_id: UUID) -> None:
        result = await self.session.execute(
            select(MaterialType.id).where(MaterialType.id == material_type_id),
        )
        if result.scalar_one_or_none() is None:
            raise MaterialTypeNotFoundForMaterialError(
                f"Loại vật tư {material_type_id} không tồn tại.",
            )

    async def _get_by_id(self, material_id: UUID) -> Material | None:
        result = await self.session.execute(
            select(Material)
            .options(selectinload(Material.material_type))
            .where(Material.id == material_id),
        )
        return result.scalar_one_or_none()

    async def _get_by_code(self, code: str) -> Material | None:
        result = await self.session.execute(select(Material).where(Material.code == code))
        return result.scalar_one_or_none()
