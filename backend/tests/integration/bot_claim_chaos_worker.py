"""Tiến trình con của bài chaos S2: claim, giữ ngẫu nhiên, hoàn tất có rào chắn.

Chạy như script: `python bot_claim_chaos_worker.py <biến thể> '<json danh sách chat>'`, với biến môi
trường `BOT_CHAOS_DB_URL` (database tạm của phiên test). In đúng một dòng JSON các sự kiện ra
stdout; mọi thứ khác (log) ra stderr. Thời gian dùng `time.monotonic()` (đồng hồ chung của hệ thống
trên Linux, không bị nhảy khi chỉnh giờ).

Lease 40 ms và thời gian giữ ngẫu nhiên 0 đến 90 ms để lease hết hạn ngay dưới chân worker đang
chạy, nên việc tiếp quản đua với lệnh hoàn tất của worker cũ.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import sys
import time
from datetime import UTC, datetime

from bot_claim_variants import VARIANTS
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.services.bot_inbox import BotInbox

LEASE_SECONDS = 0.040
HOLD_MAX_SECONDS = 0.090
TIMEOUT_SECONDS = 60.0


async def main(variant: str, chats: list[int]) -> list[dict[str, float | int | bool]]:
    engine = create_async_engine(os.environ["BOT_CHAOS_DB_URL"], pool_size=3, max_overflow=2)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    claim = VARIANTS[variant]
    order = list(chats)
    random.shuffle(order)
    events: list[dict[str, float | int | bool]] = []
    began = time.monotonic()
    try:
        while True:
            progressed = False
            for chat_id in order:
                claimed_at = time.monotonic()
                async with factory() as session:
                    claimed = await claim(session, chat_id, datetime.now(UTC), LEASE_SECONDS)
                    await session.commit()
                if claimed is None:
                    continue
                progressed = True
                await asyncio.sleep(random.uniform(0, HOLD_MAX_SECONDS))
                async with factory() as session:
                    done = await BotInbox(session).complete(
                        claimed.update_id,
                        claimed.attempts,
                        now=datetime.now(UTC),
                    )
                    await session.commit()
                events.append(
                    {
                        "update_id": claimed.update_id,
                        "attempts": claimed.attempts,
                        "claim_started": claimed_at,
                        "completed_at": time.monotonic(),
                        "won": done,
                    }
                )
            async with factory() as session:
                remaining = await session.scalar(
                    text(
                        "select count(*) from bot_updates "
                        "where chat_id = any(:chats) and status <> 'replied'"
                    ),
                    {"chats": chats},
                )
            if not remaining:
                break
            if time.monotonic() - began > TIMEOUT_SECONDS:
                events.append({"timeout": True})
                break
            if not progressed:
                await asyncio.sleep(0.002)
    finally:
        await engine.dispose()
    return events


if __name__ == "__main__":
    result = asyncio.run(main(sys.argv[1], json.loads(sys.argv[2])))
    sys.stdout.write(json.dumps(result) + "\n")
