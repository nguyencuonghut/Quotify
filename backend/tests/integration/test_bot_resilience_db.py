"""Chịu lỗi của worker chatbot (kế hoạch 5.1, S3): thử lại, thất bại, tiếp tục, rào chắn, hủy.

Postgres thật; ranh giới hệ thống (Telegram, engine/LLM) được giả. Không bao giờ để nội dung tin hay
nguyên văn ngoại lệ lọt vào `error_category`, log hay câu trả lời.
"""

from __future__ import annotations

import asyncio
import logging
import time
import traceback
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from bot_fakes import GateEngine, RecordingClient, ScriptedEngine
from bot_harness import Bot, linked_user
from db_helpers import next_update_id
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.bot_worker import BotWorkerConfig
from app.integrations.telegram import TelegramNetworkError
from app.services.bot_inbox import BotInbox, BotInboxError
from app.services.chat_engine import ChatEngineError, ChatEngineTemporaryError, ChatReply, ChatTurn
from app.services.telegram_bot_messages import EXPIRED_MESSAGE_TEXT, LOST_MESSAGE_TEXT

DECOY = "BI-MAT-1234567890"


def _past() -> datetime:
    return datetime.now(UTC) - timedelta(seconds=1)


class _SlowEngine:
    async def reply(self, turn: ChatTurn) -> ChatReply:
        await asyncio.sleep(5)
        return ChatReply("muộn")


# --- lỗi của engine: thử lại có backoff, rồi thất bại -----------------------------------------


async def test_a_temporary_engine_error_requeues_the_row_with_a_backoff_and_a_later_attempt_answers(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)
    engine = ScriptedEngine(ChatEngineTemporaryError("llm 503"), "ok")

    await bot.drain(tg, engine=engine)

    row = await bot.row(update_id)
    assert (row.status, row.attempts) == ("queued", 1)
    assert row.lease_until > datetime.now(UTC)  # backoff: chưa thử lại ngay
    assert bot.outbox.texts_to(tg) == []  # chưa trả lời, cũng chưa xin lỗi
    assert await bot.drain(tg, engine=engine) == 0  # backoff chưa hết: không claim được

    await bot.set_lease(update_id, _past())
    assert await bot.drain(tg, engine=engine) == 1

    row = await bot.row(update_id)
    assert (row.status, row.attempts) == ("replied", 2)
    assert bot.outbox.texts_to(tg) == ["ok"]
    assert engine.calls == 2


async def test_a_row_that_keeps_failing_ends_failed_with_one_apology_and_no_raw_error_text(
    chatbot_bot: Bot,
    caplog: pytest.LogCaptureFixture,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)
    engine = ScriptedEngine(*(ChatEngineTemporaryError(DECOY) for _ in range(5)))
    config = BotWorkerConfig(max_attempts=2)
    caplog.set_level(logging.DEBUG)

    await bot.drain(tg, engine=engine, config=config)  # lần 1: về hàng đợi
    await bot.set_lease(update_id, _past())
    await bot.drain(tg, engine=engine, config=config)  # lần 2 = lần cuối: thất bại

    row = await bot.row(update_id)
    assert (row.status, row.attempts, row.error_category) == ("failed", 2, "engine_error")
    assert (row.payload_text, row.reply_text) == (None, None)
    assert bot.outbox.texts_to(tg) == [LOST_MESSAGE_TEXT]  # đúng một câu xin lỗi
    assert DECOY not in caplog.text and DECOY not in row.error_category


async def test_a_final_engine_error_fails_the_row_at_once_with_one_apology(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)

    await bot.drain(tg, engine=ScriptedEngine(ChatEngineError("cấu hình sai")))

    row = await bot.row(update_id)
    assert (row.status, row.attempts, row.error_category) == ("failed", 1, "engine_error")
    assert bot.outbox.texts_to(tg) == [LOST_MESSAGE_TEXT]


async def test_an_engine_that_runs_past_the_row_timeout_is_retried_then_fails_as_a_timeout(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)
    slow = BotWorkerConfig(row_timeout_seconds=0.05, max_attempts=2)

    await bot.drain(tg, engine=_SlowEngine(), config=slow)
    assert (await bot.row(update_id)).status == "queued"  # còn lần thử

    await bot.set_lease(update_id, _past())
    await bot.drain(tg, engine=_SlowEngine(), config=slow)

    row = await bot.row(update_id)
    assert (row.status, row.error_category) == ("failed", "engine_timeout")
    assert bot.outbox.texts_to(tg) == [LOST_MESSAGE_TEXT]


