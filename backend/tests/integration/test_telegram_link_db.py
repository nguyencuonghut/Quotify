"""Ràng buộc và cấp mã liên kết Telegram trên PostgreSQL thật (fake session không kiểm được)."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from db_helpers import build_account, create_user, insert_rows
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.telegram_link_service import TelegramLinkService, hash_link_token

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_a_telegram_account_cannot_be_held_by_two_users(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    first, second = await create_user(session_factory), await create_user(session_factory)
    tg = 700_000_001
    await insert_rows(session_factory, build_account(first, tg))

    with pytest.raises(IntegrityError) as exc_info:
        await insert_rows(session_factory, build_account(second, tg))

    assert "uq_telegram_accounts_holding_telegram_user" in str(exc_info.value)


@pytest.mark.asyncio
async def test_a_user_cannot_hold_two_telegram_accounts(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user = await create_user(session_factory)
    await insert_rows(session_factory, build_account(user, 700_000_011))

    with pytest.raises(IntegrityError) as exc_info:
        await insert_rows(session_factory, build_account(user, 700_000_012))

    assert "uq_telegram_accounts_holding_user" in str(exc_info.value)


@pytest.mark.asyncio
async def test_a_blocked_account_still_holds_the_link(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    first, second = await create_user(session_factory), await create_user(session_factory)
    tg = 700_000_021
    await insert_rows(session_factory, build_account(first, tg, status="blocked"))

    with pytest.raises(IntegrityError):
        await insert_rows(session_factory, build_account(second, tg))
    with pytest.raises(IntegrityError):
        await insert_rows(session_factory, build_account(first, 700_000_022))


@pytest.mark.asyncio
async def test_revoked_accounts_release_both_the_user_and_the_telegrambuild_account(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    first, second = await create_user(session_factory), await create_user(session_factory)
    tg = 700_000_031
    await insert_rows(session_factory, build_account(first, tg, status="revoked"))

    # Telegram đó giờ gắn được cho người khác, và người cũ cũng liên kết được Telegram khác.
    await insert_rows(session_factory, build_account(second, tg))
    await insert_rows(session_factory, build_account(first, 700_000_032))
    # Nhiều bản ghi đã thu hồi cho cùng một người vẫn được phép (lịch sử).
    await insert_rows(session_factory, build_account(first, 700_000_033, status="revoked"))

    async with session_factory() as session:
        count = (
            await session.execute(
                text("select count(*) from telegram_accounts where user_id = :u"),
                {"u": first},
            )
        ).scalar_one()
    assert count == 3


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "revoked_reason"),
    [("deleted", None), ("revoked", "bad_reason")],
)
async def test_check_constraints_reject_unknown_status_and_reason(
    session_factory: async_sessionmaker[AsyncSession],
    status: str,
    revoked_reason: str | None,
) -> None:
    user = await create_user(session_factory)
    account = build_account(user, 700_000_041 + len(status), status=status)
    account.revoked_reason = revoked_reason

    with pytest.raises(IntegrityError):
        await insert_rows(session_factory, account)


@pytest.mark.asyncio
async def test_deleting_a_user_cascades_to_accounts_and_tokens(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user = await create_user(session_factory)
    await insert_rows(session_factory, build_account(user, 700_000_051))
    async with session_factory() as session:
        await TelegramLinkService(session).issue_link_token(user)
        await session.commit()

    async with session_factory() as session:
        await session.execute(text("delete from users where id = :u"), {"u": user})
        await session.commit()
        accounts = (
            await session.execute(
                text("select count(*) from telegram_accounts where user_id = :u"), {"u": user}
            )
        ).scalar_one()
        tokens = (
            await session.execute(
                text("select count(*) from telegram_link_tokens where user_id = :u"), {"u": user}
            )
        ).scalar_one()
    assert (accounts, tokens) == (0, 0)


@pytest.mark.asyncio
async def test_issued_token_is_stored_only_as_a_hash_and_status_reports_it(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user = await create_user(session_factory)

    async with session_factory() as session:
        issued = await TelegramLinkService(session).issue_link_token(user)
        await session.commit()

    async with session_factory() as session:
        stored = (
            await session.execute(
                text("select token_hash, used_at from telegram_link_tokens where user_id = :u"),
                {"u": user},
            )
        ).one()
        link_status = await TelegramLinkService(session).get_status(user)

    assert len(issued.token) == 43
    assert stored.token_hash == hash_link_token(issued.token)
    assert issued.token not in stored.token_hash
    assert stored.used_at is None
    assert link_status.account is None
    assert link_status.pending_expires_at is not None
    assert 590 <= (link_status.pending_expires_in_seconds or 0) <= 600


@pytest.mark.asyncio
async def test_issuing_again_invalidates_the_previous_token(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user = await create_user(session_factory)
    async with session_factory() as session:
        first = await TelegramLinkService(session).issue_link_token(user)
        await session.commit()
    async with session_factory() as session:
        second = await TelegramLinkService(session).issue_link_token(user)
        await session.commit()

    async with session_factory() as session:
        valid = (
            (
                await session.execute(
                    text(
                        "select id from telegram_link_tokens "
                        "where user_id = :u and used_at is null and expires_at > now()"
                    ),
                    {"u": user},
                )
            )
            .scalars()
            .all()
        )

    assert valid == [second.token_id]
    assert first.token_id != second.token_id


@pytest.mark.asyncio
async def test_cancelling_is_idempotent_and_clears_the_pending_link(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user = await create_user(session_factory)
    async with session_factory() as session:
        await TelegramLinkService(session).issue_link_token(user)
        await session.commit()

    async with session_factory() as session:
        service = TelegramLinkService(session)
        cancelled_first = await service.cancel_pending(user)
        cancelled_again = await service.cancel_pending(user)
        await session.commit()
        link_status = await service.get_status(user)

    assert (cancelled_first, cancelled_again) == (1, 0)
    assert link_status.pending_expires_at is None
    assert link_status.pending_expires_in_seconds is None


@pytest.mark.asyncio
async def test_concurrent_issuance_for_one_user_leaves_exactly_one_valid_token(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user = await create_user(session_factory)

    async def issue() -> uuid.UUID:
        async with session_factory() as session:
            issued = await TelegramLinkService(session).issue_link_token(user)
            await session.commit()
            return issued.token_id

    issued_ids = await asyncio.gather(*(issue() for _ in range(6)))

    async with session_factory() as session:
        rows = (
            await session.execute(
                text(
                    "select id, (expires_at > now() and used_at is null) as valid "
                    "from telegram_link_tokens where user_id = :u"
                ),
                {"u": user},
            )
        ).all()
    assert len(rows) == 6
    assert {row.id for row in rows} == set(issued_ids)
    assert sum(1 for row in rows if row.valid) == 1


@pytest.mark.asyncio
async def test_tokens_of_other_users_are_untouched_by_cancel_and_reissue(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    mine, theirs = await create_user(session_factory), await create_user(session_factory)
    async with session_factory() as session:
        other = await TelegramLinkService(session).issue_link_token(theirs)
        await session.commit()

    async with session_factory() as session:
        service = TelegramLinkService(session)
        await service.issue_link_token(mine)
        await service.cancel_pending(mine)
        await session.commit()

    async with session_factory() as session:
        row = (
            await session.execute(
                text("select expires_at > now() as valid from telegram_link_tokens where id = :i"),
                {"i": other.token_id},
            )
        ).one()
    assert row.valid is True
