"""Câu lệnh trong runbook mục 16.5 chạy được trên Postgres thật (kế hoạch 5.1, S8).

Runbook là tài liệu người vận hành chép-dán lúc khẩn cấp: câu lệnh sai cú pháp hay làm hỏng dữ liệu
lúc đó là tệ nhất, nên lấy nguyên văn khối SQL từ runbook rồi chạy nó.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from bot_fakes import ScriptedEngine
from bot_harness import Bot, linked_user
from db_helpers import create_user, next_update_id
from quota_helpers import gate, insert_turn, scratch_session
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[3]
RUNBOOK = ROOT / "docs" / "runbooks" / "deploy-vps-production.md"

pytestmark = pytest.mark.skipif(
    not RUNBOOK.exists(),
    reason="Không có runbook ở gốc repo (đang chạy trong container backend)",
)


def _runbook_sql(marker: str) -> str:
    runbook = RUNBOOK.read_text("utf-8")
    section = runbook[runbook.index("## 16. ") :]
    for block in re.findall(r"```sql\n(.*?)```", section, flags=re.DOTALL):
        if marker in block:
            return str(block)
    raise AssertionError(f"Mục 16 của runbook không có khối SQL chứa {marker!r}")


async def test_the_purge_ends_open_rows_without_their_content_and_leaves_the_rest(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    user_id, tg = await linked_user(bot)
    now = datetime.now(UTC)
    queued, processing, replied = next_update_id(), next_update_id(), next_update_id()
    await bot.insert_row(tg, user_id, queued, text_="nội dung đang chờ")
    await bot.insert_row(
        tg,
        user_id,
        processing,
        status="processing",
        attempts=1,
        lease_until=now + timedelta(minutes=4),
        text_="nội dung đang xử lý",
        reply_text="câu trả lời đã lưu",
    )
    await bot.insert_row(tg, user_id, replied, status="replied", finished_at=now)
    before = await bot.row(replied)

    async with bot.session_factory() as session:
        await session.execute(text(_runbook_sql("update bot_updates")))
        await session.commit()

    for update_id in (queued, processing):
        row = await bot.row(update_id)
        assert (row.status, row.error_category) == ("dropped", "operator_purge")
        assert (row.payload_text, row.reply_text) == (None, None)  # nội dung không còn trong DB
        assert row.finished_at is not None
    after = await bot.row(replied)
    assert (after.status, after.error_category, after.finished_at) == (
        before.status,
        before.error_category,
        before.finished_at,
    )


async def test_the_chat_keeps_working_after_a_purge(chatbot_bot: Bot) -> None:
    bot = chatbot_bot
    user_id, tg = await linked_user(bot)
    await bot.insert_row(
        tg,
        user_id,
        next_update_id(),
        status="processing",
        attempts=1,
        lease_until=datetime.now(UTC) + timedelta(minutes=4),
    )
    async with bot.session_factory() as session:
        await session.execute(text(_runbook_sql("update bot_updates")))
        await session.commit()

    update_id = await bot.send("tin mới sau khi dọn", tg=tg)
    await bot.drain(tg, engine=ScriptedEngine("đã nhận"))

    assert (await bot.row(update_id)).status == "replied"  # dòng bị dọn không chặn chat
    assert bot.outbox.texts_to(tg) == ["đã nhận"]


async def test_the_monitoring_queries_run_and_never_read_message_content(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    user_id, tg = await linked_user(bot)
    now = datetime.now(UTC)
    await bot.insert_row(tg, user_id, next_update_id(), text_="nội dung đang chờ")
    await bot.insert_row(
        tg, user_id, next_update_id(), status="failed", finished_at=now, received_at=now
    )
    block = _runbook_sql("group by status")
    assert "payload_text" not in block and "reply_text" not in block  # chỉ siêu dữ liệu

    async with bot.session_factory() as session:
        results = [
            (await session.execute(text(statement))).all()
            for statement in block.split(";")
            if statement.strip()
        ]

    assert len(results) == 2  # câu đếm theo trạng thái và câu đếm theo lý do
    by_status = {row[0]: row[1] for row in results[0]}
    assert by_status["queued"] >= 1 and by_status["failed"] >= 1


@pytest.mark.parametrize("db_zone", ["UTC", "Asia/Ho_Chi_Minh", "America/Los_Angeles"])
async def test_the_usage_query_agrees_with_the_gate_around_the_vietnamese_midnight(
    chatbot_bot: Bot, db_zone: str
) -> None:
    user_id = await create_user(chatbot_bot.session_factory)
    block = _runbook_sql("turns_today")
    assert "payload_text" not in block and "reply_text" not in block  # chỉ đếm, không đọc nội dung
    # `now()` thay bằng thời điểm cố định để thử đúng quanh nửa đêm giờ Việt Nam (17:00 UTC).
    query = block.strip().rstrip(";").replace("now()", "cast(:instant as timestamptz)")
    # (nhận lúc, lưu câu trả lời lúc)
    turns = [
        (datetime(2026, 10, 14, 9, 55, tzinfo=UTC), datetime(2026, 10, 14, 10, 0, tzinfo=UTC)),
        (datetime(2026, 10, 14, 16, 29, tzinfo=UTC), datetime(2026, 10, 14, 16, 30, tzinfo=UTC)),
        # Nhận 23:50 giờ Việt Nam ngày 14 nhưng trả lời 00:30 ngày 15: là lượt của ngày 15.
        (datetime(2026, 10, 14, 16, 50, tzinfo=UTC), datetime(2026, 10, 14, 17, 30, tzinfo=UTC)),
    ]
    cases = [
        (datetime(2026, 10, 14, 16, 59, tzinfo=UTC), 2),  # 23:59 ngày 14: hai lượt đầu
        (datetime(2026, 10, 14, 17, 0, tzinfo=UTC), 1),  # 00:00 ngày 15: chỉ lượt thứ ba
        (datetime(2026, 10, 15, 16, 59, tzinfo=UTC), 1),  # 23:59 ngày 15
    ]

    async with scratch_session(chatbot_bot, db_zone=db_zone) as session:
        # `limit 10` của câu truy vấn có thể không thấy người dùng này trong DB dùng chung: bỏ dòng
        # của người khác ngay trong giao dịch (hoàn tác, không bao giờ commit).
        await session.execute(text("delete from bot_updates where user_id <> :u"), {"u": user_id})
        for received, saved_at in turns:
            await insert_turn(session, user_id, received, saved_at=saved_at)
        for instant, expected in cases:
            rows = (await session.execute(text(query), {"instant": instant})).all()
            summary = await gate().summary(session, user_id, now=instant)
            by_user = {row.user_id: row.turns_today for row in rows}
            assert by_user[user_id] == summary.turns_used == expected, instant