async def test_an_unexpected_engine_exception_is_retried_and_never_leaks_its_text(
    chatbot_bot: Bot,
    caplog: pytest.LogCaptureFixture,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)
    caplog.set_level(logging.DEBUG)

    await bot.drain(tg, engine=ScriptedEngine(RuntimeError(DECOY)))

    row = await bot.row(update_id)
    assert (row.status, row.attempts) == ("queued", 1)  # lỗi bất ngờ coi như thử lại được
    assert DECOY not in caplog.text


# --- worker chết giữa chừng: tiếp tục từ chỗ đã dừng ------------------------------------------


async def _claim_and_die(bot: Bot, update_id: int, *, save: str | None) -> None:
    """Một worker claim dòng (có thể lưu câu trả lời) rồi chết: lease hết hạn mà không ai xong."""
    async with bot.session_factory() as session:
        inbox = BotInbox(session)
        result = await inbox.claim(
            (await bot.row(update_id)).chat_id,
            now=datetime.now(UTC),
            lease_seconds=240,
            max_attempts=3,
        )
        assert result.row is not None and result.row.update_id == update_id
        if save is not None:
            assert await inbox.save_reply(
                update_id, result.row.attempts, save, now=datetime.now(UTC)
            )
        await session.commit()
    await bot.set_lease(update_id, _past())


async def test_a_worker_that_died_after_saving_the_reply_is_resumed_without_calling_the_engine(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)
    await _claim_and_die(bot, update_id, save="câu đã lưu")
    engine = ScriptedEngine("không được gọi")

    await bot.drain(tg, engine=engine)

    assert engine.calls == 0  # engine không bị gọi lại (KT5): không tốn thêm token
    assert bot.outbox.texts_to(tg) == ["câu đã lưu"]
    row = await bot.row(update_id)
    assert (row.status, row.attempts) == ("replied", 2)


async def test_a_worker_that_died_before_saving_makes_the_next_attempt_call_the_engine_again(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)
    await _claim_and_die(bot, update_id, save=None)
    engine = ScriptedEngine("lần sau")

    await bot.drain(tg, engine=engine)

    assert engine.calls == 1
    assert bot.outbox.texts_to(tg) == ["lần sau"]
    assert (await bot.row(update_id)).attempts == 2  # đếm đúng theo số lần thử


# --- lỗi gửi tin: thử lại bằng câu đã lưu -----------------------------------------------------


async def test_a_send_failure_requeues_the_row_and_the_saved_reply_is_sent_later(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)
    engine = ScriptedEngine("câu trả lời")
    client = RecordingClient(fail_first=1)

    await bot.drain(tg, engine=engine, client=client)

    row = await bot.row(update_id)
    assert (row.status, row.reply_text) == ("queued", "câu trả lời")  # giữ câu đã lưu
    await bot.set_lease(update_id, _past())
    await bot.drain(tg, engine=engine, client=client)

    assert engine.calls == 1  # gửi lại bằng câu đã lưu, không gọi engine lần hai
    assert client.sent == [(tg, "câu trả lời")]
    assert (await bot.row(update_id)).status == "replied"


async def test_the_retry_backoff_grows_with_the_attempt_number(chatbot_bot: Bot) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)
    config = BotWorkerConfig(retry_backoff_seconds=100, max_attempts=5)
    engine = ScriptedEngine(
        ChatEngineTemporaryError("llm 503"), ChatEngineTemporaryError("llm 503")
    )

    await bot.drain(tg, engine=engine, config=config)
    first = await bot.row(update_id)
    await bot.set_lease(update_id, _past())  # backoff coi như đã hết
    await bot.drain(tg, engine=engine, config=config)
    second = await bot.row(update_id)

    assert second.attempts == 2
    first_wait = (first.lease_until - datetime.now(UTC)).total_seconds()
    second_wait = (second.lease_until - datetime.now(UTC)).total_seconds()
    assert 90 < first_wait <= 100  # lần thử 1: 100 × 1
    assert 190 < second_wait <= 200  # lần thử 2: 100 × 2, lùi dần


