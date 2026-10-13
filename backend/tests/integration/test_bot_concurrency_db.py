"""`drain_chat` thật dưới tranh chấp (kế hoạch 5.1, S2): một dòng chạy mỗi chat, chat độc lập.

Khác `test_bot_claim_db.py` (đo thuật toán claim), ở đây chạy cả vòng worker: claim, engine, lưu,
gửi, hoàn tất, với nhiều worker cùng chạy trên Postgres thật.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from bot_harness import Bot, linked_user
from db_helpers import next_update_id
from sqlalchemy import text

from app.integrations.telegram import TelegramForbiddenError
from app.services.chat_engine import ChatReply, ChatTurn
from app.services.telegram_bot_messages import LOST_MESSAGE_TEXT


class _TrackingEngine:
    """Ghi lại thứ tự các tin và số cuộc gọi engine chạy cùng lúc."""

    def __init__(self, delay: float = 0.02) -> None:
        self._delay = delay
        self.texts: list[str] = []
        self.active = 0
        self.max_active = 0

    async def reply(self, turn: ChatTurn) -> ChatReply:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        self.texts.append(turn.text)
        await asyncio.sleep(self._delay)
        self.active -= 1
        return ChatReply("ok")


async def _statuses(bot: Bot, chat_id: int) -> list[str]:
    return [row.status for row in await bot.inbox_rows(chat_id)]


async def test_five_messages_of_one_chat_are_answered_in_order_once_each_by_competing_workers(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    for number in range(1, 6):
        await bot.send(str(number), tg=tg)
    engine = _TrackingEngine()

    async def worker() -> int:
        handled = 0
        async with asyncio.timeout(30):  # lỗi phải hiện thành test fail, không treo
            while "queued" in await _statuses(bot, tg) or "processing" in await _statuses(bot, tg):
                handled += await bot.drain(tg, engine=engine)
                await asyncio.sleep(0.001)
        return handled

    handled = await asyncio.gather(worker(), worker(), worker())

    assert engine.max_active == 1  # không bao giờ hai tin của một chat chạy cùng lúc
    assert engine.texts == ["1", "2", "3", "4", "5"]  # đúng thứ tự, mỗi tin một lần
    assert sum(handled) == 5
    assert await _statuses(bot, tg) == ["replied"] * 5
    assert bot.outbox.texts_to(tg) == ["ok"] * 5


class _GateEngine:
    """Tin "chậm" bị kẹt cho đến khi được mở; mọi tin khác trả lời ngay."""

    def __init__(self) -> None:
        self.slow_started = asyncio.Event()
        self.release = asyncio.Event()

    async def reply(self, turn: ChatTurn) -> ChatReply:
        if turn.text == "chậm":
            self.slow_started.set()
            await self.release.wait()
        return ChatReply("ok")


async def test_a_busy_chat_does_not_hold_up_another_chat(chatbot_bot: Bot) -> None:
    bot = chatbot_bot
    _, slow_chat = await linked_user(bot)
    _, fast_chat = await linked_user(bot)
    engine = _GateEngine()
    await bot.send("chậm", tg=slow_chat)
    await bot.send("nhanh", tg=fast_chat)
    slow = asyncio.create_task(bot.drain(slow_chat, engine=engine))
    await asyncio.wait_for(engine.slow_started.wait(), timeout=5)  # chat chậm đang kẹt trong engine

    fast_handled = await asyncio.wait_for(bot.drain(fast_chat, engine=engine), timeout=2)

    assert fast_handled == 1
    assert bot.outbox.texts_to(fast_chat) == ["ok"]
    assert not slow.done()
    engine.release.set()
    assert await slow == 1


class _ProbeClient:
    """Client giả đọc DB đúng lúc gửi tin: chứng minh câu xin lỗi chỉ gửi SAU khi đã commit.

    `fail_apology`: mô phỏng người dùng đã chặn bot (chỉ câu xin lỗi bị Telegram từ chối).
    """

    def __init__(self, bot: Bot, exhausted_id: int, *, fail_apology: bool = False) -> None:
        self._bot = bot
        self._id = exhausted_id
        self._fail_apology = fail_apology
        self.sent: list[tuple[int, str, str | None]] = []

    async def send_message(self, chat_id: int, text_: str, **kwargs: Any) -> int:
        async with self._bot.session_factory() as session:
            status = await session.scalar(
                text("select status from bot_updates where update_id = :i"),
                {"i": self._id},
            )
        self.sent.append((chat_id, text_, status))
        if self._fail_apology and text_ == LOST_MESSAGE_TEXT:
            raise TelegramForbiddenError("Forbidden: bot was blocked by the user", error_code=403)
        return 1


async def _stuck_then_next(bot: Bot, tg: int, user_id: Any, *, stuck_count: int = 1) -> list[int]:
    """Dựng `stuck_count` dòng đã hết số lần thử (lease hết hạn), theo sau là một dòng thường."""
    expired = datetime.now(UTC) - timedelta(seconds=5)
    ids = [next_update_id() for _ in range(stuck_count + 1)]
    for update_id in ids[:-1]:
        await bot.insert_row(
            tg,
            user_id,
            update_id,
            status="processing",
            attempts=3,
            lease_until=expired,
            text_="kẹt",
        )
    await bot.insert_row(tg, user_id, ids[-1], text_="tiếp theo")
    return ids


async def test_a_row_out_of_attempts_gets_one_apology_after_the_commit_and_the_next_row_runs(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    user_id, tg = await linked_user(bot)
    stuck, behind = await _stuck_then_next(bot, tg, user_id)
    probe = _ProbeClient(bot, stuck)

    handled = await bot.drain(tg, engine=_TrackingEngine(0), client=probe)

    assert handled == 1  # dòng bị kẹt không tính là đã xử lý
    apologies = [
        (chat, state) for chat, message, state in probe.sent if message == LOST_MESSAGE_TEXT
    ]
    assert apologies == [
        (tg, "failed")
    ]  # đúng chat, đúng một câu, lúc gửi dòng đã `failed` và commit
    rows = {r.update_id: r for r in await bot.inbox_rows(tg)}
    assert (rows[stuck].status, rows[stuck].error_category) == ("failed", "lease_exhausted")
    assert (rows[stuck].payload_text, rows[stuck].reply_text) == (None, None)
    assert rows[stuck].finished_at is not None
    assert rows[behind].status == "replied"


async def test_a_blocked_user_does_not_stop_the_worker_when_the_apology_is_refused(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    user_id, tg = await linked_user(bot)
    stuck, behind = await _stuck_then_next(bot, tg, user_id)
    probe = _ProbeClient(bot, stuck, fail_apology=True)

    handled = await bot.drain(tg, engine=_TrackingEngine(0), client=probe)

    assert handled == 1  # vòng xử lý vẫn đi tiếp tới dòng sau
    rows = {r.update_id: r.status for r in await bot.inbox_rows(tg)}
    assert rows == {stuck: "failed", behind: "replied"}


async def test_several_rows_out_of_attempts_in_one_claim_get_a_single_apology(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    user_id, tg = await linked_user(bot)
    first, second, behind = await _stuck_then_next(bot, tg, user_id, stuck_count=2)
    probe = _ProbeClient(bot, first)

    await bot.drain(tg, engine=_TrackingEngine(0), client=probe)

    apologies = [message for _, message, _ in probe.sent if message == LOST_MESSAGE_TEXT]
    assert apologies == [LOST_MESSAGE_TEXT]  # một câu cho mỗi lần claim, không phải mỗi dòng
    assert {r.update_id: r.status for r in await bot.inbox_rows(tg)} == {
        first: "failed",
        second: "failed",
        behind: "replied",
    }
