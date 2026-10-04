"""Hàm dựng dữ liệu dùng chung cho các test tích hợp Telegram (PostgreSQL thật)."""

from __future__ import annotations

import itertools
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import TelegramAccount, User, UserStatus
from app.services.telegram_link_service import TelegramLinkService

# Database tích hợp dùng chung cả phiên test nên id Telegram và update_id phải khác nhau giữa
# các test, nếu không ràng buộc unique "đang giữ" của test này sẽ va chạm với test khác.
_telegram_ids = itertools.count(800_000_000)
_update_ids = itertools.count(900_000_000)


def next_telegram_id() -> int:
    return next(_telegram_ids)


def next_update_id() -> int:
    return next(_update_ids)


async def create_user(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    status: UserStatus = UserStatus.ACTIVE,
    full_name: str = "Người Dùng Thử",
) -> uuid.UUID:
    user = User(
        email=f"it_{uuid.uuid4().hex[:10]}@example.com",
        password_hash="x",
        full_name=full_name,
        status=status,
    )
    async with session_factory() as session:
        session.add(user)
        await session.commit()
    return user.id


def build_account(
    user_id: uuid.UUID,
    telegram_user_id: int,
    status: str = "active",
) -> TelegramAccount:
    return TelegramAccount(
        user_id=user_id,
        telegram_user_id=telegram_user_id,
        chat_id=telegram_user_id,
        status=status,
        linked_at=datetime.now(UTC),
    )


async def insert_rows(
    session_factory: async_sessionmaker[AsyncSession],
    *rows: object,
) -> None:
    async with session_factory() as session:
        session.add_all(rows)
        await session.commit()


async def issue_token(
    session_factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
) -> str:
    async with session_factory() as session:
        issued = await TelegramLinkService(session).issue_link_token(user_id)
        await session.commit()
    return issued.token