async def test_neither_the_question_nor_the_answer_is_ever_logged(
    chatbot_bot: Bot,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Cả đường gửi lỗi lẫn đường thành công: log chỉ có định danh, số lần thử và thời gian."""
    caplog.set_level(logging.DEBUG)
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send(f"câu hỏi {DECOY}", tg=tg)
    client = RecordingClient(fail_first=1)  # lần gửi đầu lỗi mạng, lần sau thành công

    await bot.drain(tg, engine=ScriptedEngine(f"trả lời {DECOY}"), client=client)
    await bot.set_lease(update_id, _past())
    await bot.drain(tg, engine=ScriptedEngine("không được gọi"), client=client)

    assert client.sent == [(tg, f"trả lời {DECOY}")]  # cả hai đường đều đã chạy
    assert DECOY not in caplog.text


# --- rào chắn: worker cũ, dòng bị xóa, hủy ----------------------------------------------------


async def test_a_stale_worker_resuming_after_a_takeover_neither_overwrites_nor_sends_twice(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)
    old_engine = GateEngine("của worker cũ")
    old_worker = asyncio.create_task(bot.drain(tg, engine=old_engine))
    await asyncio.wait_for(old_engine.started.wait(), timeout=5)  # worker cũ kẹt trong engine
    await bot.set_lease(update_id, _past())  # lease hết hạn: coi như worker cũ đã chết

    await bot.drain(tg, engine=ScriptedEngine("của worker mới"))  # worker mới tiếp quản và xong
    old_engine.release.set()
    await asyncio.wait_for(old_worker, timeout=5)  # worker cũ tỉnh dậy: không được ghi đè hay gửi

    assert bot.outbox.texts_to(tg) == ["của worker mới"]  # đúng một câu trả lời
    assert (await bot.row(update_id)).status == "replied"


async def test_a_worker_taken_over_between_saving_and_sending_does_not_send_twice(
    chatbot_bot: Bot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cửa sổ đua hẹp nhất: đã lưu câu trả lời nhưng chưa gửi thì lease hết hạn và bị tiếp quản.

    Bước lưu của worker cũ đã xong nên rào chắn của bước lưu không còn cứu được; chỉ phép kiểm
    quyền sở hữu NGAY TRƯỚC khi gửi ngăn worker cũ gửi trùng. Dùng một cổng chặn đúng chỗ đó.
    """
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)
    reached, go = asyncio.Event(), asyncio.Event()
    original_owns = BotInbox.owns
    calls = 0

    async def gated_owns(self: BotInbox, row_id: int, attempts: int) -> bool:
        nonlocal calls
        calls += 1
        if calls == 1:  # chỉ cổng chặn worker cũ, worker mới đi thẳng
            reached.set()
            await go.wait()
        return await original_owns(self, row_id, attempts)

    monkeypatch.setattr(BotInbox, "owns", gated_owns)
    old_client, new_client = RecordingClient(), RecordingClient()
    old_worker = asyncio.create_task(
        bot.drain(tg, engine=ScriptedEngine("của worker cũ"), client=old_client)
    )
    await asyncio.wait_for(reached.wait(), timeout=5)  # đã lưu câu trả lời, chưa gửi
    await bot.set_lease(update_id, _past())  # lease hết hạn: bị tiếp quản

    await bot.drain(tg, engine=ScriptedEngine("không được gọi"), client=new_client)
    go.set()
    await asyncio.wait_for(old_worker, timeout=5)

    assert new_client.sent == [(tg, "của worker cũ")]  # worker mới gửi câu đã lưu, đúng một lần
    assert old_client.sent == []  # worker cũ tỉnh dậy: bị chặn, không gửi trùng
    assert (await bot.row(update_id)).status == "replied"


async def test_a_row_deleted_while_the_engine_runs_does_not_break_the_worker(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)
    engine = GateEngine()
    worker = asyncio.create_task(bot.drain(tg, engine=engine))
    await asyncio.wait_for(engine.started.wait(), timeout=5)
    async with bot.session_factory() as session:  # vd người dùng bị xóa: ON DELETE CASCADE
        await session.execute(
            text("delete from bot_updates where update_id = :i"), {"i": update_id}
        )
        await session.commit()

    engine.release.set()
    await asyncio.wait_for(worker, timeout=5)  # không ném lỗi

    assert bot.outbox.texts_to(tg) == []


async def test_cancelling_the_worker_mid_turn_releases_the_lease_so_the_row_is_claimable_at_once(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)
    engine = GateEngine()
    worker = asyncio.create_task(bot.drain(tg, engine=engine))
    await asyncio.wait_for(engine.started.wait(), timeout=5)

    worker.cancel()  # arq hủy tác vụ khi nhận SIGTERM
    with pytest.raises(asyncio.CancelledError):
        await worker

    row = await bot.row(update_id)
    assert row.status == "processing" and row.lease_until <= datetime.now(UTC)  # lease đã nhả
    assert await bot.drain(tg, engine=ScriptedEngine("sau khi tắt")) == 1  # claim lại tức thì
    assert (await bot.row(update_id)).attempts == 2  # một lần deploy giữa chừng tốn một lần thử
    assert bot.outbox.texts_to(tg) == ["sau khi tắt"]


