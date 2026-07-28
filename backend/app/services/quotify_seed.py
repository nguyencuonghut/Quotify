from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Material, MaterialType, Supplier, SupplierMaterial
from app.quotify.seed_data import MATERIAL_SEEDS, MATERIAL_TYPE_SEEDS, SUPPLIER_SEEDS


@dataclass(slots=True, frozen=True)
class QuotifySeedSummary:
    created_material_types: int
    created_materials: int
    created_suppliers: int


class QuotifySeedService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def seed(self) -> QuotifySeedSummary:
        material_types, created_material_types = await self._ensure_material_types()
        created_materials = await self._ensure_materials(material_types)
        created_suppliers = await self._ensure_suppliers()
        await self.session.commit()

        return QuotifySeedSummary(
            created_material_types=created_material_types,
            created_materials=created_materials,
            created_suppliers=created_suppliers,
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

    async def _ensure_suppliers(self) -> int:
        result = await self.session.execute(select(Supplier))
        suppliers_by_code = {s.code: s for s in result.scalars().all()}

        mat_result = await self.session.execute(select(Material))
        materials_by_code = {m.code: m for m in mat_result.scalars().all()}

        sm_result = await self.session.execute(select(SupplierMaterial))
        existing_pairs = {(sm.supplier_id, sm.material_id) for sm in sm_result.scalars().all()}

        created_suppliers = 0
        for seed in SUPPLIER_SEEDS:
            supplier = suppliers_by_code.get(seed.code)
            if not supplier:
                supplier = Supplier(
                    code=seed.code,
                    name=seed.name,
                    supplier_type=seed.supplier_type,
                    status=seed.status,
                    note=seed.note,
                )
                self.session.add(supplier)
                await self.session.flush()
                suppliers_by_code[seed.code] = supplier
                created_suppliers += 1

            for mat_code in seed.material_codes:
                material = materials_by_code.get(mat_code)
                if material:
                    pair = (supplier.id, material.id)
                    if pair not in existing_pairs:
                        self.session.add(
                            SupplierMaterial(
                                supplier_id=supplier.id,
                                material_id=material.id,
                            )
                        )
                        existing_pairs.add(pair)

        await self.session.flush()
        return created_suppliers
