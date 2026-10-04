from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import has_permission, has_role
from app.models import User, UserAlertPreference

LEVELS = ("light", "medium", "large")


@dataclass(frozen=True, slots=True)
class AlertPreferences:
    is_enabled: bool
    min_level: str | None
    effective_min_level: str
    admin_receive_all: bool


def default_min_level(user: User) -> str:
    """Trưởng phòng và người nhận mọi vật tư mặc định từ mức Trung bình (D9)."""
    if has_role(user, "manager") or has_permission(user, "price_alerts.receive_all"):
        return "medium"
    return "light"


def build_preferences(user: User, row: UserAlertPreference | None) -> AlertPreferences:
    if row is None:
        return AlertPreferences(
            is_enabled=True,
            min_level=None,
            effective_min_level=default_min_level(user),
            admin_receive_all=False,
        )
    return AlertPreferences(
        is_enabled=row.is_enabled,
        min_level=row.min_level,
        effective_min_level=row.min_level or default_min_level(user),
        admin_receive_all=row.admin_receive_all,
    )


class UserAlertPreferenceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user: User) -> AlertPreferences:
        row = (
            await self.session.execute(
                select(UserAlertPreference).where(UserAlertPreference.user_id == user.id),
            )
        ).scalar_one_or_none()
        return build_preferences(user, row)

    async def upsert(
        self,
        user: User,
        *,
        is_enabled: bool,
        min_level: str | None,
        admin_receive_all: bool,
    ) -> AlertPreferences:
        if min_level is not None and min_level not in LEVELS:
            raise ValueError("Mức tối thiểu phải là light, medium hoặc large.")
        if admin_receive_all and not has_role(user, "admin"):
            raise PermissionError("Chỉ quản trị viên được bật nhận mọi thông báo.")
        statement = pg_insert(UserAlertPreference).values(
            user_id=user.id,
            is_enabled=is_enabled,
            min_level=min_level,
            admin_receive_all=admin_receive_all,
        )
        statement = statement.on_conflict_do_update(
            index_elements=[UserAlertPreference.user_id],
            set_={
                "is_enabled": statement.excluded.is_enabled,
                "min_level": statement.excluded.min_level,
                "admin_receive_all": statement.excluded.admin_receive_all,
                "updated_at": func.now(),
            },
        )
        await self.session.execute(statement)
        await self.session.flush()
        return await self.get(user)