async def test_an_unexpected_error_while_processing_releases_the_lease_and_still_propagates(
    chatbot_bot: Bot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lỗi ngoài dự kiến (vd DB đứt đúng lúc lưu câu trả lời) không được giữ chat đến hết lease."""
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)

    async def broken_save(self: BotInbox, *args: Any, **kwargs: Any) -> bool:
        raise BotInboxError(
            "Lưu câu trả lời thất bại (ConnectionDoesNotExistError).", transient=True
        )

    monkeypatch.setattr(BotInbox, "save_reply", broken_save)

    with pytest.raises(BotInboxError):  # vẫn ném lên để arq ghi log lỗi
        await bot.drain(tg, engine=ScriptedEngine("đã trả tiền cho câu này"))

    row = await bot.row(update_id)
    assert row.status == "processing" and row.lease_until <= datetime.now(UTC)  # lease đã nhả
    monkeypatch.undo()
    assert await bot.drain(tg, engine=ScriptedEngine("lần sau")) == 1  # claim lại tức thì
    assert bot.outbox.texts_to(tg) == ["lần sau"]


async def test_a_cancel_landing_right_after_the_claim_committed_still_releases_the_lease(
    chatbot_bot: Bot,
) -> None:
    """SIGTERM rơi vào bước đóng phiên của claim (sau commit): dòng đã `processing` nhưng chưa vào
    vùng `try` xử lý, nên nếu không phủ cả đoạn claim thì lease bị giữ đến hết hạn."""
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)
    real_factory = bot.session_factory
    closed = 0

    class _CancelledOnFirstClose:
        def __init__(self) -> None:
            self._inner = real_factory()

        async def __aenter__(self) -> Any:
            return await self._inner.__aenter__()

        async def __aexit__(self, *exc_info: Any) -> None:
            nonlocal closed
            await self._inner.__aexit__(*exc_info)
            closed += 1
            if closed == 1:  # lần đóng đầu tiên chính là phiên của claim
                raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await bot.drain(tg, session_factory=_CancelledOnFirstClose)

    row = await bot.row(update_id)
    assert row.status == "processing" and row.lease_until <= datetime.now(UTC)  # lease đã nhả
    assert await bot.drain(tg, engine=ScriptedEngine("sau khi tắt")) == 1


async def test_an_engine_error_text_does_not_reach_the_traceback_when_the_database_fails_next(
    chatbot_bot: Bot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """arq in cả chuỗi `__context__` của lỗi thoát khỏi worker: nếu xử lý lỗi engine ngay trong khối
    `except` thì lỗi DB sau đó mang theo thông điệp của engine (có thể chứa nội dung tin)."""
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    await bot.send("xin chào", tg=tg)

    async def broken_requeue(self: BotInbox, *args: Any, **kwargs: Any) -> bool:
        raise OperationalError("UPDATE", {}, ConnectionError("db down"))

    monkeypatch.setattr(BotInbox, "requeue", broken_requeue)

    with pytest.raises(OperationalError) as caught:
        await bot.drain(tg, engine=ScriptedEngine(RuntimeError(f"llm lỗi với câu hỏi: {DECOY}")))

    assert DECOY not in "".join(traceback.format_exception(caught.value))


async def test_a_send_error_text_does_not_reach_the_traceback_when_the_database_fails_next(
    chatbot_bot: Bot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    await bot.send("xin chào", tg=tg)

    async def broken_requeue(self: BotInbox, *args: Any, **kwargs: Any) -> bool:
        raise OperationalError("UPDATE", {}, ConnectionError("db down"))

    class _LeakyClient(RecordingClient):
        async def send_message(self, chat_id: int, text_: str, **kwargs: Any) -> int:
            raise TelegramNetworkError(f"gửi lỗi, nội dung: {DECOY}")

    monkeypatch.setattr(BotInbox, "requeue", broken_requeue)

    with pytest.raises(OperationalError) as caught:
        await bot.drain(tg, engine=ScriptedEngine("ok"), client=_LeakyClient())

    assert DECOY not in "".join(traceback.format_exception(caught.value))


async def test_a_stale_token_cannot_requeue_end_release_or_pass_the_ownership_check(
    chatbot_bot: Bot,
) -> None:
    """Worker mới còn sống (lease còn hạn): lệnh của worker cũ chỉ có `attempts` để bị chặn.

    Các test về worker cũ khác để worker mới xong trước, lúc đó điều kiện `status` đã chặn thay nên
    không chứng minh được rào chắn `attempts` của từng câu lệnh.
    """
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

    old = await claim(start)
    new = await claim(start + timedelta(seconds=241))  # lease của worker cũ hết hạn: tiếp quản
    assert (old.attempts, new.attempts) == (1, 2)
    later = start + timedelta(seconds=242)
    async with bot.session_factory() as session:
        inbox = BotInbox(session)
        assert not await inbox.requeue(
            update_id, 1, retry_at=later + timedelta(seconds=5), now=later
        )
        assert not await inbox.end(
            update_id, 1, status="failed", category="engine_error", now=later
        )
        assert not await inbox.release_lease(update_id, 1, now=later)
        assert not await inbox.owns(update_id, 1)
        assert await inbox.owns(update_id, 2)
        await session.commit()

    row = await bot.row(update_id)
    assert (row.status, row.attempts, row.payload_text) == ("processing", 2, "x")
    assert row.lease_until > start + timedelta(seconds=300)  # lease của worker mới còn nguyên


async def test_a_second_cancel_during_the_lease_release_still_releases_it(
    chatbot_bot: Bot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nhả lease chạy trong `shield`: một lần hủy nữa giữa lúc đang nhả không được cắt ngang."""
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)
    original_release = BotInbox.release_lease
    releasing = asyncio.Event()

    async def slow_release(self: BotInbox, *args: Any, **kwargs: Any) -> bool:
        releasing.set()
        await asyncio.sleep(0.3)
        return await original_release(self, *args, **kwargs)

    monkeypatch.setattr(BotInbox, "release_lease", slow_release)
    engine = GateEngine()
    worker = asyncio.create_task(bot.drain(tg, engine=engine))
    await asyncio.wait_for(engine.started.wait(), timeout=5)

    worker.cancel()
    await asyncio.wait_for(releasing.wait(), timeout=5)
    worker.cancel()  # lần hủy thứ hai, đúng lúc đang nhả
    with pytest.raises(asyncio.CancelledError):
        await worker
    # Nhả lease chạy tiếp trong `shield` sau khi worker đã bị hủy: chờ có thời hạn, không ngủ cứng.
    deadline = time.monotonic() + 5
    row = await bot.row(update_id)
    while row.lease_until > datetime.now(UTC) and time.monotonic() < deadline:
        await asyncio.sleep(0.05)
        row = await bot.row(update_id)

    assert row.status == "processing" and row.lease_until <= datetime.now(UTC)


