from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import set_committed_value

from app.auth.hashing import hash_password
from app.auth.seed_data import ADMIN_ROLE_NAME, BASE_PERMISSION_CODES, USER_ROLE_NAME
from app.core.config import get_settings
from app.models import Permission, Role, User, UserStatus


class AuthSeedConfigurationError(Exception):
    """Raised when auth seed configuration is unsafe or incomplete."""


@dataclass(slots=True, frozen=True)
class AuthSeedSummary:
    created_permissions: int
    created_roles: int
    created_admin_user: bool
    updated_admin_password: bool


class AuthSeedService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = get_settings()

    async def seed(self) -> AuthSeedSummary:
        self._validate_seed_configuration()

        permissions, created_permissions = await self._ensure_permissions()
        created_roles = await self._ensure_roles(permissions)
        created_admin_user, updated_admin_password = await self._ensure_admin_user()
        await self.session.commit()

        return AuthSeedSummary(
            created_permissions=created_permissions,
            created_roles=created_roles,
            created_admin_user=created_admin_user,
            updated_admin_password=updated_admin_password,
        )

    def _validate_seed_configuration(self) -> None:
        password = self.settings.auth_seed_admin_password.strip()
        email = self.settings.auth_seed_admin_email.strip()

        if not email:
            raise AuthSeedConfigurationError("AUTH_SEED_ADMIN_EMAIL must not be empty.")
        if not password or password == "change-me-admin-password":  # nosec B105
            raise AuthSeedConfigurationError(
                "AUTH_SEED_ADMIN_PASSWORD must be set to a non-placeholder value before seeding.",
            )

    async def _ensure_permissions(self) -> tuple[list[Permission], int]:
        result = await self.session.execute(select(Permission))
        existing_permissions = {
            permission.code: permission for permission in result.scalars().all()
        }

        permissions: list[Permission] = []
        created_permissions = 0
        for code in BASE_PERMISSION_CODES:
            permission = existing_permissions.get(code)
            if permission is None:
                permission = Permission(code=code)
                self.session.add(permission)
                created_permissions += 1
            permissions.append(permission)

        await self.session.flush()
        return permissions, created_permissions

    async def _ensure_roles(self, permissions: list[Permission]) -> int:
        result = await self.session.execute(select(Role).options(selectinload(Role.permissions)))
        existing_roles = {role.name: role for role in result.scalars().all()}

        created_roles = 0

        admin_role = existing_roles.get(ADMIN_ROLE_NAME)
        if admin_role is None:
            admin_role = Role(
                name=ADMIN_ROLE_NAME,
                description="System administrator with full access.",
                is_system=True,
            )
            set_committed_value(admin_role, "permissions", [])
            self.session.add(admin_role)
            created_roles += 1

        user_role = existing_roles.get(USER_ROLE_NAME)
        if user_role is None:
            user_role = Role(
                name=USER_ROLE_NAME,
                description="Baseline application user.",
                is_system=True,
            )
            set_committed_value(user_role, "permissions", [])
            self.session.add(user_role)
            created_roles += 1

        await self.session.flush()

        admin_role.permissions = list(permissions)
        dashboard_permission = next(
            permission for permission in permissions if permission.code == "dashboard.read"
        )
        user_role.permissions = [dashboard_permission]
        return created_roles

    async def _ensure_admin_user(self) -> tuple[bool, bool]:
        result = await self.session.execute(
            select(User)
            .options(selectinload(User.roles))
            .where(User.email == self.settings.auth_seed_admin_email)
        )
        admin_user = result.scalar_one_or_none()

        admin_role_result = await self.session.execute(
            select(Role).where(Role.name == ADMIN_ROLE_NAME),
        )
        admin_role = admin_role_result.scalar_one()

        created_admin_user = False
        updated_admin_password = False

        if admin_user is None:
            admin_user = User(
                email=self.settings.auth_seed_admin_email,
                password_hash=hash_password(self.settings.auth_seed_admin_password),
                status=UserStatus.ACTIVE,
                full_name="System Administrator",
            )
            admin_user.roles = [admin_role]
            self.session.add(admin_user)
            created_admin_user = True
        else:
            admin_user.status = UserStatus.ACTIVE
            admin_user.full_name = "System Administrator"
            if not any(role.name == ADMIN_ROLE_NAME for role in admin_user.roles):
                admin_user.roles.append(admin_role)
            if self.settings.auth_seed_update_admin_password:
                admin_user.password_hash = hash_password(self.settings.auth_seed_admin_password)
                updated_admin_password = True

        await self.session.flush()
        return created_admin_user, updated_admin_password
