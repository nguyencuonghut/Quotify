"""Dựng sẵn hạn mức và lượt đã dùng cho các test của cổng hạn mức (kế hoạch 5.1, S10)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from bot_harness import Bot
from db_helpers import next_update_id
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.usage_gate import (
    BUSINESS_TIMEZONE,
    FixedQuotaLimits,
    QuotaLimits,
    TurnLimitGate,
    business_day_bounds,
)


def gate(turns: int = 20, files: int = 5) -> TurnLimitGate:
    return TurnLimitGate(FixedQuotaLimits(QuotaLimits(turns=turns, files=files)))


def tomorrow_text() -> str:
    """Ngày làm mới hạn mức (00:00 ngày kế tiếp, giờ Việt Nam) đúng như câu từ chối ghi."""
    _, resets_at = business_day_bounds(datetime.now(UTC))
    return resets_at.astimezone(BUSINESS_TIMEZONE).strftime("00:00 ngày %d/%m/%Y")


async def use_turns(
    bot: Bot,
    user_id: uuid.UUID,
    chat_id: int,
    count: int,
    *,
    received_at: Any = None,
) -> None:
    """Dựng `count` lượt đã được trả lời (đã lưu câu trả lời) của người dùng trong ngày."""
    async with bot.session_factory() as session:
        for _ in range(count):
            await session.execute(
                text(
                    "insert into bot_updates (update_id, chat_id, telegram_user_id, user_id, "
                    "status, attempts, received_at, started_at, finished_at, reply_saved_at) "
                    "values (:id, :chat, :chat, :user, 'replied', 1, "
                    "coalesce(:received, now()), coalesce(:received, now()), "
                    "coalesce(:received, now()), coalesce(:received, now()))"
                ),
                {
                    "id": next_update_id(),
                    "chat": chat_id,
                    "user": user_id,
                    "received": received_at,
                },
            )
        await session.commit()


@asynccontextmanager
async def scratch_session(bot: Bot, *, db_zone: str = "UTC") -> AsyncIterator[AsyncSession]:
    """Một phiên không bao giờ commit: dựng dòng mẫu (kể cả tin có tệp) rồi hoàn tác.

    Hộp thư hiện chỉ cho `kind='text'` (2C mới thêm tệp), nên bỏ ràng buộc ngay trong giao dịch:
    DDL của Postgres hoàn tác được, DB dùng chung không bị ảnh hưởng.
    """
    async with bot.session_factory() as session:
        await session.execute(text("ALTER TABLE bot_updates DROP CONSTRAINT ck_bot_updates_kind"))
        await session.execute(text("SELECT set_config('TimeZone', :zone, true)"), {"zone": db_zone})
        try:
            yield session
        finally:
            await session.rollback()


async def insert_turn(
    session: AsyncSession,
    user_id: uuid.UUID,
    received_at: datetime,
    *,
    kind: str = "text",
    saved_at: datetime | None = None,
) -> None:
    await session.execute(
        text(
            "insert into bot_updates (update_id, chat_id, telegram_user_id, user_id, kind, status, "
            "attempts, received_at, finished_at, reply_saved_at) "
            "values (:id, 1, 1, :user, :kind, 'replied', 1, :received, :received, :saved)"
        ),
        {
            "id": next_update_id(),
            "user": user_id,
            "kind": kind,
            "received": received_at,
            "saved": saved_at if saved_at is not None else received_at,
        },
    )
