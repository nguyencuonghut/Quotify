from __future__ import annotations

import asyncio

from app.db.session import get_sessionmaker
from app.quotify.seed_data import MATERIAL_TYPE_SEEDS
from app.services.quotify_seed import QuotifySeedService


async def main() -> int:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        service = QuotifySeedService(session)
        summary = await service.seed_material_types()

    print("Quotify material type seed completed.")
    print(f"Created material types: {summary.created_material_types}")
    print("Material types:")
    for material_type in MATERIAL_TYPE_SEEDS:
        print(f"- {material_type.code}: {material_type.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
