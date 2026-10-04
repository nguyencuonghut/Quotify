"""Hàm dựng dữ liệu dùng chung cho các test tích hợp Telegram (PostgreSQL thật)."""

from __future__ import annotations

import itertools
import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
    Material,
    MaterialType,
    Permission,
    Quote,
    QuoteLine,
    QuoteVersion,
    Role,
    Supplier,
    TelegramAccount,
    User,
    UserStatus,
    role_permissions,
    user_roles,
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
    email: str | None = None,
    role_names: Sequence[str] = (),
) -> uuid.UUID:
    user = User(
        email=email or f"it_{uuid.uuid4().hex[:10]}@example.com",
        password_hash="x",
        full_name=full_name,
        status=status,
    )
    async with session_factory() as session:
        session.add(user)
        await session.flush()
        for name in role_names:
            role_id = (await session.execute(select(Role.id).where(Role.name == name))).scalar_one()
            await session.execute(user_roles.insert().values(user_id=user.id, role_id=role_id))
        await session.commit()
    return user.id


async def ensure_role(
    session_factory: async_sessionmaker[AsyncSession],
    name: str,
    permission_codes: Sequence[str] = (),
) -> uuid.UUID:
    """Tạo role nếu chưa có (DB tích hợp dùng chung cả phiên) và gán đúng các quyền đã có."""
    async with session_factory() as session:
        role = (await session.execute(select(Role).where(Role.name == name))).scalar_one_or_none()
        if role is None:
            role = Role(name=name, is_system=False)
            session.add(role)
            await session.flush()
        for code in permission_codes:
            permission_id = (
                await session.execute(select(Permission.id).where(Permission.code == code))
            ).scalar_one()
            await session.execute(
                pg_insert(role_permissions)
                .values(role_id=role.id, permission_id=permission_id)
                .on_conflict_do_nothing(),
            )
        await session.commit()
    return role.id


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


async def create_priced_line(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    material_id: uuid.UUID,
    price: int | str | Decimal,
    received_date: date,
    delivery_month: date = date(2026, 12, 1),
    status: str = "confirmed",
    cancelled: bool = False,
    created_by_id: uuid.UUID | None = None,
    confirmed_at: datetime | None = None,
    confirmed_at_null: bool = False,
    price_converted: int | str | Decimal | None = None,
    currency: str = "VND",
    unit: str = "KG",
    price_original: int | str | Decimal | None = None,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Dựng phiếu + version + MỘT dòng giá; trả về `(version_id, line_id)`."""
    suffix = uuid.uuid4().hex[:8].upper()
    moment = confirmed_at or datetime.now(UTC)
    async with session_factory() as session:
        supplier = Supplier(code=f"IT{suffix}", name="Nhà cung cấp thử", supplier_type="domestic")
        session.add(supplier)
        await session.flush()
        quote = Quote(
            supplier_id=supplier.id,
            created_by_id=created_by_id,
            cancelled_at=moment if cancelled else None,
        )
        session.add(quote)
        await session.flush()
        version = QuoteVersion(
            quote_id=quote.id,
            version_number=1,
            received_date=received_date,
            status=status,
            created_by_id=created_by_id,
            confirmed_at=(
                moment if status in ("confirmed", "superseded") and not confirmed_at_null else None
            ),
        )
        session.add(version)
        await session.flush()
        line = QuoteLine(
            quote_version_id=version.id,
            material_id=material_id,
            price_original=Decimal(price if price_original is None else price_original),
            currency=currency,
            unit=unit,
            delivery_month=delivery_month,
            price_converted_vnd_per_kg=Decimal(
                price if price_converted is None else price_converted
            ),
        )
        session.add(line)
        await session.commit()
    return version.id, line.id


async def create_quote_shell(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    created_by_id: uuid.UUID | None = None,
    cancelled: bool = False,
) -> uuid.UUID:
    suffix = uuid.uuid4().hex[:8].upper()
    async with session_factory() as session:
        supplier = Supplier(code=f"IT{suffix}", name="Nhà cung cấp thử", supplier_type="domestic")
        session.add(supplier)
        await session.flush()
        quote = Quote(
            supplier_id=supplier.id,
            created_by_id=created_by_id,
            cancelled_at=datetime.now(UTC) if cancelled else None,
        )
        session.add(quote)
        await session.commit()
    return quote.id


async def create_version_with_lines(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    quote_id: uuid.UUID,
    version_number: int,
    received_date: date,
    lines: Sequence[tuple[uuid.UUID, int | str, date]],
    status: str = "confirmed",
    confirmed_at: datetime | None = None,
    supersedes_version_id: uuid.UUID | None = None,
) -> tuple[uuid.UUID, list[uuid.UUID]]:
    """Dựng version nhiều dòng `(material_id, giá, delivery_month)`, có thể thay thế version cũ."""
    moment = confirmed_at or datetime.now(UTC)
    async with session_factory() as session:
        version = QuoteVersion(
            quote_id=quote_id,
            version_number=version_number,
            received_date=received_date,
            status=status,
            confirmed_at=moment if status in ("confirmed", "superseded") else None,
        )
        session.add(version)
        await session.flush()
        line_ids: list[uuid.UUID] = []
        for order, (material_id, price, delivery_month) in enumerate(lines):
            line = QuoteLine(
                quote_version_id=version.id,
                material_id=material_id,
                price_original=Decimal(price),
                currency="VND",
                unit="KG",
                delivery_month=delivery_month,
                line_order=order,
                price_converted_vnd_per_kg=Decimal(price),
            )
            session.add(line)
            await session.flush()
            line_ids.append(line.id)
        if supersedes_version_id is not None:
            old = await session.get(QuoteVersion, supersedes_version_id)
            assert old is not None
            old.status = "superseded"
            old.superseded_at = moment
            old.superseded_by_version_id = version.id
        await session.commit()
    return version.id, line_ids
