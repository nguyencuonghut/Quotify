from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Permission, Role


class RoleAlreadyExistsError(Exception):
    """Raised when creating or renaming a role to an existing name."""


class RoleNotFoundError(Exception):
    """Raised when the target role does not exist."""


class SystemRoleModificationError(Exception):
    """Raised when trying to modify or delete a system role."""


class PermissionNotFoundError(Exception):
    """Raised when requested permission codes do not exist."""


class RoleAdminService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_role(
        self,
        *,
        name: str,
        description: str | None = None,
        permission_codes: Sequence[str] = (),
    ) -> Role:
        existing_role = await self._get_role_by_name(name)
        if existing_role is not None:
            raise RoleAlreadyExistsError(f"Role with name '{name}' already exists.")

        permissions = await self._get_permissions_by_codes(permission_codes)

        role = Role(
            name=name,
            description=description,
            is_system=False,
        )
        role.permissions = permissions
        self.session.add(role)
        await self.session.flush()
        return role

    async def get_role_by_id(self, role_id: UUID) -> Role:
        role = await self._get_role_by_id(role_id)
        if role is None:
            raise RoleNotFoundError(f"Role {role_id} does not exist.")
        return role

    async def list_roles(
        self,
        *,
        limit: int = 10,
        offset: int = 0,
        search: str | None = None,
        sort_by: str = "name",
        sort_order: str = "asc",
    ) -> tuple[Sequence[Role], int]:
        stmt = select(Role).options(selectinload(Role.permissions))

        if search:
            stmt = stmt.where(Role.name.ilike(f"%{search}%"))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar_one()

        sort_attr = getattr(Role, sort_by, None)
        if sort_attr is None:
            sort_attr = Role.name

        if sort_order.lower() == "desc":
            stmt = stmt.order_by(sort_attr.desc())
        else:
            stmt = stmt.order_by(sort_attr.asc())

        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        roles = result.scalars().all()
        return roles, total

    async def update_role(
        self,
        *,
        role_id: UUID,
        name: str,
        description: str | None = None,
        permission_codes: Sequence[str] = (),
    ) -> Role:
        role = await self._get_role_by_id(role_id)
        if role is None:
            raise RoleNotFoundError(f"Role {role_id} does not exist.")

        if role.is_system:
            if role.name != name:
                raise SystemRoleModificationError(f"System role '{role.name}' cannot be renamed.")

        if role.name != name:
            existing_role = await self._get_role_by_name(name)
            if existing_role is not None:
                raise RoleAlreadyExistsError(f"Role with name '{name}' already exists.")
            role.name = name

        role.description = description

        permissions = await self._get_permissions_by_codes(permission_codes)
        role.permissions = permissions

        await self.session.flush()
        return role

    async def delete_role(self, role_id: UUID) -> None:
        role = await self._get_role_by_id(role_id)
        if role is None:
            raise RoleNotFoundError(f"Role {role_id} does not exist.")

        if role.is_system:
            raise SystemRoleModificationError(f"System role '{role.name}' cannot be deleted.")

        await self.session.delete(role)
        await self.session.flush()

    async def _get_role_by_id(self, role_id: UUID) -> Role | None:
        stmt = select(Role).where(Role.id == role_id).options(selectinload(Role.permissions))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_role_by_name(self, name: str) -> Role | None:
        stmt = select(Role).where(Role.name == name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_permissions_by_codes(self, codes: Sequence[str]) -> list[Permission]:
        if not codes:
            return []
        stmt = select(Permission).where(Permission.code.in_(codes))
        result = await self.session.execute(stmt)
        permissions = list(result.scalars().all())

        found_codes = {p.code for p in permissions}
        missing_codes = set(codes) - found_codes
        if missing_codes:
            raise PermissionNotFoundError(
                f"One or more permissions do not exist: {', '.join(sorted(missing_codes))}."
            )
        return permissions
