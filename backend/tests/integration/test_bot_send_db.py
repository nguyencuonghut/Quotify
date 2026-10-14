"""Đường gửi câu trả lời của worker chatbot (kế hoạch 5.1, S4): chia tin, gửi tiếp, lỗi gửi.

Postgres thật; ranh giới hệ thống (Telegram, engine/LLM) được giả. Câu trả lời do engine sinh luôn
là văn bản thuần, chia ở ranh giới đoạn khi vượt giới hạn 4.096 ký tự của Telegram.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from bot_fakes import FakeClock, RecordingClient, ScriptedEngine
from bot_harness import Bot, linked_user
from db_helpers import create_user, next_update_id
from sqlalchemy import text

from app.bot_worker import BotWorkerConfig
from app.integrations.telegram import (
    TELEGRAM_MESSAGE_MAX_LENGTH,
    TelegramApiError,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRateLimitError,
)
from app.services.bot_inbox import BotInbox
from app.services.chat_engine import ChatReply, ChatTurn
from app.services.telegram_bot_messages import LOST_MESSAGE_TEXT


async def test_a_long_reply_is_delivered_as_ordered_plain_text_parts_within_the_limit(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("viết dài giúp tôi", tg=tg)
    paragraphs = [f"Đoạn {number}: " + "x" * 1500 for number in range(1, 7)]  # khoảng 9.000 ký tự
    reply = "\n\n".join(paragraphs)

    await bot.drain(tg, engine=ScriptedEngine(reply))

    parts = bot.outbox.texts_to(tg)
    assert len(parts) == 3
    assert all(len(part) <= TELEGRAM_MESSAGE_MAX_LENGTH for part in parts)
    assert "\n\n".join(parts) == reply  # đủ nội dung, đúng thứ tự, cắt ở ranh giới đoạn
    assert all(
        "parse_mode" not in message for message in bot.outbox.sent_messages()
    )  # văn bản thuần
    row = await bot.row(update_id)
    assert (row.status, row.sent_parts) == ("replied", 3)


async def test_a_failure_between_parts_resumes_from_the_first_unsent_part_without_repeating(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("viết dài giúp tôi", tg=tg)
    reply = "\n\n".join(f"Đoạn {number}: " + "x" * 1500 for number in range(1, 7))
    # Phần 1 gửi được, phần 2 lỗi mạng; lần thử sau Telegram trả lời bình thường.
    client = RecordingClient(None, TelegramNetworkError("Không thể gọi Telegram: ConnectError."))
    engine = ScriptedEngine(reply)

    await bot.drain(tg, engine=engine, client=client)

    row = await bot.row(update_id)
    assert (row.status, row.sent_parts) == ("queued", 1)  # chờ thử lại, phần 1 đã tính là xong
    await bot.set_lease(update_id, datetime.now(UTC) - timedelta(seconds=1))
    await bot.drain(tg, engine=engine, client=client)

    assert engine.calls == 1  # không gọi lại engine
    texts = [text for _, text in client.sent]
    assert "\n\n".join(texts) == reply  # mỗi phần đúng một lần, đúng thứ tự
    assert len(texts) == 3
    assert (await bot.row(update_id)).status == "replied"


async def test_an_empty_reply_from_the_engine_is_retried_instead_of_sent(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)

    await bot.drain(tg, engine=ScriptedEngine("  \n "))  # Telegram từ chối tin rỗng

    row = await bot.row(update_id)
    assert (row.status, row.attempts, row.reply_text) == ("queued", 1, None)
    assert bot.outbox.texts_to(tg) == []


async def test_a_half_sent_reply_is_finished_even_when_its_message_is_past_the_ttl(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    user_id, tg = await linked_user(bot)
    update_id = next_update_id()
    first, second = "đoạn một " + "x" * 3000, "đoạn hai " + "y" * 3000
    await bot.insert_row(
        tg,
        user_id,
        update_id,
        status="processing",
        attempts=1,
        lease_until=datetime.now(UTC) - timedelta(seconds=1),
        received_at=datetime.now(UTC) - timedelta(hours=2),  # quá TTL, nhưng đã gửi được một phần
        reply_text=first + "\n\n" + second,
        sent_parts=1,
    )
    client = RecordingClient()

    await bot.drain(tg, engine=ScriptedEngine("không được gọi"), client=client)

    assert client.sent == [(tg, second)]  # nửa sau được gửi nốt, không xin người dùng gửi lại
    assert (await bot.row(update_id)).status == "replied"


# --- phân loại lỗi gửi -------------------------------------------------------------------------


async def test_a_blocked_bot_marks_the_link_blocked_and_drops_the_row_without_retry_or_apology(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    user_id, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)
    client = RecordingClient(
        TelegramForbiddenError("Forbidden: bot was blocked by the user", error_code=403)
    )
    engine = ScriptedEngine("trả lời")

    await bot.drain(tg, engine=engine, client=client)

    row = await bot.row(update_id)
    assert (row.status, row.error_category, row.reply_text, row.payload_text) == (
        "dropped",
        "forbidden",
        None,
        None,
    )
    assert [account.status for account in await bot.accounts(user_id)] == ["blocked"]
    assert client.attempts == [(tg, "trả lời")]  # không thử lại, không xin lỗi người chặn bot


async def test_a_reply_that_keeps_failing_to_send_ends_failed_and_the_user_gets_an_apology(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)
    network = TelegramNetworkError("Không thể gọi Telegram (sendMessage): ConnectError.")
    client = RecordingClient(network, network, None)  # hai lần gửi lỗi, lời xin lỗi gửi được
    config = BotWorkerConfig(max_attempts=2)

    await bot.drain(tg, engine=ScriptedEngine("a"), client=client, config=config)
    await bot.set_lease(update_id, datetime.now(UTC) - timedelta(seconds=1))
    await bot.drain(tg, engine=ScriptedEngine("a"), client=client, config=config)

    row = await bot.row(update_id)
    assert (row.status, row.error_category, row.attempts) == ("failed", "send_failed", 2)
    assert client.sent == [(tg, LOST_MESSAGE_TEXT)]  # chat vẫn tới được thì không để im lặng


async def test_a_reply_rejected_by_telegram_fails_at_once_with_an_apology_and_no_retry(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)
    rejected = TelegramApiError("Bad Request: message text is empty", error_code=400)
    client = RecordingClient(rejected, None)

    await bot.drain(tg, engine=ScriptedEngine("a"), client=client)

    row = await bot.row(update_id)
    assert (row.status, row.error_category, row.attempts) == ("failed", "send_rejected", 1)
    assert client.sent == [(tg, LOST_MESSAGE_TEXT)]  # thử lại cũng vẫn 400: xin lỗi luôn


# --- 429 và ngân sách gửi ----------------------------------------------------------------------


def _rate_limited(retry_after: int) -> TelegramRateLimitError:
    return TelegramRateLimitError(
        f"Too Many Requests: retry after {retry_after}",
        error_code=429,
        retry_after=retry_after,
    )


async def test_a_rate_limited_part_waits_for_retry_after_and_is_then_delivered(
    chatbot_bot: Bot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)
    clock = FakeClock().install(monkeypatch)
    client = RecordingClient(_rate_limited(2), None)

    await bot.drain(tg, engine=ScriptedEngine("trả lời"), client=client)

    assert clock.waited == [2]  # chờ đúng `retry_after` rồi gửi lại cùng phần đó
    assert client.sent == [(tg, "trả lời")]
    row = await bot.row(update_id)
    assert (row.status, row.attempts) == ("replied", 1)  # không tốn lần thử


async def test_a_wait_longer_than_the_remaining_budget_stops_at_once_and_retries_later(
    chatbot_bot: Bot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)
    clock = FakeClock().install(monkeypatch)
    client = RecordingClient(_rate_limited(30))

    await bot.drain(
        tg,
        engine=ScriptedEngine("trả lời"),
        client=client,
        config=BotWorkerConfig(send_budget_seconds=10),
    )

    assert clock.waited == []  # biết trước không đủ ngân sách thì không chờ vô ích
    row = await bot.row(update_id)
    assert (row.status, row.sent_parts, row.reply_text) == ("queued", 0, "trả lời")  # gửi lần sau


async def test_repeated_rate_limits_never_wait_longer_than_the_budget_in_total(
    chatbot_bot: Bot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)
    clock = FakeClock().install(monkeypatch)
    client = RecordingClient(_rate_limited(6), _rate_limited(6), None)

    await bot.drain(
        tg,
        engine=ScriptedEngine("trả lời"),
        client=client,
        config=BotWorkerConfig(send_budget_seconds=10),
    )

    assert clock.waited == [6]  # lần chờ thứ hai (6 giây) vượt phần ngân sách còn lại (4 giây)
    assert client.sent == []
    assert (await bot.row(update_id)).status == "queued"


async def test_a_wait_that_exactly_uses_the_remaining_budget_is_still_taken(
    chatbot_bot: Bot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    await bot.send("xin chào", tg=tg)
    clock = FakeClock().install(monkeypatch)
    client = RecordingClient(_rate_limited(10), None)

    await bot.drain(
        tg,
        engine=ScriptedEngine("trả lời"),
        client=client,
        config=BotWorkerConfig(send_budget_seconds=10),
    )

    assert clock.waited == [10]  # vừa đúng phần ngân sách còn lại thì vẫn chờ rồi gửi
    assert client.sent == [(tg, "trả lời")]


async def test_a_wait_beyond_the_budget_is_honoured_when_scheduling_the_next_attempt(
    chatbot_bot: Bot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)
    FakeClock().install(monkeypatch)

    await bot.drain(
        tg,
        engine=ScriptedEngine("trả lời"),
        client=RecordingClient(_rate_limited(300)),
        config=BotWorkerConfig(send_budget_seconds=10),
    )

    row = await bot.row(update_id)
    waited = (row.lease_until - datetime.now(UTC)).total_seconds()
    assert row.status == "queued" and 290 < waited <= 300  # Telegram bảo chờ 300 giây thì chờ


async def test_running_out_of_budget_on_a_long_flood_wait_ends_as_a_timeout_with_an_apology(
    chatbot_bot: Bot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)
    FakeClock().install(monkeypatch)
    client = RecordingClient(_rate_limited(300), None)  # lần gửi bị chặn, lời xin lỗi gửi được

    await bot.drain(
        tg,
        engine=ScriptedEngine("trả lời"),
        client=client,
        config=BotWorkerConfig(send_budget_seconds=10, max_attempts=1),
    )

    row = await bot.row(update_id)
    assert (row.status, row.error_category) == ("failed", "send_timeout")
    assert client.sent == [(tg, LOST_MESSAGE_TEXT)]


@pytest.mark.parametrize("retry_after", [None, 0])
async def test_a_missing_or_zero_retry_after_still_waits_a_second_instead_of_spinning(
    chatbot_bot: Bot,
    monkeypatch: pytest.MonkeyPatch,
    retry_after: int | None,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    await bot.send("xin chào", tg=tg)
    clock = FakeClock().install(monkeypatch)
    limited = TelegramRateLimitError("Too Many Requests", error_code=429, retry_after=retry_after)
    client = RecordingClient(limited, None)

    await bot.drain(tg, engine=ScriptedEngine("trả lời"), client=client)

    assert clock.waited == [1]
    assert client.sent == [(tg, "trả lời")]


class _HangingClient(RecordingClient):
    """Gửi tin trả lời thì treo mãi (mạng chết giữa chừng); lời xin lỗi vẫn gửi được."""

    async def send_message(self, chat_id: int, text_: str, **kwargs: Any) -> int:
        if text_ == LOST_MESSAGE_TEXT:
            return await super().send_message(chat_id, text_, **kwargs)
        await asyncio.sleep(3600)
        raise AssertionError("không tới được đây")


async def test_a_send_that_hangs_is_cut_by_the_budget_and_counted_as_a_timeout(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)
    client = _HangingClient()

    await bot.drain(
        tg,
        engine=ScriptedEngine("trả lời"),
        client=client,
        config=BotWorkerConfig(send_budget_seconds=0.2, max_attempts=1),
    )

    row = await bot.row(update_id)
    assert (row.status, row.error_category) == ("failed", "send_timeout")
    assert client.sent == [(tg, LOST_MESSAGE_TEXT)]


async def test_a_429_from_the_telegram_api_waits_for_the_retry_after_it_reports(
    chatbot_bot: Bot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Qua client HTTP thật: `parameters.retry_after` trong thân 429 phải tới được vòng chờ."""
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)
    clock = FakeClock().install(monkeypatch)
    bot.outbox.script(
        "sendMessage",
        (
            429,
            {
                "ok": False,
                "error_code": 429,
                "description": "Too Many Requests: retry after 3",
                "parameters": {"retry_after": 3},
            },
        ),
    )

    await bot.drain(tg, engine=ScriptedEngine("trả lời"))

    assert clock.waited == [3]
    assert bot.outbox.texts_to(tg) == ["trả lời", "trả lời"]  # lần đầu bị 429, lần sau tới nơi
    assert (await bot.row(update_id)).status == "replied"