async def test_a_stale_worker_that_fails_late_sends_no_apology_after_the_new_owner_answered(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)
    started, go = asyncio.Event(), asyncio.Event()

    class _LateFailingEngine:
        async def reply(self, turn: ChatTurn) -> ChatReply:
            started.set()
            await go.wait()
            raise ChatEngineError("cấu hình sai")

    old_worker = asyncio.create_task(bot.drain(tg, engine=_LateFailingEngine()))
    await asyncio.wait_for(started.wait(), timeout=5)
    await bot.set_lease(update_id, _past())  # bị tiếp quản
    await bot.drain(tg, engine=ScriptedEngine("của worker mới"))

    go.set()  # worker cũ thất bại muộn: dòng đã `replied`, không được xin lỗi người dùng
    await asyncio.wait_for(old_worker, timeout=5)

    assert bot.outbox.texts_to(tg) == ["của worker mới"]
    assert (await bot.row(update_id)).status == "replied"


# --- tin quá cũ -------------------------------------------------------------------------------


async def test_messages_older_than_the_ttl_are_dropped_with_a_single_notice_per_run(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    user_id, tg = await linked_user(bot)
    old = datetime.now(UTC) - timedelta(hours=2)
    first, second, fresh = next_update_id(), next_update_id(), next_update_id()
    await bot.insert_row(tg, user_id, first, text_="cũ 1", received_at=old)
    await bot.insert_row(tg, user_id, second, text_="cũ 2", received_at=old)
    await bot.insert_row(tg, user_id, fresh, text_="mới")
    engine = ScriptedEngine("trả lời tin mới")

    await bot.drain(tg, engine=engine)

    for update_id in (first, second):
        row = await bot.row(update_id)
        assert (row.status, row.error_category, row.payload_text) == ("dropped", "expired", None)
    assert (await bot.row(fresh)).status == "replied"
    assert bot.outbox.texts_to(tg) == [EXPIRED_MESSAGE_TEXT, "trả lời tin mới"]  # một thông báo
    assert engine.calls == 1  # không trả lời câu hỏi đã cũ
