from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.hashing import hash_password
from app.models import Role, User, UserStatus


class EmailAlreadyExistsError(Exception):
    """Raised when creating a user with an existing email."""


class RoleNotFoundError(Exception):
    """Raised when one or more requested roles do not exist."""


class UserNotFoundError(Exception):
    """Raised when the target user does not exist."""


class UserAdminService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_user(
        self,
        *,
        email: str,
        password: str,
        status: UserStatus,
        role_names: Sequence[str],
        full_name: str,
        avatar_url: str | None = None,
    ) -> User:
        existing_user = await self._get_user_by_email(email)
        if existing_user is not None:
            raise EmailAlreadyExistsError(f"User with email {email} already exists.")

        roles = await self._get_roles_by_names(role_names)
        user = User(
            email=email,
            password_hash=hash_password(password),
            status=status,
            full_name=full_name,
            avatar_url=avatar_url,
        )
        user.roles = roles
        self.session.add(user)
        await self.session.flush()
        return user

    async def get_user_by_id(self, user_id: UUID) -> User:
        user = await self._get_user_by_id(user_id)
        if user is None:
            raise UserNotFoundError(f"User {user_id} does not exist.")
        return user

    async def list_users(
        self,
        *,
        limit: int = 10,
        offset: int = 0,
        search: str | None = None,
        status: UserStatus | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[Sequence[User], int]:
        stmt = select(User).options(selectinload(User.roles).selectinload(Role.permissions))

        if search:
            stmt = stmt.where(User.email.ilike(f"%{search}%"))
        if status:
            stmt = stmt.where(User.status == status)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar_one()

        sort_attr = getattr(User, sort_by, None)
        if sort_attr is None:
            sort_attr = User.created_at

        if sort_order.lower() == "desc":
            stmt = stmt.order_by(sort_attr.desc())
        else:
            stmt = stmt.order_by(sort_attr.asc())

        stmt = stmt.offset(offset).limit(limit)

        result = await self.session.execute(stmt)
        users = result.scalars().all()
        return users, total

    async def update_user(
        self,
        *,
        user_id: UUID,
        email: str,
        status: UserStatus,
        password: str | None = None,
        role_names: Sequence[str],
        full_name: str,
        avatar_url: str | None = None,
    ) -> User:
        user = await self._get_user_by_id(user_id)
        if user is None:
            raise UserNotFoundError(f"User {user_id} does not exist.")

        if email != user.email:
            existing = await self._get_user_by_email(email)
            if existing is not None:
                raise EmailAlreadyExistsError(f"User with email {email} already exists.")
            user.email = email

        user.status = status
        user.full_name = full_name
        user.avatar_url = avatar_url
        if password is not None and password.strip():
            user.password_hash = hash_password(password)

        roles = await self._get_roles_by_names(role_names)
        user.roles = roles

        await self.session.flush()
        return user

    async def update_user_roles(
        self,
        *,
        user_id: UUID,
        role_names: Sequence[str],
    ) -> User:
        user = await self._get_user_by_id(user_id)
        if user is None:
            raise UserNotFoundError(f"User {user_id} does not exist.")

        roles = await self._get_roles_by_names(role_names)
        user.roles = roles
        await self.session.flush()
        return user

    async def delete_user(self, user_id: UUID) -> None:
        user = await self._get_user_by_id(user_id)
        if user is None:
            raise UserNotFoundError(f"User {user_id} does not exist.")

        await self.session.delete(user)
        await self.session.flush()

    async def _get_user_by_email(self, email: str) -> User | None:
        statement = (
            select(User)
            .options(selectinload(User.roles).selectinload(Role.permissions))
            .where(User.email == email)
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def _get_user_by_id(self, user_id: UUID) -> User | None:
        statement = (
            select(User)
            .options(selectinload(User.roles).selectinload(Role.permissions))
            .where(User.id == user_id)
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def _get_roles_by_names(self, role_names: Sequence[str]) -> list[Role]:
        normalized_names = sorted(set(role_names))
        if not normalized_names:
            return []

        result = await self.session.execute(
            select(Role)
            .options(selectinload(Role.permissions))
            .where(Role.name.in_(normalized_names)),
        )
        roles = list(result.scalars().all())
        resolved_names = {role.name for role in roles}
        missing_names = [name for name in normalized_names if name not in resolved_names]
        if missing_names:
            raise RoleNotFoundError(
                f"Roles do not exist: {', '.join(missing_names)}.",
            )
        return sorted(roles, key=lambda role: role.name)