# --- chỉ báo "đang gõ" -------------------------------------------------------------------------

TYPING_EVERY_20_MS = BotWorkerConfig(typing_interval_seconds=0.02)
DECOY = "BI-MAT-1234567890"


class _EngineThatNeedsTyping:
    """Chỉ trả lời sau khi đã thấy ít nhất `minimum` chỉ báo "đang gõ" (đếm bằng `count`)."""

    def __init__(self, count: Callable[[], int], *, minimum: int) -> None:
        self._count = count
        self._minimum = minimum
        self.actions_seen = 0

    async def reply(self, turn: ChatTurn) -> ChatReply:
        deadline = time.monotonic() + 2
        # Giả lập không có sự kiện để chờ nên hỏi lại theo chu kỳ, có thời hạn.
        while self._count() < self._minimum and time.monotonic() < deadline:  # noqa: ASYNC110
            await asyncio.sleep(0.01)
        self.actions_seen = self._count()
        return ChatReply("trả lời")


async def test_the_typing_indicator_is_sent_while_the_engine_runs_and_repeats(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    await bot.send("xin chào", tg=tg)
    engine = _EngineThatNeedsTyping(lambda: len(bot.outbox.chat_actions()), minimum=2)

    await bot.drain(tg, engine=engine, config=TYPING_EVERY_20_MS)

    assert engine.actions_seen >= 2  # đã báo "đang gõ" trước khi có câu trả lời, và lặp lại
    assert all(
        action == {"chat_id": tg, "action": "typing"} for action in bot.outbox.chat_actions()
    )
    assert bot.outbox.texts_to(tg) == ["trả lời"]


async def test_the_typing_indicator_stops_once_the_engine_has_answered(chatbot_bot: Bot) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    await bot.send("xin chào", tg=tg)
    engine = _EngineThatNeedsTyping(lambda: len(bot.outbox.chat_actions()), minimum=1)

    await bot.drain(tg, engine=engine, config=TYPING_EVERY_20_MS)
    after_answer = len(bot.outbox.chat_actions())
    await asyncio.sleep(0.2)  # nếu tác vụ nền còn sống thì trong 0,2 giây phải gửi thêm ~10 lần

    assert len(bot.outbox.chat_actions()) == after_answer


async def test_a_failing_typing_indicator_never_stops_the_reply_or_its_own_repeats(
    chatbot_bot: Bot,
) -> None:
    class _TypingBroken(RecordingClient):
        async def send_chat_action(self, chat_id: int, action: str = "typing") -> bool:
            self.chat_actions.append((chat_id, action))
            raise TelegramForbiddenError("Forbidden: bot was blocked", error_code=403)

    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)
    client = _TypingBroken()
    # Engine chỉ trả lời khi đã có ít nhất 2 lần gọi: tức là vòng lặp sống tiếp sau lỗi đầu tiên.
    engine = _EngineThatNeedsTyping(lambda: len(client.chat_actions), minimum=2)

    await bot.drain(tg, engine=engine, client=client, config=TYPING_EVERY_20_MS)

    assert engine.actions_seen >= 2
    assert client.sent == [(tg, "trả lời")]
    assert (await bot.row(update_id)).status == "replied"


