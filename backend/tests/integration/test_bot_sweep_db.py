"""Cron quét và dọn của worker chatbot (kế hoạch 5.1, S3).

Hàng đợi chỉ là cái chuông; trạng thái nằm ở Postgres. Cron quét đánh chuông lại cho mọi dòng bị bỏ
sót (Redis hỏng lúc đánh chuông, worker chết, hết lease) và KHÔNG tự đổi trạng thái dòng nào.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from bot_harness import Bot, linked_user
from db_helpers import next_update_id
from sqlalchemy import text

from app.bot_worker import BotWorkerConfig


class _RaisingDispatcher:
    async def notify(self, chat_id: int, update_id: int) -> None:
        raise ConnectionError("redis down")

    async def aclose(self) -> None:
        return None


EVERY_ROW = BotWorkerConfig(sweep_stale_seconds=0)  # cho dòng vừa vào cũng đủ "cũ"


@pytest.fixture(autouse=True)
async def _no_open_rows_left_by_other_tests(session_factory) -> None:  # noqa: ANN001
    """Cron quét nhìn mọi chat của DB tạm dùng chung cả phiên (giới hạn mỗi lần quét), nên dọn dòng
    còn mở do test khác để lại: kết quả quét của test này chỉ phụ thuộc vào dòng của chính nó."""
    async with session_factory() as session:
        await session.execute(
            text("delete from bot_updates where status in ('queued', 'processing')")
        )
        await session.commit()


def _past(seconds: float = 1) -> datetime:
    return datetime.now(UTC) - timedelta(seconds=seconds)


def _future(seconds: float = 60) -> datetime:
    return datetime.now(UTC) + timedelta(seconds=seconds)


async def test_the_sweep_rings_again_for_a_row_whose_bell_was_lost_and_the_message_is_answered(
    chatbot_bot_factory,  # noqa: ANN001
) -> None:
    from app.services.bot_policy import ChatbotPolicy

    bot: Bot = chatbot_bot_factory(ChatbotPolicy(enabled=True), dispatcher=_RaisingDispatcher())
    _, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)  # Redis hỏng: chuông không rung, webhook vẫn 200

    bell = await bot.sweep(config=EVERY_ROW)

    assert (tg, update_id) in bell.notified
    await bot.drain(tg)
    assert bot.outbox.texts_to(tg) != []  # tin được trả lời dù chuông đầu bị mất
    assert (await bot.row(update_id)).status == "replied"


async def test_the_sweep_leaves_a_row_alone_until_it_has_waited_long_enough(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)  # chuông của chính nó đang trên đường tới

    bell = await bot.sweep(config=BotWorkerConfig(sweep_stale_seconds=30))

    assert (tg, update_id) not in bell.notified


async def test_the_sweep_rings_for_an_expired_lease_and_for_a_retry_that_is_due(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    user_id, expired_chat = await linked_user(bot)
    _, retry_chat = await linked_user(bot)
    stuck, retry = next_update_id(), next_update_id()
    await bot.insert_row(
        expired_chat, user_id, stuck, status="processing", attempts=1, lease_until=_past()
    )
    await bot.insert_row(retry_chat, user_id, retry, attempts=1, lease_until=_past())

    bell = await bot.sweep(config=EVERY_ROW)

    assert (expired_chat, stuck) in bell.notified
    assert (retry_chat, retry) in bell.notified


async def test_the_sweep_does_not_ring_for_a_chat_that_is_busy_or_waiting_for_a_retry(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    user_id, busy_chat = await linked_user(bot)
    _, waiting_chat = await linked_user(bot)
    busy_head, busy_behind = next_update_id(), next_update_id()
    waiting_head, waiting_behind = next_update_id(), next_update_id()
    await bot.insert_row(
        busy_chat, user_id, busy_head, status="processing", attempts=1, lease_until=_future()
    )
    await bot.insert_row(busy_chat, user_id, busy_behind)
    await bot.insert_row(waiting_chat, user_id, waiting_head, attempts=1, lease_until=_future())
    await bot.insert_row(waiting_chat, user_id, waiting_behind)

    bell = await bot.sweep(config=EVERY_ROW)

    rung_chats = {chat for chat, _ in bell.notified}
    assert busy_chat not in rung_chats  # đang có dòng chạy còn lease: chuông thừa
    assert waiting_chat not in rung_chats  # dòng đầu đang chờ thử lại chặn cả chat


async def test_the_sweep_rings_once_per_chat_for_its_oldest_claimable_row(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    user_id, tg = await linked_user(bot)
    oldest, middle, newest = next_update_id(), next_update_id(), next_update_id()
    for update_id in (oldest, middle, newest):
        await bot.insert_row(
            tg, user_id, update_id, status="processing", attempts=1, lease_until=_past()
        )

    bell = await bot.sweep(config=EVERY_ROW)

    assert bell.notified == [(tg, oldest)]  # một chuông cho cả chat, gắn với dòng cũ nhất


async def test_the_sweep_does_nothing_when_the_chatbot_is_switched_off(chatbot_bot: Bot) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    await bot.send("xin chào", tg=tg)

    bell = await bot.sweep(config=BotWorkerConfig(enabled=False, sweep_stale_seconds=0))

    assert bell.notified == []


async def test_two_sweeps_at_once_ring_the_same_bells_and_the_row_is_still_answered_once(
    chatbot_bot_factory,  # noqa: ANN001
) -> None:
    from app.services.bot_policy import ChatbotPolicy

    bot: Bot = chatbot_bot_factory(ChatbotPolicy(enabled=True), dispatcher=_RaisingDispatcher())
    _, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)

    first, second = await asyncio.gather(
        bot.sweep(config=EVERY_ROW),
        bot.sweep(config=EVERY_ROW),
    )

    # `_job_id="bot:<update_id>"` làm hai chuông trùng nhau chỉ thành một job; ở đây thấy cả hai
    # cron cùng nhắm đúng một dòng, và cron không đổi trạng thái dòng nào.
    # Quét nhìn mọi chat trong DB dùng chung của phiên test nên chỉ so phần của chat này.
    mine = [(c, u) for c, u in first.notified if c == tg]
    assert mine == [(c, u) for c, u in second.notified if c == tg] == [(tg, update_id)]
    assert (await bot.row(update_id)).status == "queued"
    await asyncio.gather(bot.drain(tg), bot.drain(tg))
    assert bot.outbox.texts_to(tg) != [] and len(bot.outbox.texts_to(tg)) == 1  # đúng một lần


async def test_the_cleanup_removes_old_finished_rows_and_keeps_everything_else(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    user_id, tg = await linked_user(bot)
    ids = {
        name: next_update_id()
        for name in ("old_replied", "old_failed", "new_dropped", "old_queued", "new_replied")
    }
    long_ago, recently = _past(40 * 86400), _past(5 * 86400)
    await bot.insert_row(tg, user_id, ids["old_replied"], status="replied", finished_at=long_ago)
    await bot.insert_row(
        tg, user_id, ids["old_failed"], status="failed", finished_at=_past(31 * 86400)
    )
    await bot.insert_row(
        tg, user_id, ids["new_dropped"], status="dropped", finished_at=_past(29 * 86400)
    )  # sát hạn 30 ngày nhưng chưa quá
    await bot.insert_row(tg, user_id, ids["old_queued"], received_at=long_ago)  # còn mở: không xóa
    await bot.insert_row(tg, user_id, ids["new_replied"], status="replied", finished_at=recently)

    deleted = await bot.cleanup()

    assert deleted >= 2
    remaining = {r.update_id for r in await bot.inbox_rows(tg)}
    assert remaining == {ids["new_dropped"], ids["old_queued"], ids["new_replied"]}
