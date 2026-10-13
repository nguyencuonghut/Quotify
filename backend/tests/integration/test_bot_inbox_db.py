"""`BotInbox` trực tiếp trên PostgreSQL thật: claim, rào chắn, hết số lần thử (kế hoạch 5.1, 4.5).

Các bài đua đồng thời và chaos đầy đủ là việc của S2 (kịch bản ở
`docs/quotify/analysis-chatbot-5-1`); ở đây chỉ giữ các hành vi nền để thay đổi nào ở `BotInbox`
cũng bị bắt ngay.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from db_helpers import create_user, next_telegram_id, next_update_id
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.bot_inbox import BotInbox

NOW = datetime(2026, 10, 13, 3, 0, tzinfo=UTC)
LEASE = 240.0
MAX_ATTEMPTS = 3


async def _enqueue(
    sf: async_sessionmaker[AsyncSession],
    chat_id: int,
    user_id: uuid.UUID,
    texts: list[str],
) -> list[int]:
    ids: list[int] = []
    async with sf() as session:
        for text_ in texts:
            update_id = next_update_id()
            await BotInbox(session).enqueue(
                update_id=update_id,
                chat_id=chat_id,
                telegram_user_id=chat_id,
                user_id=user_id,
                text=text_,
            )
            ids.append(update_id)
        await session.commit()
    return ids


async def _claim(sf: async_sessionmaker[AsyncSession], chat_id: int, now: datetime) -> tuple:
    async with sf() as session:
        result = await BotInbox(session).claim(
            chat_id,
            now=now,
            lease_seconds=LEASE,
            max_attempts=MAX_ATTEMPTS,
        )
        await session.commit()
    return result.row, result.exhausted


async def test_only_one_row_of_a_chat_is_live_and_rows_come_out_in_order(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    chat = next_telegram_id()
    user_id = await create_user(session_factory)
    first, second = await _enqueue(session_factory, chat, user_id, ["một", "hai"])

    row, _ = await _claim(session_factory, chat, NOW)
    assert row is not None and (row.update_id, row.attempts, row.payload_text) == (first, 1, "một")

    blocked, _ = await _claim(session_factory, chat, NOW + timedelta(seconds=1))
    assert blocked is None  # dòng đầu còn lease: không ai nhảy sang dòng sau

    async with session_factory() as session:
        assert await BotInbox(session).complete(first, 1, now=NOW)
        await session.commit()
    row, _ = await _claim(session_factory, chat, NOW + timedelta(seconds=2))
    assert row is not None and row.update_id == second


async def test_a_stale_worker_cannot_write_after_its_lease_was_taken_over(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    chat = next_telegram_id()
    user_id = await create_user(session_factory)
    (update_id,) = await _enqueue(session_factory, chat, user_id, ["xin chào"])
    await _claim(session_factory, chat, NOW)
    taken_over, _ = await _claim(session_factory, chat, NOW + timedelta(seconds=LEASE + 1))
    assert taken_over is not None and taken_over.attempts == 2

    async with session_factory() as session:
        inbox = BotInbox(session)
        assert not await inbox.save_reply(update_id, 1, "muộn", now=NOW)  # worker cũ: bị chặn
        assert not await inbox.complete(update_id, 1, now=NOW)
        assert await inbox.save_reply(update_id, 2, "đúng", now=NOW)  # chủ sở hữu mới: ghi được
        assert await inbox.complete(update_id, 2, now=NOW)
        await session.commit()


async def test_a_row_that_used_every_attempt_fails_and_the_next_row_is_claimed(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    chat = next_telegram_id()
    user_id = await create_user(session_factory)
    stuck, after = await _enqueue(session_factory, chat, user_id, ["kẹt", "sau"])
    when = NOW
    for expected_attempts in range(1, MAX_ATTEMPTS + 1):
        row, _ = await _claim(session_factory, chat, when)
        assert row is not None and row.attempts == expected_attempts
        when += timedelta(seconds=LEASE + 1)  # lease hết hạn, worker không bao giờ xong

    row, exhausted = await _claim(session_factory, chat, when)

    assert exhausted == (stuck,)  # câu xin lỗi gửi sau commit: người gọi biết dòng nào
    assert row is not None and row.update_id == after


async def test_the_clock_given_to_the_inbox_must_have_a_timezone(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    chat = next_telegram_id()

    with pytest.raises(ValueError, match="múi giờ"):
        await _claim(session_factory, chat, datetime(2026, 10, 13, 3, 0))  # noqa: DTZ001
