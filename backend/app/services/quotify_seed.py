from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Material, MaterialType
from app.quotify.seed_data import MATERIAL_SEEDS, MATERIAL_TYPE_SEEDS


@dataclass(slots=True, frozen=True)
class QuotifySeedSummary:
    created_material_types: int
    created_materials: int


class QuotifySeedService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def seed(self) -> QuotifySeedSummary:
        material_types, created_material_types = await self._ensure_material_types()
        created_materials = await self._ensure_materials(material_types)
        await self.session.commit()

        return QuotifySeedSummary(
            created_material_types=created_material_types,
            created_materials=created_materials,
        )

    async def _ensure_material_types(self) -> tuple[dict[str, MaterialType], int]:
        result = await self.session.execute(select(MaterialType))
        material_types = {
            material_type.code: material_type for material_type in result.scalars().all()
        }

        created_material_types = 0
        for seed in MATERIAL_TYPE_SEEDS:
            if seed.code in material_types:
                continue

            material_type = MaterialType(
                code=seed.code,
                name=seed.name,
                status="active",
                note=seed.note,
            )
            self.session.add(material_type)
            material_types[seed.code] = material_type
            created_material_types += 1

        await self.session.flush()
        return material_types, created_material_types

    async def _ensure_materials(self, material_types: dict[str, MaterialType]) -> int:
        result = await self.session.execute(select(Material))
        existing_material_codes = {
            material.code for material in result.scalars().all()
        }

        created_materials = 0
        for seed in MATERIAL_SEEDS:
            if seed.code in existing_material_codes:
                continue

            material_type = material_types[seed.material_type_code]
            self.session.add(
                Material(
                    code=seed.code,
                    name=seed.name,
                    material_type_id=material_type.id,
                    status="active",
                    note=seed.note,
                ),
            )
            existing_material_codes.add(seed.code)
            created_materials += 1

        await self.session.flush()
        return created_materials
