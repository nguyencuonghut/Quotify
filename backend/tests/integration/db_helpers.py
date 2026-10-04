"""Hàm dựng dữ liệu dùng chung cho các test tích hợp Telegram (PostgreSQL thật)."""

from __future__ import annotations

import itertools
import uuid
from datetime import UTC, date, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
    Material,
    MaterialType,
    Quote,
    QuoteVersion,
    Supplier,
    TelegramAccount,
    User,
    UserStatus,
)
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


async def create_material(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    name: str = "Vật tư thử",
) -> uuid.UUID:
    suffix = uuid.uuid4().hex[:8].upper()
    async with session_factory() as session:
        material_type = MaterialType(code=f"IT{suffix}", name="Loại vật tư thử")
        session.add(material_type)
        await session.flush()
        material = Material(code=f"IT{suffix}", name=name, material_type_id=material_type.id)
        session.add(material)
        await session.commit()
    return material.id


async def create_confirmed_quote_version(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    created_by_id: uuid.UUID | None = None,
    received_date: date | None = None,
    confirmed_at: datetime | None = None,
) -> uuid.UUID:
    """Dựng phiếu có một version đã chốt (chưa có dòng giá) và trả về id của version."""
    suffix = uuid.uuid4().hex[:8].upper()
    moment = confirmed_at or datetime.now(UTC)
    async with session_factory() as session:
        supplier = Supplier(code=f"IT{suffix}", name="Nhà cung cấp thử", supplier_type="domestic")
        session.add(supplier)
        await session.flush()
        quote = Quote(supplier_id=supplier.id, created_by_id=created_by_id)
        session.add(quote)
        await session.flush()
        version = QuoteVersion(
            quote_id=quote.id,
            version_number=1,
            received_date=received_date or moment.date(),
            status="confirmed",
            created_by_id=created_by_id,
            confirmed_at=moment,
            confirmed_by_id=created_by_id,
        )
        session.add(version)
        await session.commit()
    return version.id

