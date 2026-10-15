"""Hạn mức sử dụng mỗi người mỗi ngày của chatbot (kế hoạch 5.1, S10).

Cổng đếm lượt từ chính hộp thư `bot_updates` (dòng đã lưu câu trả lời trong ngày nghiệp vụ theo giờ
Việt Nam) và chặn ở worker, ngay trước khi gọi engine.
"""

from __future__ import annotations

import dataclasses
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from bot_fakes import RecordingClient, ScriptedEngine
from bot_harness import Bot, linked_user
from db_helpers import create_user, next_update_id
from quota_helpers import gate, insert_turn, scratch_session, tomorrow_text, use_turns
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import bot_worker
from app.bot_worker import BotWorkerConfig
from app.core.bot_metrics import BotMetrics
from app.services.bot_inbox import BotInbox, ClaimResult
from app.services.chat_engine import ChatEngineError
from app.services.usage_gate import QuotaLimits, TurnLimitGate

VN = ZoneInfo("Asia/Ho_Chi_Minh")


async def test_the_twenty_first_message_of_the_day_is_refused_without_calling_the_engine(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    user_id, tg = await linked_user(bot)
    await use_turns(bot, user_id, tg, 20)
    update_id = await bot.send("câu hỏi thứ 21", tg=tg)
    engine = ScriptedEngine("không được gọi")
    before = tomorrow_text()

    await bot.drain(tg, engine=engine, usage_gate=gate())

    row = await bot.row(update_id)
    assert (row.status, row.error_category, row.payload_text) == ("dropped", "quota_exceeded", None)
    assert engine.calls == 0
    [refusal] = bot.outbox.texts_to(tg)  # đúng một câu, không gọi LLM
    assert "20/20" in refusal
    # Tính cả trước và sau: nếu nửa đêm giờ Việt Nam đi qua giữa chừng thì ngày làm mới nhảy ngày.
    assert before in refusal or tomorrow_text() in refusal


async def _turns_used(bot: Bot, user_id: uuid.UUID) -> int:
    async with bot.session_factory() as session:
        summary = await gate().summary(session, user_id, now=datetime.now(UTC))
    return summary.turns_used


async def test_the_twentieth_message_is_still_answered(chatbot_bot: Bot) -> None:
    bot = chatbot_bot
    user_id, tg = await linked_user(bot)
    await use_turns(bot, user_id, tg, 19)
    update_id = await bot.send("lượt thứ 20", tg=tg)
    engine = ScriptedEngine("trả lời lượt 20")

    await bot.drain(tg, engine=engine, usage_gate=gate())

    assert (await bot.row(update_id)).status == "replied"
    assert engine.calls == 1
    # Lượt cuối của ngày: câu trả lời kèm lời báo đã hết lượt.
    assert bot.outbox.texts_to(tg) == ["trả lời lượt 20\n\nBạn đã dùng hết 20/20 lượt hôm nay."]
    assert await _turns_used(bot, user_id) == 20  # lượt vừa trả lời đã được tính


async def test_two_messages_sent_back_to_back_with_one_turn_left_get_exactly_one_answer(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    user_id, tg = await linked_user(bot)
    await use_turns(bot, user_id, tg, 19)
    first = await bot.send("câu thứ nhất", tg=tg)
    second = await bot.send("câu thứ hai", tg=tg)
    engine = ScriptedEngine("đã trả lời")

    await bot.drain(tg, engine=engine, usage_gate=gate())

    assert (await bot.row(first)).status == "replied"
    assert (await bot.row(second)).error_category == "quota_exceeded"
    assert engine.calls == 1  # tuần tự: dòng thứ hai thấy lượt thứ nhất đã được tính
    texts = bot.outbox.texts_to(tg)
    assert texts[0] == "đã trả lời\n\nBạn đã dùng hết 20/20 lượt hôm nay."
    assert "20/20" in texts[1] and len(texts) == 2


async def test_several_refused_messages_in_one_run_get_a_single_refusal(chatbot_bot: Bot) -> None:
    bot = chatbot_bot
    user_id, tg = await linked_user(bot)
    await use_turns(bot, user_id, tg, 20)
    updates = [await bot.send(f"câu {n}", tg=tg) for n in range(3)]

    await bot.drain(tg, engine=ScriptedEngine("không gọi"), usage_gate=gate())

    assert [(await bot.row(u)).error_category for u in updates] == ["quota_exceeded"] * 3
    assert len(bot.outbox.texts_to(tg)) == 1  # một câu cho cả đợt, không gửi ba lần


async def test_a_failed_engine_turn_does_not_use_up_a_turn(chatbot_bot: Bot) -> None:
    bot = chatbot_bot
    user_id, tg = await linked_user(bot)
    await use_turns(bot, user_id, tg, 19)
    failed = await bot.send("engine sẽ lỗi", tg=tg)
    await bot.drain(tg, engine=ScriptedEngine(ChatEngineError("lỗi cấu hình")), usage_gate=gate())
    assert (await bot.row(failed)).status == "failed"
    bot.outbox.requests.clear()

    again = await bot.send("hỏi lại", tg=tg)
    await bot.drain(tg, engine=ScriptedEngine("được trả lời"), usage_gate=gate())

    assert (await bot.row(again)).status == "replied"  # lượt lỗi không bị tính
    assert bot.outbox.texts_to(tg) == ["được trả lời\n\nBạn đã dùng hết 20/20 lượt hôm nay."]


@pytest.mark.parametrize("why", ["expired", "unlinked", "user_inactive"])
async def test_rows_dropped_before_the_engine_do_not_count_as_turns(
    chatbot_bot: Bot, why: str
) -> None:
    bot = chatbot_bot
    user_id, tg = await linked_user(bot)
    await use_turns(bot, user_id, tg, 19)
    queued = next_update_id()
    old = datetime.now(UTC) - timedelta(hours=2)
    await bot.insert_row(tg, user_id, queued, received_at=old if why == "expired" else None)
    async with bot.session_factory() as session:
        if why == "unlinked":
            await session.execute(
                text("update telegram_accounts set status = 'revoked' where telegram_user_id = :t"),
                {"t": tg},
            )
        if why == "user_inactive":
            await session.execute(
                text("update users set status = 'locked' where id = :u"), {"u": user_id}
            )
        await session.commit()
    engine = ScriptedEngine("không gọi")

    await bot.drain(tg, engine=engine, usage_gate=gate())

    row = await bot.row(queued)
    assert (row.status, row.error_category) == ("dropped", why)
    assert engine.calls == 0
    assert await _turns_used(bot, user_id) == 19  # lượt bị loại không bị tính


async def test_a_reply_that_was_saved_but_could_not_be_sent_still_counts(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    user_id, tg = await linked_user(bot)
    await bot.send("câu hỏi", tg=tg)
    client = RecordingClient(always_fail=True)  # Telegram không nhận được tin nào

    await bot.drain(
        tg,
        engine=ScriptedEngine("đã trả lời"),
        client=client,
        usage_gate=gate(),
        config=BotWorkerConfig(max_attempts=1, send_budget_seconds=5),
    )

    # Chi phí đã phát sinh ngay khi engine trả lời, dù gửi lỗi (mục 4.11, điểm 3).
    assert await _turns_used(bot, user_id) == 1


async def test_a_row_that_already_has_its_reply_is_resent_without_the_gate_or_a_new_turn(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    user_id, tg = await linked_user(bot)
    await use_turns(bot, user_id, tg, 19)
    resend = next_update_id()
    now = datetime.now(UTC)
    await bot.insert_row(
        tg,
        user_id,
        resend,
        status="processing",
        attempts=1,
        lease_until=now.replace(year=2020),
        reply_text="câu trả lời đã lưu",
        reply_saved_at=now,
    )
    # Người dùng đã dùng đủ 20 lượt (kể cả dòng này) nên một tin mới sẽ bị chặn, nhưng dòng gửi lại
    # thì không.
    engine = ScriptedEngine("không gọi")

    await bot.drain(tg, engine=engine, usage_gate=gate())

    assert (await bot.row(resend)).status == "replied"
    assert engine.calls == 0 and bot.outbox.texts_to(tg) == ["câu trả lời đã lưu"]
    assert await _turns_used(bot, user_id) == 20  # không tính thêm


@pytest.mark.parametrize("role", ["admin", "manager"])
async def test_nobody_is_exempt_by_role(chatbot_bot: Bot, role: str) -> None:
    from bot_harness import FULL_NAME
    from db_helpers import create_user, ensure_role, issue_token, next_telegram_id

    bot = chatbot_bot
    await ensure_role(bot.session_factory, role)
    user_id = await create_user(bot.session_factory, full_name=FULL_NAME, role_names=[role])
    tg = next_telegram_id()
    await bot.send(f"/start {await issue_token(bot.session_factory, user_id)}", tg=tg)
    bot.outbox.requests.clear()
    await use_turns(bot, user_id, tg, 20)
    update_id = await bot.send("tôi là quản trị viên", tg=tg)
    engine = ScriptedEngine("không gọi")

    await bot.drain(tg, engine=engine, usage_gate=gate())

    assert (
        await bot.row(update_id)
    ).error_category == "quota_exceeded"  # cùng hạn mức như mọi người
    assert engine.calls == 0


def _units(text_: str) -> int:
    return len(text_.encode("utf-16-le")) // 2


async def test_the_reply_gets_a_reminder_when_the_allowance_runs_low(chatbot_bot: Bot) -> None:
    bot = chatbot_bot
    user_id, tg = await linked_user(bot)
    await use_turns(bot, user_id, tg, 15)  # lượt này là lượt 16: còn 4/20 = đúng ngưỡng 20%
    await bot.send("hỏi gì đó", tg=tg)

    await bot.drain(tg, engine=ScriptedEngine("đây là câu trả lời"), usage_gate=gate())

    assert bot.outbox.texts_to(tg) == ["đây là câu trả lời\n\nCòn 4/20 lượt hôm nay."]


async def test_no_reminder_while_there_is_plenty_left(chatbot_bot: Bot) -> None:
    bot = chatbot_bot
    user_id, tg = await linked_user(bot)
    await use_turns(bot, user_id, tg, 14)  # lượt này là lượt 15: còn 5/20 = 25%
    await bot.send("hỏi gì đó", tg=tg)

    await bot.drain(tg, engine=ScriptedEngine("đây là câu trả lời"), usage_gate=gate())

    assert bot.outbox.texts_to(tg) == ["đây là câu trả lời"]


async def test_the_reminder_can_be_switched_off(chatbot_bot: Bot) -> None:
    bot = chatbot_bot
    user_id, tg = await linked_user(bot)
    await use_turns(bot, user_id, tg, 18)
    await bot.send("hỏi gì đó", tg=tg)

    await bot.drain(
        tg,
        engine=ScriptedEngine("câu trả lời"),
        usage_gate=gate(),
        config=BotWorkerConfig(quota_warn_remaining_percent=0),
    )

    assert bot.outbox.texts_to(tg) == ["câu trả lời"]


async def test_the_reminder_survives_a_reply_so_long_that_it_fills_every_part(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    user_id, tg = await linked_user(bot)
    await use_turns(bot, user_id, tg, 18)
    await bot.send("cho tôi một bản báo cáo dài", tg=tg)
    very_long = "\n\n".join(f"đoạn {n} " + "x" * 3000 for n in range(10))  # hơn 4 phần

    await bot.drain(tg, engine=ScriptedEngine(very_long), usage_gate=gate())

    texts = bot.outbox.texts_to(tg)
    assert len(texts) == 4 and all(_units(part) <= 4096 for part in texts)  # đủ 4 phần, không hơn
    assert texts[-1].endswith("Còn 1/20 lượt hôm nay.")  # nhắc không bị cắt cùng phần dư


async def test_a_resend_after_a_failure_carries_the_same_single_reminder(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    user_id, tg = await linked_user(bot)
    await use_turns(bot, user_id, tg, 17)
    await bot.send("hỏi gì đó", tg=tg)
    client = RecordingClient(fail_first=1)  # lần gửi đầu lỗi mạng, lần sau được

    await bot.drain(
        tg,
        engine=ScriptedEngine("câu trả lời"),
        client=client,
        usage_gate=gate(),
        config=BotWorkerConfig(retry_backoff_seconds=0.0),
    )

    expected = "câu trả lời\n\nCòn 2/20 lượt hôm nay."
    assert client.attempts == [(tg, expected), (tg, expected)]  # cùng một câu, không nhắc hai lần
    assert client.sent == [(tg, expected)]


# --- cổng đếm trực tiếp trên Postgres (mọi thứ nằm trong một giao dịch rồi hoàn tác) ---------


@pytest.mark.parametrize("db_zone", ["UTC", "Asia/Ho_Chi_Minh", "America/Los_Angeles"])
async def test_the_day_boundary_is_midnight_in_vietnam_whatever_the_database_zone(
    chatbot_bot: Bot, db_zone: str
) -> None:
    user_id = await create_user(chatbot_bot.session_factory)
    async with scratch_session(chatbot_bot, db_zone=db_zone) as session:
        # A: trả lời trước nửa đêm. B: nhận 23:59:50, trả lời 00:00:30 hôm sau. C: sau nửa đêm.
        await insert_turn(
            session,
            user_id,
            datetime(2026, 10, 14, 23, 59, 0, tzinfo=VN),
            saved_at=datetime(2026, 10, 14, 23, 59, 20, tzinfo=VN),
        )
        await insert_turn(
            session,
            user_id,
            datetime(2026, 10, 14, 23, 59, 50, tzinfo=VN),
            saved_at=datetime(2026, 10, 15, 0, 0, 30, tzinfo=VN),
        )
        await insert_turn(session, user_id, datetime(2026, 10, 15, 0, 1, 0, tzinfo=VN))
        before_midnight = await gate().summary(
            session, user_id, now=datetime(2026, 10, 14, 23, 59, 30, tzinfo=VN)
        )
        after_midnight = await gate().summary(
            session, user_id, now=datetime(2026, 10, 15, 0, 30, 0, tzinfo=VN)
        )

    assert before_midnight.turns_used == 1  # chỉ A
    # Lượt tính vào ngày engine trả lời (chi phí phát sinh lúc đó), khớp với ngày cổng xét.
    assert after_midnight.turns_used == 2  # B và C
    assert after_midnight.resets_at == datetime(2026, 10, 16, 0, 0, tzinfo=VN)


async def test_an_answer_saved_at_exactly_midnight_belongs_to_the_new_day(
    chatbot_bot: Bot,
) -> None:
    user_id = await create_user(chatbot_bot.session_factory)
    midnight = datetime(2026, 10, 15, 0, 0, 0, tzinfo=VN)
    async with scratch_session(chatbot_bot) as session:
        await insert_turn(session, user_id, midnight - timedelta(microseconds=1))
        await insert_turn(session, user_id, midnight)
        old_day = await gate().summary(session, user_id, now=midnight - timedelta(seconds=1))
        new_day = await gate().summary(session, user_id, now=midnight)

    assert (old_day.turns_used, new_day.turns_used) == (1, 1)


class _Frozen(datetime):
    """Đồng hồ của worker đứng yên ở một thời điểm (chỉ trong `app.bot_worker`)."""

    now_value: datetime = datetime(2026, 10, 15, 0, 0, 30, tzinfo=VN)

    @classmethod
    def now(cls, tz: Any = None) -> datetime:
        return cls.now_value.astimezone(tz) if tz is not None else cls.now_value


async def test_a_message_received_before_midnight_but_answered_after_it_is_charged_to_the_new_day(
    chatbot_bot: Bot, monkeypatch: pytest.MonkeyPatch
) -> None:
    bot = chatbot_bot
    user_id, tg = await linked_user(bot)
    evening = datetime(2026, 10, 14, 23, 58, 0, tzinfo=VN)
    await use_turns(bot, user_id, tg, 20, received_at=evening)  # ngày 14 đã dùng hết
    backlog = next_update_id()
    await bot.insert_row(
        tg, user_id, backlog, received_at=datetime(2026, 10, 14, 23, 59, 30, tzinfo=VN)
    )
    monkeypatch.setattr(bot_worker, "datetime", _Frozen)  # worker xử lý lúc 00:00:30 ngày 15
    engine = ScriptedEngine("đã trả lời")

    await bot.drain(tg, engine=engine, usage_gate=gate())

    assert (await bot.row(backlog)).status == "replied"  # ngày mới còn lượt
    assert engine.calls == 1
    async with bot.session_factory() as session:
        old_day = await gate().summary(
            session, user_id, now=datetime(2026, 10, 14, 23, 59, 59, tzinfo=VN)
        )
        new_day = await gate().summary(
            session, user_id, now=datetime(2026, 10, 15, 0, 1, 0, tzinfo=VN)
        )
    # Không có lượt "miễn phí" ở biên ngày: lượt được xét và được tính cùng một ngày.
    assert (old_day.turns_used, new_day.turns_used) == (20, 1)


async def test_the_file_allowance_is_separate_from_the_turn_allowance(chatbot_bot: Bot) -> None:
    user_id = await create_user(chatbot_bot.session_factory)
    now = datetime(2026, 10, 14, 10, 0, 0, tzinfo=VN)
    async with scratch_session(chatbot_bot) as session:
        for n in range(3):
            await insert_turn(session, user_id, now - timedelta(minutes=n), kind="text")
        for n in range(5):
            await insert_turn(session, user_id, now - timedelta(minutes=10 + n), kind="photo")

        text_turn = await gate().check(session, user_id, "text", now=now)
        photo_turn = await gate().check(session, user_id, "photo", now=now)
        pdf_turn = await gate().check(session, user_id, "document", now=now)

    assert text_turn.allowed  # còn lượt chữ (8/20) dù hết lượt file
    assert not photo_turn.allowed and photo_turn.reason == "files"
    assert (photo_turn.used, photo_turn.limit) == (5, 5)
    assert not pdf_turn.allowed and pdf_turn.reason == "files"
    assert photo_turn.turns_used == 8  # lượt file cũng là lượt hỏi
    assert (text_turn.files_used, text_turn.files_limit) == (5, 5)  # dòng nhắc dựa vào các số này


async def test_the_turn_allowance_wins_when_both_are_used_up(chatbot_bot: Bot) -> None:
    user_id = await create_user(chatbot_bot.session_factory)
    now = datetime(2026, 10, 14, 10, 0, 0, tzinfo=VN)
    async with scratch_session(chatbot_bot) as session:
        for n in range(5):
            await insert_turn(session, user_id, now - timedelta(minutes=n), kind="photo")

        decision = await gate(turns=5, files=5).check(session, user_id, "photo", now=now)

    assert decision.reason == "turns"  # lượt hỏi là hạn mức chung nên được nói trước


async def test_zero_means_no_limit_for_that_kind_only(chatbot_bot: Bot) -> None:
    user_id = await create_user(chatbot_bot.session_factory)
    now = datetime(2026, 10, 14, 10, 0, 0, tzinfo=VN)
    async with scratch_session(chatbot_bot) as session:
        for n in range(30):
            await insert_turn(session, user_id, now - timedelta(minutes=n), kind="photo")

        no_limits = await gate(turns=0, files=0).check(session, user_id, "photo", now=now)
        files_only = await gate(turns=0, files=5).check(session, user_id, "photo", now=now)
        text_only = await gate(turns=0, files=5).check(session, user_id, "text", now=now)

    assert no_limits.allowed  # 30 lượt, không giới hạn gì cả
    assert not files_only.allowed and files_only.reason == "files"
    assert text_only.allowed  # lượt chữ không giới hạn dù lượt file có


async def test_two_users_are_counted_separately(chatbot_bot: Bot) -> None:
    busy = await create_user(chatbot_bot.session_factory)
    quiet = await create_user(chatbot_bot.session_factory)
    now = datetime(2026, 10, 14, 10, 0, 0, tzinfo=VN)
    async with scratch_session(chatbot_bot) as session:
        for n in range(20):
            await insert_turn(session, busy, now - timedelta(minutes=n))

        busy_decision = await gate().check(session, busy, "text", now=now)
        quiet_decision = await gate().check(session, quiet, "text", now=now)

    assert not busy_decision.allowed and quiet_decision.allowed
    assert quiet_decision.turns_used == 0


async def test_a_limit_source_can_give_one_person_a_different_allowance(
    chatbot_bot: Bot,
) -> None:
    # Điểm nối cho 5.6: ghi đè theo từng người do Admin cấu hình, không đổi cổng.
    manager = await create_user(chatbot_bot.session_factory)
    staff = await create_user(chatbot_bot.session_factory)

    class PerPerson:
        async def limits_for(self, session: AsyncSession, user_id: uuid.UUID) -> QuotaLimits:
            return QuotaLimits(turns=50, files=10) if user_id == manager else QuotaLimits(20, 5)

    gate = TurnLimitGate(PerPerson())
    now = datetime(2026, 10, 14, 10, 0, 0, tzinfo=VN)
    async with scratch_session(chatbot_bot) as session:
        for user in (manager, staff):
            for n in range(25):
                await insert_turn(session, user, now - timedelta(minutes=n))

        manager_decision = await gate.check(session, manager, "text", now=now)
        staff_decision = await gate.check(session, staff, "text", now=now)

    assert manager_decision.allowed and manager_decision.turns_limit == 50
    assert not staff_decision.allowed and staff_decision.turns_limit == 20


async def test_the_scratch_ddl_never_leaks_into_the_shared_database(chatbot_bot: Bot) -> None:
    async with scratch_session(chatbot_bot):  # bỏ ràng buộc loại tin rồi hoàn tác khi thoát
        pass

    async with chatbot_bot.session_factory() as session:
        found = (
            await session.execute(
                text("select 1 from pg_constraint where conname = 'ck_bot_updates_kind'")
            )
        ).scalar_one_or_none()

    assert found == 1  # tự chứa: không phụ thuộc thứ tự chạy của các test khác


async def _denied_gauge(bot: Bot) -> int:
    metrics = BotMetrics(bot.session_factory, ttl_seconds=0, chatbot_enabled=lambda: True)
    await metrics.refresh(datetime.now(UTC))
    assert metrics.snapshot is not None and metrics.snapshot.quota_denied is not None
    return metrics.snapshot.quota_denied


async def test_a_refusal_by_the_worker_is_what_the_quota_denied_gauge_counts(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    user_id, tg = await linked_user(bot)
    await use_turns(bot, user_id, tg, 20)
    await bot.send("hỏi nữa", tg=tg)
    before = await _denied_gauge(bot)  # DB tích hợp dùng chung: so sánh chênh lệch

    await bot.drain(tg, engine=ScriptedEngine("không gọi"), usage_gate=gate())

    assert await _denied_gauge(bot) == before + 1  # tên danh mục của worker khớp số đo


async def test_no_refusal_is_sent_when_another_worker_already_owns_the_row(
    chatbot_bot: Bot, monkeypatch: pytest.MonkeyPatch
) -> None:
    bot = chatbot_bot
    user_id, tg = await linked_user(bot)
    await use_turns(bot, user_id, tg, 20)
    await bot.send("hỏi nữa", tg=tg)

    async def lost_the_row(self: BotInbox, *args: Any, **kwargs: Any) -> bool:
        return False  # dòng đã bị worker khác tiếp quản hay đã bị xóa

    monkeypatch.setattr(BotInbox, "end", lost_the_row)

    await bot.drain(tg, engine=ScriptedEngine("không gọi"), usage_gate=gate())

    assert bot.outbox.texts_to(tg) == []  # chỉ báo khi chính worker này đã loại dòng


class _SpyGate:
    """Ghi lại cổng được hỏi về ai và loại tin nào, rồi cho qua."""

    def __init__(self) -> None:
        self.asked: list[tuple[uuid.UUID, str]] = []

    async def check(
        self, session: AsyncSession, user_id: uuid.UUID, kind: str, *, now: datetime
    ) -> Any:
        self.asked.append((user_id, kind))
        return await gate().check(session, user_id, kind, now=now)


async def test_the_worker_asks_the_gate_about_this_user_and_this_kind_of_message(
    chatbot_bot: Bot, monkeypatch: pytest.MonkeyPatch
) -> None:
    bot = chatbot_bot
    user_id, tg = await linked_user(bot)
    await bot.send("hỏi gì đó", tg=tg)
    original = BotInbox.claim

    async def claim_as_photo(self: BotInbox, *args: Any, **kwargs: Any) -> ClaimResult:
        result = await original(self, *args, **kwargs)
        row = result.row
        return (
            result
            if row is None
            else dataclasses.replace(result, row=dataclasses.replace(row, kind="photo"))
        )

    monkeypatch.setattr(BotInbox, "claim", claim_as_photo)  # 2C sẽ có dòng ảnh thật
    spy = _SpyGate()

    await bot.drain(tg, engine=ScriptedEngine("ok"), usage_gate=spy)

    assert spy.asked == [(user_id, "photo")]


async def test_the_worker_refuses_to_run_without_a_gate_instead_of_silently_skipping_the_limit(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    await bot.send("hỏi gì đó", tg=tg)
    ctx = {  # thiếu `usage_gate`: lỗi cấu hình, không được coi là "không giới hạn"
        "session_factory": bot.session_factory,
        "telegram_client": bot.client,
        "chat_engine": ScriptedEngine("không gọi"),
        "bot_config": BotWorkerConfig(),
    }

    with pytest.raises(KeyError, match="usage_gate"):
        await bot_worker.drain_chat(ctx, tg)
