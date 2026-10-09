"""Trạng thái liên kết Telegram của người dùng ở danh mục Người dùng, trên PostgreSQL thật."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from db_helpers import build_account, create_user, insert_rows
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.user_admin import UserAdminService

pytestmark = pytest.mark.integration


async def _statuses(
    session_factory: async_sessionmaker[AsyncSession],
    user_ids: list[uuid.UUID],
) -> dict[uuid.UUID, str]:
    async with session_factory() as session:
        return await UserAdminService(session).get_telegram_link_statuses(user_ids)


@pytest.mark.asyncio
async def test_only_users_holding_a_link_are_reported(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    linked, blocked, revoked, never = [await create_user(session_factory) for _ in range(4)]
    revoked_account = build_account(revoked, 710_000_003, status="revoked")
    revoked_account.revoked_at = datetime.now(UTC)
    revoked_account.revoked_reason = "user_unlink"
    await insert_rows(
        session_factory,
        build_account(linked, 710_000_001),
        build_account(blocked, 710_000_002, status="blocked"),
        revoked_account,
    )

    result = await _statuses(session_factory, [linked, blocked, revoked, never])

    assert result == {linked: "active", blocked: "blocked"}


@pytest.mark.asyncio
async def test_a_relinked_user_reports_the_current_link_not_the_revoked_one(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user = await create_user(session_factory)
    old = build_account(user, 710_000_011, status="revoked")
    old.revoked_at = datetime.now(UTC)
    old.revoked_reason = "replaced"
    await insert_rows(session_factory, old, build_account(user, 710_000_012))

    assert await _statuses(session_factory, [user]) == {user: "active"}


@pytest.mark.asyncio
async def test_no_user_ids_returns_empty_without_a_query(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    assert await _statuses(session_factory, []) == {}
