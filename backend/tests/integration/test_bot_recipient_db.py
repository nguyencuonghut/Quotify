"""Ai còn được nhận tin của chatbot (kế hoạch 5.1, S4).

Liên kết bị hủy hay bị chặn, hoặc người dùng bị khóa, trong lúc tin còn chờ hay đang xử lý: dòng bị
loại (`dropped`) và không tốn lượt engine. Cả câu xin lỗi và thông báo tin quá cũ cũng phải qua kiểm
tra này, và 403 cho chúng cũng đánh dấu liên kết `blocked`.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from bot_fakes import GateEngine, RecordingClient, ScriptedEngine
from bot_harness import Bot, linked_user
from db_helpers import next_update_id
from sqlalchemy import text

from app.integrations.telegram import TelegramForbiddenError
from app.services.telegram_bot_messages import EXPIRED_MESSAGE_TEXT, LOST_MESSAGE_TEXT


async def _set_link_status(bot: Bot, telegram_user_id: int, status: str) -> None:
    async with bot.session_factory() as session:
        await session.execute(
            text("update telegram_accounts set status = :s where telegram_user_id = :t"),
            {"s": status, "t": telegram_user_id},
        )
        await session.commit()


async def _set_user_status(bot: Bot, user_id: uuid.UUID, status: str) -> None:
    async with bot.session_factory() as session:
        await session.execute(
            text("update users set status = :s where id = :u"),
            {"s": status, "u": user_id},
        )
        await session.commit()


def _past(seconds: float = 1) -> datetime:
    return datetime.now(UTC) - timedelta(seconds=seconds)


@pytest.mark.parametrize(
    ("link_status", "category"),
    [("revoked", "unlinked"), ("blocked", "forbidden")],
)
async def test_a_row_whose_link_is_gone_is_dropped_before_the_engine_runs(
    chatbot_bot: Bot,
    link_status: str,
    category: str,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)
    await _set_link_status(bot, tg, link_status)  # trong lúc tin còn chờ
    engine = ScriptedEngine("không được gọi")

    await bot.drain(tg, engine=engine)

    row = await bot.row(update_id)
    assert (row.status, row.error_category, row.payload_text) == ("dropped", category, None)
    assert engine.calls == 0  # không tốn lượt engine
    assert bot.outbox.texts_to(tg) == []


async def test_a_row_of_a_user_who_is_no_longer_active_is_dropped_before_the_engine_runs(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    user_id, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)
    await _set_user_status(bot, user_id, "locked")
    engine = ScriptedEngine("không được gọi")

    await bot.drain(tg, engine=engine)

    row = await bot.row(update_id)
    assert (row.status, row.error_category, row.payload_text) == ("dropped", "user_inactive", None)
    assert engine.calls == 0
    assert bot.outbox.texts_to(tg) == []


async def test_a_link_revoked_while_the_engine_runs_stops_the_reply_from_being_sent(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)
    engine = GateEngine("trả lời")
    worker = asyncio.create_task(bot.drain(tg, engine=engine))
    await asyncio.wait_for(engine.started.wait(), timeout=5)

    await _set_link_status(bot, tg, "revoked")  # người dùng gõ /stop giữa lúc engine chạy
    engine.release.set()
    await asyncio.wait_for(worker, timeout=5)

    row = await bot.row(update_id)
    assert (row.status, row.error_category, row.reply_text) == ("dropped", "unlinked", None)
    assert bot.outbox.texts_to(tg) == []  # kiểm lần cuối trước khi gửi


async def test_a_user_locked_while_the_engine_runs_stops_the_reply_from_being_sent(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    user_id, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)
    engine = GateEngine("trả lời")
    worker = asyncio.create_task(bot.drain(tg, engine=engine))
    await asyncio.wait_for(engine.started.wait(), timeout=5)

    await _set_user_status(bot, user_id, "inactive")
    engine.release.set()
    await asyncio.wait_for(worker, timeout=5)

    row = await bot.row(update_id)
    assert (row.status, row.error_category) == ("dropped", "user_inactive")
    assert bot.outbox.texts_to(tg) == []


# --- câu xin lỗi và thông báo tin quá cũ -------------------------------------------------------


async def _exhausted_row(bot: Bot, user_id: uuid.UUID, tg: int) -> int:
    update_id = next_update_id()
    await bot.insert_row(
        tg, user_id, update_id, status="processing", attempts=3, lease_until=_past()
    )
    return update_id


async def test_the_apology_is_not_sent_to_a_chat_that_is_no_longer_linked(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    user_id, tg = await linked_user(bot)
    update_id = await _exhausted_row(bot, user_id, tg)
    await _set_link_status(bot, tg, "revoked")
    client = RecordingClient()

    await bot.drain(tg, client=client)

    assert (await bot.row(update_id)).status == "failed"  # dòng vẫn kết thúc
    assert client.attempts == []  # nhưng không gửi gì cho chat đã hủy liên kết


async def test_a_blocked_bot_during_the_apology_marks_the_link_blocked(chatbot_bot: Bot) -> None:
    bot = chatbot_bot
    user_id, tg = await linked_user(bot)
    await _exhausted_row(bot, user_id, tg)
    client = RecordingClient(TelegramForbiddenError("Forbidden: bot was blocked", error_code=403))

    await bot.drain(tg, client=client)

    assert client.attempts == [(tg, LOST_MESSAGE_TEXT)]
    assert [account.status for account in await bot.accounts(user_id)] == ["blocked"]


async def test_the_too_old_notice_is_not_sent_to_a_chat_that_is_no_longer_linked(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    user_id, tg = await linked_user(bot)
    update_id = next_update_id()
    await bot.insert_row(tg, user_id, update_id, received_at=_past(7200))
    await _set_link_status(bot, tg, "revoked")
    client = RecordingClient()

    await bot.drain(tg, client=client)

    assert (await bot.row(update_id)).status == "dropped"
    assert client.attempts == []


async def test_the_apology_and_the_too_old_notice_still_reach_a_linked_chat(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    user_id, tg = await linked_user(bot)
    await _exhausted_row(bot, user_id, tg)
    client = RecordingClient()

    await bot.drain(tg, client=client)

    assert client.sent == [(tg, LOST_MESSAGE_TEXT)]
    expired = next_update_id()
    await bot.insert_row(tg, user_id, expired, received_at=_past(7200))
    await bot.drain(tg, client=client)
    assert client.sent[-1] == (tg, EXPIRED_MESSAGE_TEXT)
