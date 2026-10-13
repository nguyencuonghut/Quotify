"""Chaos của claim hộp thư với NHIỀU TIẾN TRÌNH thật (kế hoạch 5.1, S2, kịch bản gốc ở S0(c)).

Lease 40 ms và thời gian giữ ngẫu nhiên 0 đến 90 ms làm lease hết hạn dưới chân worker đang chạy,
nên việc tiếp quản liên tục đua với lệnh hoàn tất của worker cũ. Bất biến: mỗi dòng hoàn tất đúng
một lần, không dòng nào bị claim lại sau khi đã hoàn tất, `attempts` tăng liên tục từ 1.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from conftest import BACKEND_DIR
from db_helpers import create_user, next_telegram_id, next_update_id
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

HELPER = Path(__file__).with_name("bot_claim_chaos_worker.py")
PROCESSES = 4


async def _chaos(
    factory: async_sessionmaker[AsyncSession],
    variant: str,
    *,
    chats: int,
    rows_per_chat: int,
) -> dict[str, int]:
    user_id = await create_user(factory)
    chat_ids = [next_telegram_id() for _ in range(chats)]
    row_ids: list[int] = []
    async with factory() as session:
        for chat_id in chat_ids:
            for _ in range(rows_per_chat):
                update_id = next_update_id()
                row_ids.append(update_id)
                await session.execute(
                    text(
                        "insert into bot_updates (update_id, chat_id, telegram_user_id, user_id, "
                        "status, payload_text) values (:id, :chat, :chat, :user, 'queued', 'x')"
                    ),
                    {"id": update_id, "chat": chat_id, "user": user_id},
                )
        await session.commit()

    # URL (có mật khẩu) lấy từ engine thay vì làm tham số test: pytest in tham số khi test fail.
    database_url = factory.kw["bind"].url.render_as_string(hide_password=False)
    env = {
        **os.environ,
        "PYTHONPATH": str(BACKEND_DIR),
        "BOT_CHAOS_DB_URL": database_url,
    }
    children = [
        await asyncio.create_subprocess_exec(
            sys.executable,
            str(HELPER),
            variant,
            json.dumps(chat_ids),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        for _ in range(PROCESSES)
    ]
    try:
        outputs = await asyncio.wait_for(
            asyncio.gather(*(child.communicate() for child in children)),
            timeout=120.0,
        )
    finally:
        for child in children:  # không để tiến trình con mồ côi khi test lỗi hoặc quá hạn
            if child.returncode is None:
                child.kill()
    for child, (_, err) in zip(children, outputs, strict=True):
        assert child.returncode == 0, err.decode(errors="replace")[-600:]

    events: list[dict[str, Any]] = [e for out, _ in outputs for e in json.loads(out.decode())]
    by_row: dict[int, list[dict[str, Any]]] = defaultdict(list)
    violations: dict[str, int] = defaultdict(int)
    for event in events:
        if event.get("timeout"):
            violations["timeout"] += 1
        else:
            by_row[event["update_id"]].append(event)
    for update_id in row_ids:
        claims = sorted(by_row.get(update_id, []), key=lambda e: e["claim_started"])
        winners = [e for e in claims if e["won"]]
        if len(winners) != 1:
            violations["a row was not completed exactly once"] += 1
        elif any(e["claim_started"] > winners[0]["completed_at"] for e in claims):
            violations["a row was claimed again after it was completed (revival)"] += 1
        if sorted(e["attempts"] for e in claims) != list(range(1, len(claims) + 1)):
            violations["attempts did not go 1..n"] += 1
    summary = {
        "rows": len(row_ids),
        "takeovers": sum(max(len(c) - 1, 0) for c in by_row.values()),
    }
    async with factory() as session:
        not_replied = await session.scalar(
            text(
                "select count(*) from bot_updates where chat_id = any(:c) and status <> 'replied'"
            ),
            {"c": chat_ids},
        )
    if not_replied:
        violations["a row did not end replied"] += 1
    return {**summary, **violations}


async def test_the_real_claim_completes_every_row_exactly_once_under_chaos(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    result = await _chaos(session_factory, "real", chats=3, rows_per_chat=20)

    # Đủ tranh chấp thì bài chaos mới có ý nghĩa: S0 đo hàng chục lần tiếp quản trên 60 dòng.
    assert result["takeovers"] >= 10, result
    violations = {k: v for k, v in result.items() if k not in {"rows", "takeovers"}}
    assert violations == {}, result


async def test_a_take_without_the_status_guard_is_caught_by_the_chaos(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # Đối chứng xác suất: lỗi chỉ lộ khi lệnh hoàn tất của worker cũ rơi đúng giữa lúc đọc đầu
    # hàng đợi và lúc nhận làm, nên cho tối đa vài lượt (thường lộ ngay lượt đầu).
    seen: dict[str, int] = {}
    for _ in range(4):
        result = await _chaos(
            session_factory,
            "unguarded_take",
            chats=2,
            rows_per_chat=30,
        )
        seen = {k: v for k, v in result.items() if k not in {"rows", "takeovers"}}
        if seen:
            break

    # Phải thấy đúng lỗi của biến thể này (không hoàn tất đúng một lần hoặc bị hồi sinh).
    assert set(seen) - {"timeout"}, f"the chaos test did not catch an unguarded take: {seen}"
