"""Đường ống chatbot (kế hoạch 5.1, S1): tin văn bản -> hộp thư -> worker bot -> trả lời.

Dựng trên PostgreSQL thật: runner thật, client Telegram qua `httpx.MockTransport`, bên đánh chuông
giả (ranh giới Redis/arq) và engine giả hoặc `StubChatEngine` (ranh giới LLM).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from bot_harness import Bot, linked_user
from db_helpers import create_user, ensure_role, issue_token, next_telegram_id, next_update_id
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from telegram_fakes import make_update

from app.bot_worker import BotWorkerConfig
from app.services.bot_inbox import BotInboxError
from app.services.bot_policy import ChatbotPolicy
from app.services.chat_engine import ChatReply, ChatTurn
from app.services.telegram_bot_messages import (
    HELP_TEXT,
    INVALID_CARD_TEXT,
    STOPPED_TEXT,
    STUB_REPLY_TEXT,
    SYSTEM_ERROR_TEXT,
    UNKNOWN_TEXT,
    USER_INACTIVE_TEXT,
)
from app.services.telegram_update_runner import TelegramTemporaryError


async def test_a_linked_users_text_is_queued_then_answered_by_the_worker(chatbot_bot: Bot) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)

    update_id = await bot.send("xin chào", tg=tg)

    rows = await bot.inbox_rows(tg)
    assert [(r.update_id, r.status, r.payload_text) for r in rows] == [
        (update_id, "queued", "xin chào"),
    ]
    assert bot.dispatcher.notified == [(tg, update_id)]
    assert bot.outbox.texts_to(tg) == []  # webhook không trả lời: việc của worker

    handled = await bot.drain(tg)

    assert handled == 1
    assert bot.outbox.texts_to(tg) == [STUB_REPLY_TEXT]
    (row,) = await bot.inbox_rows(tg)
    assert (row.status, row.payload_text, row.reply_text) == ("replied", None, None)


# --- hành vi không đổi khi chatbot tắt hoặc người dùng ngoài danh sách thử -----------------------


async def test_with_the_chatbot_off_plain_text_keeps_the_old_answer_and_writes_no_row(
    bot: Bot,
) -> None:
    _, tg = await linked_user(bot)

    await bot.send("xin chào", tg=tg)

    assert bot.outbox.texts_to(tg) == [UNKNOWN_TEXT]
    assert await bot.inbox_rows(tg) == []


async def test_a_user_outside_the_pilot_list_is_treated_as_if_the_chatbot_were_off(
    chatbot_bot_factory: Callable[..., Bot],
) -> None:
    bot = chatbot_bot_factory(ChatbotPolicy(enabled=True, pilot_emails=frozenset({"khac@x.vn"})))
    _, tg = await linked_user(bot)

    await bot.send("xin chào", tg=tg)

    assert bot.outbox.texts_to(tg) == [UNKNOWN_TEXT]
    assert await bot.inbox_rows(tg) == []
    assert bot.dispatcher.notified == []


async def test_a_pilot_user_is_handed_off_whatever_the_case_of_the_email(
    chatbot_bot_factory: Callable[..., Bot],
) -> None:
    bot = chatbot_bot_factory(
        ChatbotPolicy(enabled=True, pilot_emails=frozenset({"thu.nghiem@honghafeed.vn"})),
    )
    user_id = await create_user(bot.session_factory, email="Thu.Nghiem@HongHaFeed.vn")
    tg = next_telegram_id()
    await bot.send(f"/start {await issue_token(bot.session_factory, user_id)}", tg=tg)

    update_id = await bot.send("xin chào", tg=tg)

    assert [r.update_id for r in await bot.inbox_rows(tg)] == [update_id]


async def test_commands_and_buttons_keep_their_inline_answers_when_the_chatbot_is_on(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)

    await bot.send("/help", tg=tg)
    await bot.send("/dieu_khong_co", tg=tg)
    await bot.process_raw(
        {
            "update_id": next_update_id(),
            "callback_query": {
                "id": "cb1",
                "from": {"id": tg, "is_bot": False, "first_name": "Q"},
                "message": {"message_id": 7, "chat": {"id": tg, "type": "private"}},
                "data": "khong-phai-nut-duyet-gia",
            },
        },
    )

    assert bot.outbox.texts_to(tg) == [HELP_TEXT, UNKNOWN_TEXT]
    assert [a["text"] for a in bot.outbox.callback_answers()] == [INVALID_CARD_TEXT]
    assert await bot.inbox_rows(tg) == []
    assert bot.dispatcher.notified == []


async def test_stopping_the_link_still_works_when_the_chatbot_is_on(chatbot_bot: Bot) -> None:
    bot = chatbot_bot
    user_id, tg = await linked_user(bot)

    await bot.send("/stop", tg=tg)

    assert bot.outbox.texts_to(tg) == [STOPPED_TEXT]
    assert [a.status for a in await bot.accounts(user_id)] == ["revoked"]
    assert await bot.inbox_rows(tg) == []


# --- webhook không chờ engine, lỗi hạ tầng ----------------------------------------------------


class _CountingEngine:
    def __init__(self) -> None:
        self.turns: list[ChatTurn] = []

    async def reply(self, turn: ChatTurn) -> ChatReply:
        self.turns.append(turn)
        return ChatReply("ok")


class _BlockingEngine:
    """Engine giả bị kẹt cho đến khi được mở: mô phỏng một cuộc gọi LLM chậm."""

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def reply(self, turn: ChatTurn) -> ChatReply:
        self.started.set()
        await self.release.wait()
        return ChatReply("ok")


async def test_the_webhook_keeps_answering_while_the_engine_is_busy(chatbot_bot: Bot) -> None:
    bot = chatbot_bot
    _, busy_tg = await linked_user(bot)
    _, other_tg = await linked_user(bot)
    engine = _BlockingEngine()
    await bot.send("câu hỏi chậm", tg=busy_tg)
    worker = asyncio.create_task(bot.drain(busy_tg, engine=engine))
    await asyncio.wait_for(engine.started.wait(), timeout=5)  # worker đang kẹt trong engine

    # Webhook không bị chặn: tin của người khác vào hộp thư và lệnh của chính người đang chờ
    # vẫn được trả lời ngay (nếu engine chạy trong request thì hai lời gọi này sẽ treo).
    queued_id = await asyncio.wait_for(bot.send("tin khác", tg=other_tg), timeout=2)
    await asyncio.wait_for(bot.send("/help", tg=busy_tg), timeout=2)

    assert [r.update_id for r in await bot.inbox_rows(other_tg)] == [queued_id]
    assert bot.outbox.texts_to(busy_tg) == [HELP_TEXT]
    engine.release.set()
    assert await worker == 1


class _RaisingDispatcher:
    async def notify(self, chat_id: int, update_id: int) -> None:
        raise ConnectionError("redis down")

    async def aclose(self) -> None:
        return None


async def test_a_failing_bell_does_not_fail_the_update_and_the_row_stays_queued(
    chatbot_bot_factory: Callable[..., Bot],
) -> None:
    bot = chatbot_bot_factory(ChatbotPolicy(enabled=True), dispatcher=_RaisingDispatcher())
    _, tg = await linked_user(bot)

    update_id = await bot.send("xin chào", tg=tg)  # không ném

    assert [(r.update_id, r.status) for r in await bot.inbox_rows(tg)] == [(update_id, "queued")]


class _CommitFails(AsyncSession):
    async def commit(self) -> None:
        raise OperationalError("COMMIT", {}, Exception("db down"))


async def test_a_database_failure_asks_telegram_to_retry_and_leaves_no_row_behind(
    chatbot_bot_factory: Callable[..., Bot],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    healthy = chatbot_bot_factory(ChatbotPolicy(enabled=True))
    _, tg = await linked_user(healthy)
    failing = chatbot_bot_factory(
        ChatbotPolicy(enabled=True),
        session_factory_for_runner=async_sessionmaker(
            bind=session_factory.kw["bind"],
            expire_on_commit=False,
            class_=_CommitFails,
        ),
    )
    update_id = next_update_id()

    with pytest.raises(TelegramTemporaryError):
        await failing.process_raw(make_update(update_id, "xin chào", user_id=tg))

    assert await healthy.inbox_rows(tg) == []
    async with session_factory() as session:
        remembered = await session.scalar(
            text("select count(*) from telegram_processed_updates where update_id = :i"),
            {"i": update_id},
        )
    assert remembered == 0  # Telegram gửi lại thì update vẫn được xử lý
    assert failing.dispatcher.notified == []


# --- người dùng và quyền ----------------------------------------------------------------------


class _PermissionProbe:
    """Engine giả ghi lại việc `principal` có quyền kiểm tra hay không ở mỗi tin."""

    def __init__(self, permission: str) -> None:
        self._permission = permission
        self.allowed: list[bool] = []

    async def reply(self, turn: ChatTurn) -> ChatReply:
        self.allowed.append(turn.principal.can(self._permission))
        return ChatReply("ok")


async def test_permissions_are_loaded_fresh_for_every_message(chatbot_bot: Bot) -> None:
    bot = chatbot_bot
    permission = "price_alerts.receive_all"  # quyền có sẵn từ migration
    await ensure_role(bot.session_factory, "bot-probe-role", [permission])
    user_id = await create_user(bot.session_factory, role_names=("bot-probe-role",))
    tg = next_telegram_id()
    await bot.send(f"/start {await issue_token(bot.session_factory, user_id)}", tg=tg)
    probe = _PermissionProbe(permission)

    await bot.send("tin thứ nhất", tg=tg)
    await bot.drain(tg, engine=probe)
    async with bot.session_factory() as session:
        await session.execute(text("delete from user_roles where user_id = :u"), {"u": user_id})
        await session.commit()
    await bot.send("tin thứ hai", tg=tg)
    await bot.drain(tg, engine=probe)

    assert probe.allowed == [True, False]


# --- dữ liệu và thứ tự ----------------------------------------------------------------------


async def test_reply_saved_at_is_set_when_the_engines_reply_is_saved(chatbot_bot: Bot) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    await bot.send("xin chào", tg=tg)

    before = datetime.now(UTC)
    await bot.drain(tg)
    after = datetime.now(UTC)

    (row,) = await bot.inbox_rows(tg)
    assert row.reply_saved_at is not None
    assert before <= row.reply_saved_at <= after


async def test_messages_of_one_chat_are_answered_in_order_by_one_run(chatbot_bot: Bot) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    engine = _CountingEngine()
    await bot.send("một", tg=tg)
    await bot.send("hai", tg=tg)

    handled = await bot.drain(tg, engine=engine)

    assert handled == 2
    assert [t.text for t in engine.turns] == ["một", "hai"]
    assert [r.status for r in await bot.inbox_rows(tg)] == ["replied", "replied"]


# --- chatbot tắt giữa chừng, rò nội dung, các nhánh âm tính -----------------------------------


async def test_a_worker_with_the_chatbot_switched_off_leaves_queued_rows_alone(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)

    handled = await bot.drain(tg, config=BotWorkerConfig(enabled=False))

    assert handled == 0
    assert bot.outbox.texts_to(tg) == []
    assert [(r.update_id, r.status) for r in await bot.inbox_rows(tg)] == [(update_id, "queued")]


DECOY = "MAT-KHAU-1234567890"


async def test_message_text_never_reaches_the_logs_when_the_inbox_write_fails(
    chatbot_bot: Bot,
    caplog: pytest.LogCaptureFixture,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    caplog.set_level(logging.DEBUG)

    # Postgres không lưu được ký tự NUL trong văn bản: lệnh INSERT hộp thư thất bại.
    await bot.send(f"{DECOY}\x00", tg=tg)

    assert DECOY not in caplog.text  # SQLAlchemy mặc định in cả tham số của câu lệnh lỗi
    assert await bot.inbox_rows(tg) == []
    assert bot.outbox.texts_to(tg) == [SYSTEM_ERROR_TEXT]


class _FixedReplyEngine:
    def __init__(self, text_: str) -> None:
        self._text = text_

    async def reply(self, turn: ChatTurn) -> ChatReply:
        return ChatReply(self._text)


async def test_reply_text_never_reaches_the_error_when_saving_it_fails(
    chatbot_bot: Bot,
    caplog: pytest.LogCaptureFixture,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    await bot.send("xin chào", tg=tg)
    caplog.set_level(logging.DEBUG)

    with pytest.raises(BotInboxError) as raised:
        await bot.drain(tg, engine=_FixedReplyEngine(f"{DECOY}\x00"))

    assert DECOY not in str(raised.value)
    assert DECOY not in caplog.text


async def test_a_message_from_an_unlinked_telegram_account_is_not_handed_off(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    tg = next_telegram_id()

    await bot.send("xin chào", tg=tg)

    assert bot.outbox.texts_to(tg) == [UNKNOWN_TEXT]
    assert await bot.inbox_rows(tg) == []


async def test_a_message_from_a_deactivated_user_is_not_handed_off(chatbot_bot: Bot) -> None:
    bot = chatbot_bot
    user_id, tg = await linked_user(bot)
    async with bot.session_factory() as session:
        await session.execute(
            text("update users set status = 'inactive' where id = :u"),
            {"u": user_id},
        )
        await session.commit()

    await bot.send("xin chào", tg=tg)

    assert bot.outbox.texts_to(tg) == [USER_INACTIVE_TEXT]
    assert await bot.inbox_rows(tg) == []


async def test_a_replayed_update_is_queued_and_bell_rung_only_once(chatbot_bot: Bot) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = next_update_id()
    payload = make_update(update_id, "xin chào", user_id=tg)

    await bot.process_raw(payload)
    await bot.process_raw(payload)  # Telegram gửi lại cùng update

    assert [r.update_id for r in await bot.inbox_rows(tg)] == [update_id]
    assert bot.dispatcher.notified == [(tg, update_id)]


async def test_blocking_the_bot_still_marks_the_link_blocked_when_the_chatbot_is_on(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    user_id, tg = await linked_user(bot)

    await bot.process_raw(
        {
            "update_id": next_update_id(),
            "my_chat_member": {
                "chat": {"id": tg, "type": "private"},
                "from": {"id": tg, "is_bot": False, "first_name": "Q"},
                "new_chat_member": {"status": "kicked"},
            },
        },
    )

    assert [a.status for a in await bot.accounts(user_id)] == ["blocked"]