async def test_the_first_typing_indicator_goes_out_at_once_not_after_a_whole_interval(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    await bot.send("xin chào", tg=tg)
    engine = _EngineThatNeedsTyping(lambda: len(bot.outbox.chat_actions()), minimum=1)

    await bot.drain(tg, engine=engine, config=BotWorkerConfig(typing_interval_seconds=60))

    assert engine.actions_seen == 1  # không phải đợi hết 60 giây mới có chỉ báo đầu tiên


async def test_no_typing_indicator_is_sent_when_only_a_saved_reply_is_resent(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)
    network = TelegramNetworkError("Không thể gọi Telegram (sendMessage): ConnectError.")
    client = RecordingClient(network)  # lần gửi đầu lỗi, lần sau được
    await bot.drain(tg, engine=ScriptedEngine("trả lời"), client=client, config=TYPING_EVERY_20_MS)
    typing_so_far = len(client.chat_actions)
    await bot.set_lease(update_id, datetime.now(UTC) - timedelta(seconds=1))

    await bot.drain(tg, engine=ScriptedEngine("không được gọi"), client=client)

    assert len(client.chat_actions) == typing_so_far  # không có engine chạy thì không báo gõ
    assert (await bot.row(update_id)).status == "replied"


# --- các nhánh gửi còn lại ---------------------------------------------------------------------

TWO_PARTS = "\n\n".join(["đoạn một " + "x" * 3000, "đoạn hai " + "y" * 3000])


async def test_the_part_cap_from_the_worker_config_limits_a_long_reply(chatbot_bot: Bot) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    await bot.send("viết dài", tg=tg)
    reply = "\n\n".join(f"đoạn {number} " + "x" * 3000 for number in range(1, 9))

    await bot.drain(tg, engine=ScriptedEngine(reply), config=BotWorkerConfig(reply_max_parts=2))

    parts = bot.outbox.texts_to(tg)
    assert len(parts) == 2 and parts[-1].endswith("…")  # phần dư bị cắt


async def test_a_server_error_from_telegram_is_retried_without_an_apology(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)
    client = RecordingClient(TelegramApiError("Bad Gateway", error_code=502))

    await bot.drain(tg, engine=ScriptedEngine("trả lời"), client=client)

    row = await bot.row(update_id)
    assert (row.status, row.attempts) == ("queued", 1)  # thử lại sau backoff, chưa xin lỗi
    assert client.sent == []


async def test_a_worker_taken_over_between_parts_stops_without_sending_more_or_completing(
    chatbot_bot: Bot,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("viết dài", tg=tg)

    class _TakenOverAfterFirstPart(RecordingClient):
        async def send_message(self, chat_id: int, text_: str, **kwargs: Any) -> int:
            result = await super().send_message(chat_id, text_, **kwargs)
            if len(self.sent) == 1:  # worker khác tiếp quản ngay sau phần đầu (attempts tăng)
                async with bot.session_factory() as session:
                    await session.execute(
                        text("update bot_updates set attempts = attempts + 1 where update_id = :i"),
                        {"i": update_id},
                    )
                    await session.commit()
            return result

    client = _TakenOverAfterFirstPart()

    await bot.drain(tg, engine=ScriptedEngine(TWO_PARTS), client=client)

    assert len(client.sent) == 1  # phần hai không được gửi
    row = await bot.row(update_id)
    assert (row.status, row.attempts, row.sent_parts) == ("processing", 2, 0)  # không hoàn tất
    assert "bot.row_lost" in caplog.text and "bot.row_done" not in caplog.text  # biết là mất quyền


async def test_the_sent_parts_write_is_fenced_by_the_claim_it_belongs_to(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    user_id, tg = await linked_user(bot)
    update_id = next_update_id()
    await bot.insert_row(tg, user_id, update_id, text_="x")
    start = datetime(2026, 10, 13, 3, 0, tzinfo=UTC)

    async def claim(now: datetime) -> Any:
        async with bot.session_factory() as session:
            result = await BotInbox(session).claim(tg, now=now, lease_seconds=240, max_attempts=3)
            await session.commit()
            return result.row

    async def save(attempts: int, parts: int) -> bool:
        async with bot.session_factory() as session:
            saved = await BotInbox(session).save_sent_parts(update_id, attempts, parts)
            await session.commit()
            return saved

    await claim(start)
    await claim(start + timedelta(seconds=241))  # worker mới tiếp quản (attempts 2)

    assert not await save(1, 1)  # token cũ không ghi được khi worker mới còn sống
    assert (await bot.row(update_id)).sent_parts == 0
    assert await save(2, 1)
    assert (await bot.row(update_id)).sent_parts == 1
    async with bot.session_factory() as session:  # dòng đã kết thúc thì không ghi được nữa
        await BotInbox(session).complete(update_id, 2, now=start + timedelta(seconds=300))
        await session.commit()
    assert not await save(2, 2)


async def test_no_text_of_a_send_failure_or_of_the_reply_reaches_the_logs(
    chatbot_bot: Bot,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)
    leaky = RuntimeError(f"gửi lỗi, câu trả lời là {DECOY}")
    # Cả lần gửi lẫn lời xin lỗi đều lỗi với thông điệp chứa nội dung.
    client = RecordingClient(leaky, leaky)

    await bot.drain(
        tg,
        engine=ScriptedEngine(f"trả lời {DECOY}"),
        client=client,
        config=BotWorkerConfig(max_attempts=1),
    )

    assert (await bot.row(update_id)).status == "failed"
    assert len(client.attempts) == 2  # lần gửi và lời xin lỗi đều đã chạy qua nhánh lỗi
    assert DECOY not in caplog.text


async def test_a_link_that_now_belongs_to_someone_else_is_dropped_before_and_after_the_engine(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    other_user = await create_user(bot.session_factory)
    update_id = await bot.send("xin chào", tg=tg)
    async with bot.session_factory() as session:  # liên kết Telegram này chuyển sang người khác
        await session.execute(
            text("update telegram_accounts set user_id = :u where telegram_user_id = :t"),
            {"u": other_user, "t": tg},
        )
        await session.commit()
    engine = ScriptedEngine("không được gọi")

    await bot.drain(tg, engine=engine)

    row = await bot.row(update_id)
    assert (row.status, row.error_category) == ("dropped", "unlinked")
    assert engine.calls == 0 and bot.outbox.texts_to(tg) == []
