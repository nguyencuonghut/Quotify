from __future__ import annotations

import asyncio

from app.db.session import get_sessionmaker
from app.quotify.seed_data import MATERIAL_SEEDS, MATERIAL_TYPE_SEEDS
from app.services.quotify_seed import QuotifySeedService


async def main() -> int:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        service = QuotifySeedService(session)
        summary = await service.seed()

    print("Quotify seed completed.")
    print(f"Created material types: {summary.created_material_types}")
    print(f"Created materials: {summary.created_materials}")
    print("Material types:")
    for material_type in MATERIAL_TYPE_SEEDS:
        print(f"- {material_type.code}: {material_type.name}")
    print("Materials:")
    for material in MATERIAL_SEEDS:
        print(f"- {material.code}: {material.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
