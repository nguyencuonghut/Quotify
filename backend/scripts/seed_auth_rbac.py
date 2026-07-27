from __future__ import annotations

import asyncio
import sys

from app.auth.seed_data import BASE_PERMISSION_CODES
from app.db.session import get_sessionmaker
from app.services.auth_seed import AuthSeedConfigurationError, AuthSeedService


async def main() -> int:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        service = AuthSeedService(session)
        try:
            summary = await service.seed()
        except AuthSeedConfigurationError as exc:
            print(f"Auth seed configuration error: {exc}", file=sys.stderr)
            await session.rollback()
            return 1

    print("Auth/RBAC seed completed.")
    print(f"Created permissions: {summary.created_permissions}")
    print(f"Created roles: {summary.created_roles}")
    print(f"Created admin user: {summary.created_admin_user}")
    print(f"Updated admin password: {summary.updated_admin_password}")
    print("Baseline permissions:")
    for code in BASE_PERMISSION_CODES:
        print(f"- {code}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
