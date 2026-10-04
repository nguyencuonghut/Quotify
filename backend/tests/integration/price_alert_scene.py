"""Dựng người dùng, liên kết Telegram và phiếu cho các test người nhận và tin (Slice 6, 7)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from db_helpers import (
    build_account,
    create_material,
    create_priced_line,
    create_user,
    insert_rows,
    next_telegram_id,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import UserAlertPreference, UserStatus
from app.services.price_alert_recipients import RecipientDecision, resolve_recipients

NOW = datetime(2046, 6, 15, 3, 0, tzinfo=UTC)
TODAY = date(2046, 6, 15)


class Scene:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.sf = session_factory
        self.mine: set[uuid.UUID] = set()
        self.material: uuid.UUID

    async def setup(self) -> Scene:
        self.material = await create_material(self.sf)
        return self

    async def person(
        self,
        *roles: str,
        linked: bool = True,
        status: UserStatus = UserStatus.ACTIVE,
        email: str | None = None,
        account_status: str = "active",
    ) -> uuid.UUID:
        user_id = await create_user(self.sf, status=status, email=email, role_names=roles)
        if linked:
            await insert_rows(self.sf, build_account(user_id, next_telegram_id(), account_status))
        self.mine.add(user_id)
        return user_id

    async def entered(
        self,
        user_id: uuid.UUID,
        *,
        received: date = TODAY,
        status: str = "confirmed",
        cancelled: bool = False,
        material: uuid.UUID | None = None,
    ) -> tuple[uuid.UUID, uuid.UUID]:
        return await create_priced_line(
            self.sf,
            material_id=material or self.material,
            price=100,
            received_date=received,
            status=status,
            cancelled=cancelled,
            created_by_id=user_id,
        )

    async def prefer(self, user_id: uuid.UUID, **values: object) -> None:
        await insert_rows(self.sf, UserAlertPreference(user_id=user_id, **values))

    async def resolve(self, level: str | None = "medium", **kwargs: object) -> RecipientDecision:
        async with self.sf() as session:
            decision = await resolve_recipients(
                session,
                material_id=kwargs.pop("material_id", self.material),  # type: ignore[arg-type]
                event_level=level,
                kind=kwargs.pop("kind", "change"),  # type: ignore[arg-type]
                now=NOW,
                seed_user_id=kwargs.pop("seed_user_id", None),  # type: ignore[arg-type]
                **kwargs,  # type: ignore[arg-type]
            )
        return RecipientDecision(
            [r for r in decision.recipients if r.user_id in self.mine],
            [s for s in decision.skipped if s.user_id in self.mine],
        )

    @staticmethod
    def ids(decision: RecipientDecision) -> set[uuid.UUID]:
        return {r.user_id for r in decision.recipients}
