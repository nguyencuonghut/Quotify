"""Hành vi chống trùng update Telegram trên PostgreSQL thật (fake session không kiểm được)."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from telegram_fakes import Outbox, make_client, make_update

from app.services.telegram_update_runner import TelegramUpdateRunner
from app.services.telegram_update_service import TelegramUpdateService, parse_update

pytestmark = pytest.mark.integration


async def _handle_and_commit(
    session_factory: async_sessionmaker[AsyncSession],
    payload: dict[str, object],
) -> int:
    update = parse_update(payload)
    assert update is not None
    async with session_factory() as session:
        messages = await TelegramUpdateService(session).handle(update)
        await session.commit()
    return len(messages)


@pytest.mark.asyncio
async def test_concurrent_deliveries_of_the_same_update_are_handled_exactly_once(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    payload = make_update(4242, "/help")

    deliveries = [_handle_and_commit(session_factory, payload) for _ in range(5)]
    results = await asyncio.gather(*deliveries)

    assert sorted(results) == [0, 0, 0, 0, 1]
    async with session_factory() as session:
        count = (
            await session.execute(
                text("select count(*) from telegram_processed_updates where update_id = 4242")
            )
        ).scalar_one()
    assert count == 1


@pytest.mark.asyncio
async def test_rolled_back_update_is_not_recorded_and_can_be_retried(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    payload = make_update(4243, "/help")
    update = parse_update(payload)
    assert update is not None

    async with session_factory() as session:
        await TelegramUpdateService(session).handle(update)
        await session.rollback()

    assert await _handle_and_commit(session_factory, payload) == 1


@pytest.mark.asyncio
async def test_runner_answers_once_and_cleans_old_rows_on_real_postgres(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    outbox = Outbox()
    client, http_client = make_client(outbox)
    runner = TelegramUpdateRunner(session_factory=session_factory, client=client)
    async with session_factory() as session:
        await session.execute(
            text(
                "insert into telegram_processed_updates (update_id, received_at) "
                "values (1, now() - interval '10 days'), (2, now())"
            )
        )
        await session.commit()

    await runner.process(make_update(4244, "/help"))
    await runner.process(make_update(4244, "/help"))
    await http_client.aclose()

    assert len(outbox.sent_messages()) == 1
    async with session_factory() as session:
        remaining = (
            (await session.execute(text("select update_id from telegram_processed_updates")))
            .scalars()
            .all()
        )
    assert 1 not in remaining  # quá 3 ngày: đã bị dọn
    assert {2, 4244} <= set(remaining)


@pytest.mark.asyncio
async def test_migration_creates_the_table_with_the_expected_primary_key(
    db_engine: object,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        pk_columns = (
            (
                await session.execute(
                    text(
                        "select a.attname from pg_index i "
                        "join pg_attribute a on a.attrelid = i.indrelid "
                        "and a.attnum = any(i.indkey) "
                        "where i.indrelid = 'telegram_processed_updates'::regclass "
                        "and i.indisprimary"
                    )
                )
            )
            .scalars()
            .all()
        )
    assert pk_columns == ["update_id"]
