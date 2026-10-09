"""Trạng thái liên kết Telegram của người dùng ở danh mục Người dùng, trên PostgreSQL thật."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from db_helpers import (
    build_account,
    create_user,
    ensure_role,
    insert_rows,
    next_telegram_id,
)
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


async def _list(
    session_factory: async_sessionmaker[AsyncSession],
    tag: str,
    **filters: str,
) -> set[str]:
    """Email của các người dùng khớp bộ lọc, giới hạn bằng `tag` riêng của từng test."""
    async with session_factory() as session:
        users, total = await UserAdminService(session).list_users(search=tag, limit=100, **filters)  # type: ignore[arg-type]
    assert total == len(users)
    return {user.email.split("@")[0].removeprefix(f"{tag}_") for user in users}


async def _make(
    session_factory: async_sessionmaker[AsyncSession],
    tag: str,
    name: str,
    *,
    roles: tuple[str, ...] = (),
    telegram: str | None = None,
) -> None:
    user = await create_user(session_factory, email=f"{tag}_{name}@example.com", role_names=roles)
    if telegram is not None:
        status = "active" if telegram == "linked" else telegram
        await insert_rows(session_factory, build_account(user, next_telegram_id(), status=status))


@pytest.mark.asyncio
async def test_the_list_filters_by_role(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tag = f"flt{uuid.uuid4().hex[:8]}"
    role_a, role_b = f"it_{tag}_a", f"it_{tag}_b"
    await ensure_role(session_factory, role_a)
    await ensure_role(session_factory, role_b)
    await _make(session_factory, tag, "a", roles=(role_a,))
    await _make(session_factory, tag, "both", roles=(role_a, role_b))
    await _make(session_factory, tag, "b", roles=(role_b,))
    await _make(session_factory, tag, "none")

    assert await _list(session_factory, tag, role_name=role_a) == {"a", "both"}
    assert await _list(session_factory, tag, role_name=role_b) == {"both", "b"}
    assert await _list(session_factory, tag) == {"a", "both", "b", "none"}


@pytest.mark.asyncio
async def test_the_list_filters_by_telegram_link(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tag = f"flt{uuid.uuid4().hex[:8]}"
    await _make(session_factory, tag, "linked", telegram="linked")
    await _make(session_factory, tag, "blocked", telegram="blocked")
    await _make(session_factory, tag, "revoked", telegram="revoked")
    await _make(session_factory, tag, "never")

    assert await _list(session_factory, tag, telegram="linked") == {"linked"}
    assert await _list(session_factory, tag, telegram="blocked") == {"blocked"}
    # Liên kết đã thu hồi giống chưa liên kết, đúng như cột hiển thị.
    assert await _list(session_factory, tag, telegram="none") == {"revoked", "never"}


@pytest.mark.asyncio
async def test_role_and_telegram_filters_combine_and_keep_the_total_in_step(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tag = f"flt{uuid.uuid4().hex[:8]}"
    role = f"it_{tag}_r"
    await ensure_role(session_factory, role)
    await _make(session_factory, tag, "hit", roles=(role,), telegram="linked")
    await _make(session_factory, tag, "other_role", telegram="linked")
    await _make(session_factory, tag, "no_link", roles=(role,))

    assert await _list(session_factory, tag, role_name=role, telegram="linked") == {"hit"}
