"""Mỗi chat chỉ một dòng chạy tại một thời điểm (kế hoạch 5.1, S2): claim đua trên Postgres thật.

Bộ test phải BẮT được các biến thể sai (`bot_claim_variants`): nếu một cách claim "đơn giản hơn"
qua được bộ này thì bộ test đang xanh giả. Kịch bản và số đo gốc ở
`docs/quotify/analysis-chatbot-5-1/s0/pg/`.
"""

from __future__ import annotations

import asyncio
import random
import time
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from bot_claim_variants import VARIANTS, Claim, ClaimFn
from db_helpers import create_user, next_telegram_id, next_update_id
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.bot_inbox import BotInbox

Factory = async_sessionmaker[AsyncSession]
LEASE = 240.0
RACE_ROUNDS = 40
# Đối chứng chỉ cần thấy MỘT vi phạm (S0: các biến thể sai hỏng 300 trên 300 vòng).
NEGATIVE_ROUNDS = 15
WORKERS = 3
ROWS_PER_CHAT = 5
HOLD_MAX = 0.004
# Một vòng đúng chỉ mất vài chục mili giây; quá hạn nghĩa là kẹt (tính là vi phạm).
ROUND_TIMEOUT = 8.0


# --- dữ liệu và thao tác nền ---------------------------------------------------------------------


async def _insert(
    factory: Factory,
    chat_id: int,
    user_id: uuid.UUID,
    update_ids: list[int],
    *,
    status: str = "queued",
    lease_until: datetime | None = None,
    attempts: int = 0,
) -> None:
    async with factory() as session:
        for update_id in update_ids:
            await session.execute(
                text(
                    "insert into bot_updates (update_id, chat_id, telegram_user_id, user_id, "
                    "status, payload_text, attempts, lease_until) values "
                    "(:id, :chat, :chat, :user, :status, 'x', :attempts, :lease)"
                ),
                {
                    "id": update_id,
                    "chat": chat_id,
                    "user": user_id,
                    "status": status,
                    "attempts": attempts,
                    "lease": lease_until,
                },
            )
        await session.commit()


async def _claim(factory: Factory, claim: ClaimFn, chat_id: int, now: datetime) -> Claim | None:
    async with factory() as session:
        result = await claim(session, chat_id, now, LEASE)
        await session.commit()
    return result


async def _complete(factory: Factory, update_id: int, attempts: int) -> bool:
    async with factory() as session:
        done = await BotInbox(session).complete(update_id, attempts, now=datetime.now(UTC))
        await session.commit()
    return done


async def _replied(factory: Factory, chat_id: int) -> int:
    async with factory() as session:
        return int(
            await session.scalar(
                text("select count(*) from bot_updates where chat_id = :c and status = 'replied'"),
                {"c": chat_id},
            )
            or 0
        )


# --- bài đua đồng thời ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Event:
    update_id: int
    attempts: int
    started: float
    finished: float
    live_after: int
    completed: bool


async def _race_round(factory: Factory, claim: ClaimFn, ids: list[int], chat_id: int) -> set[str]:
    """Nhiều worker cùng tranh một chat có sẵn các dòng; trả về các vi phạm bất biến thấy được."""
    events: list[Event] = []
    started_at = time.monotonic()

    async def worker() -> None:
        while True:
            claimed = await _claim(factory, claim, chat_id, datetime.now(UTC))
            if claimed is not None:
                began = time.monotonic()
                await asyncio.sleep(random.uniform(0, HOLD_MAX))
                ended = time.monotonic()
                done = await _complete(factory, claimed.update_id, claimed.attempts)
                events.append(
                    Event(
                        claimed.update_id, claimed.attempts, began, ended, claimed.live_after, done
                    )
                )
            elif await _replied(factory, chat_id) >= len(ids):
                return
            elif time.monotonic() - started_at > ROUND_TIMEOUT:
                events.append(Event(-1, -1, 0.0, 0.0, 0, False))  # đánh dấu quá giờ
                return
            else:
                await asyncio.sleep(0.0005)

    await asyncio.gather(*(worker() for _ in range(WORKERS)))
    return _violations(events, ids)


def _violations(events: list[Event], ids: list[int]) -> set[str]:
    found: set[str] = set()
    if any(e.update_id == -1 for e in events):
        found.add("timeout")
    ordered = sorted((e for e in events if e.update_id != -1), key=lambda e: e.started)
    got = [e.update_id for e in ordered]
    if sorted(got) != sorted(ids):
        found.add("a row was not claimed exactly once")
    if got != sorted(ids):
        found.add("rows were not claimed in ascending update_id order")
    if any(e.attempts != 1 for e in ordered):
        found.add("a row was claimed more than once")
    if any(e.live_after != 1 for e in ordered):
        found.add("more than one live row of the chat inside the claim transaction")
    if any(
        later.started < max(e.finished for e in ordered[: index + 1])
        for index, later in enumerate(ordered[1:])
    ):
        found.add("two rows of the chat were held at the same time")
    if any(not e.completed for e in ordered):
        found.add("a completion lost its row")
    return found


async def _race(
    factory: Factory, variant: str, rounds: int, *, stop_at_first: bool = False
) -> Counter[str]:
    user_id = await create_user(factory)
    seen: Counter[str] = Counter()
    for _ in range(rounds):
        chat_id = next_telegram_id()
        ids = [next_update_id() for _ in range(ROWS_PER_CHAT)]
        await _insert(factory, chat_id, user_id, ids)
        seen.update(await _race_round(factory, VARIANTS[variant], ids, chat_id))
        if stop_at_first and seen:
            break  # đối chứng chỉ cần thấy MỘT vi phạm, khỏi tốn thêm vòng
    return seen


async def test_the_real_claim_never_runs_two_rows_of_a_chat_at_once_and_keeps_the_order(
    session_factory: Factory,
) -> None:
    seen = await _race(session_factory, "real", RACE_ROUNDS)

    assert dict(seen) == {}


@pytest.mark.parametrize(
    "variant", ["headlock", "advisory_nolive", "skip_locked", "nolock_noguard"]
)
async def test_a_naive_claim_is_caught_by_the_race(session_factory: Factory, variant: str) -> None:
    seen = await _race(session_factory, variant, NEGATIVE_ROUNDS, stop_at_first=True)

    # Một vòng quá hạn không đủ: phải thấy đúng một vi phạm bất biến thật.
    assert set(seen) - {"timeout"}, f"the race test did not catch '{variant}': {seen}"


# --- kịch bản xác định ---------------------------------------------------------------------------


async def _out_of_order(factory: Factory, claim: ClaimFn) -> tuple[Claim | None, Claim, int, int]:
    """Dòng 101 được claim, rồi dòng 100 mới đến: 100 không được chạy trong lúc 101 còn lease.

    Trả về (lần claim thứ hai khi 101 còn sống, lần claim đầu, update_id nhỏ, update_id lớn).
    """
    user_id = await create_user(factory)
    chat_id = next_telegram_id()
    earlier, later = next_update_id(), next_update_id()  # `earlier` có update_id nhỏ hơn
    await _insert(factory, chat_id, user_id, [later])
    first = await _claim(factory, claim, chat_id, datetime.now(UTC))
    assert first is not None and first.update_id == later
    await _insert(factory, chat_id, user_id, [earlier])
    second = await _claim(factory, claim, chat_id, datetime.now(UTC))
    return second, first, earlier, later


async def _backoff_head(factory: Factory, claim: ClaimFn) -> Claim | None:
    """Dòng đầu đang chờ thử lại (`lease_until` ở tương lai) chặn cả chat, không bị nhảy cóc."""
    user_id = await create_user(factory)
    chat_id = next_telegram_id()
    waiting, behind = next_update_id(), next_update_id()
    retry_at = datetime.now(UTC) + timedelta(seconds=60)
    await _insert(factory, chat_id, user_id, [waiting], lease_until=retry_at, attempts=1)
    await _insert(factory, chat_id, user_id, [behind])
    return await _claim(factory, claim, chat_id, datetime.now(UTC))


async def test_a_row_that_arrives_out_of_order_waits_for_the_live_row_then_runs(
    session_factory: Factory,
) -> None:
    during, first, earlier, later = await _out_of_order(session_factory, VARIANTS["real"])

    assert during is None  # 100 không được chạy trong lúc 101 còn lease
    chat_id = await _chat_of(session_factory, later)
    assert await _complete(session_factory, later, first.attempts)
    after = await _claim(session_factory, VARIANTS["real"], chat_id, datetime.now(UTC))
    assert after is not None and after.update_id == earlier  # xong 101 thì tới 100


async def test_the_head_check_alone_fails_when_a_row_arrives_out_of_order(
    session_factory: Factory,
) -> None:
    # Biến thể này qua được bài đua thuần: chỉ kịch bản này bắt được nó.
    claimed, *_ = await _out_of_order(session_factory, VARIANTS["headlock_headcheck"])

    assert claimed is not None


async def test_a_row_waiting_for_a_retry_blocks_the_whole_chat(session_factory: Factory) -> None:
    assert await _backoff_head(session_factory, VARIANTS["real"]) is None


async def test_claiming_the_next_due_row_is_caught_because_it_skips_a_row_in_backoff(
    session_factory: Factory,
) -> None:
    claimed = await _backoff_head(session_factory, VARIANTS["due_filter"])

    assert claimed is not None


async def test_the_row_claimed_after_the_live_one_finishes_is_the_next_in_order(
    session_factory: Factory,
) -> None:
    user_id = await create_user(session_factory)
    chat_id = next_telegram_id()
    first, second = next_update_id(), next_update_id()
    await _insert(session_factory, chat_id, user_id, [first, second])

    one = await _claim(session_factory, VARIANTS["real"], chat_id, datetime.now(UTC))
    assert one is not None and one.update_id == first
    assert await _claim(session_factory, VARIANTS["real"], chat_id, datetime.now(UTC)) is None
    assert await _complete(session_factory, first, one.attempts)
    two = await _claim(session_factory, VARIANTS["real"], chat_id, datetime.now(UTC))

    assert two is not None and two.update_id == second


async def test_two_workers_racing_for_an_expired_lease_only_one_takes_it_over(
    session_factory: Factory,
) -> None:
    user_id = await create_user(session_factory)
    chat_id = next_telegram_id()
    stuck = next_update_id()
    await _insert(
        session_factory,
        chat_id,
        user_id,
        [stuck],
        status="processing",
        lease_until=datetime.now(UTC) - timedelta(seconds=1),
        attempts=1,
    )

    results = await asyncio.gather(
        *(_claim(session_factory, VARIANTS["real"], chat_id, datetime.now(UTC)) for _ in range(4))
    )

    winners = [c for c in results if c is not None]
    assert len(winners) == 1 and (winners[0].update_id, winners[0].attempts) == (stuck, 2)


async def test_chats_do_not_wait_for_each_other_but_one_chat_is_serialised(
    session_factory: Factory,
) -> None:
    user_id = await create_user(session_factory)
    chat_a, chat_b = next_telegram_id(), next_telegram_id()
    a_row, b_row = next_update_id(), next_update_id()
    await _insert(session_factory, chat_a, user_id, [a_row])
    await _insert(session_factory, chat_b, user_id, [b_row])

    async with session_factory() as holder:
        # Giữ khóa của chat A bằng một giao dịch claim chưa commit.
        held = await VARIANTS["real"](holder, chat_a, datetime.now(UTC), LEASE)
        assert held is not None

        other_chat = await asyncio.wait_for(
            _claim(session_factory, VARIANTS["real"], chat_b, datetime.now(UTC)),
            timeout=2.0,
        )
        assert other_chat is not None and other_chat.update_id == b_row  # chat B không phải chờ

        same_chat = asyncio.create_task(
            _claim(session_factory, VARIANTS["real"], chat_a, datetime.now(UTC))
        )
        await asyncio.sleep(0.3)
        assert not same_chat.done()  # cùng chat thì phải chờ bên đang giữ khóa

        await holder.commit()

    assert await asyncio.wait_for(same_chat, timeout=5.0) is None  # dòng đã bị bên kia nhận


async def _chat_of(factory: Factory, update_id: int) -> int:
    async with factory() as session:
        return int(
            await session.scalar(
                text("select chat_id from bot_updates where update_id = :i"),
                {"i": update_id},
            )
            or 0
        )


async def _wait_until_a_statement_waits_for_a_lock(factory: Factory) -> None:
    async with factory() as session:
        for _ in range(200):
            waiting = await session.scalar(
                text(
                    "select count(*) from pg_stat_activity "
                    "where datname = current_database() and wait_event_type = 'Lock'"
                )
            )
            if waiting:
                return
            await asyncio.sleep(0.025)
    raise AssertionError("no statement ever waited for a row lock")


async def test_a_take_that_loses_its_row_to_a_late_completion_retries_with_the_next_row(
    session_factory: Factory,
) -> None:
    """`UPDATE` trả 0 dòng (dòng vừa bị lệnh hoàn tất của worker cũ đóng): phải đọc lại đầu hàng.

    Dựng xác định bằng khóa dòng: worker cũ đã ghi `replied` nhưng chưa commit; claim đã đọc dòng đó
    là đầu hàng đợi và đang chờ khóa dòng. Khi worker cũ commit, `UPDATE` có điều kiện `status` trả
    0 dòng, và claim phải chuyển sang dòng kế tiếp thay vì bỏ cuộc hoặc hồi sinh dòng đã xong.
    """
    user_id = await create_user(session_factory)
    chat_id = next_telegram_id()
    stale, behind = next_update_id(), next_update_id()
    expired = datetime.now(UTC) - timedelta(seconds=1)
    await _insert(
        session_factory,
        chat_id,
        user_id,
        [stale],
        status="processing",
        lease_until=expired,
        attempts=1,
    )
    await _insert(session_factory, chat_id, user_id, [behind])

    async with session_factory() as late_worker:
        await late_worker.execute(
            text("update bot_updates set status = 'replied' where update_id = :i"),
            {"i": stale},
        )
        claim = asyncio.create_task(
            _claim(session_factory, VARIANTS["real"], chat_id, datetime.now(UTC))
        )
        await _wait_until_a_statement_waits_for_a_lock(session_factory)
        assert not claim.done()  # claim đang chờ khóa dòng của worker cũ
        await late_worker.commit()

    claimed = await asyncio.wait_for(claim, timeout=5.0)
    assert claimed is not None and claimed.update_id == behind
    async with session_factory() as session:
        stale_status = await session.scalar(
            text("select status from bot_updates where update_id = :i"),
            {"i": stale},
        )
    assert stale_status == "replied"  # dòng đã xong không bị hồi sinh


async def test_the_head_of_a_chat_is_its_lowest_update_id_even_without_an_index_scan(
    session_factory: Factory,
) -> None:
    """Chỉ mục từng phần tình cờ trả về dòng đã sắp xếp, nên `ORDER BY` chỉ lộ khi quét tuần tự."""
    user_id = await create_user(session_factory)
    chat_id = next_telegram_id()
    lower, higher = next_update_id(), next_update_id()
    await _insert(session_factory, chat_id, user_id, [higher])  # dòng cao chèn trước (vật lý)
    await _insert(session_factory, chat_id, user_id, [lower])

    async with session_factory() as session:
        for setting in ("enable_indexscan", "enable_bitmapscan", "enable_indexonlyscan"):
            await session.execute(text(f"SET LOCAL {setting} = off"))
        result = await BotInbox(session).claim(
            chat_id,
            now=datetime.now(UTC),
            lease_seconds=LEASE,
            max_attempts=3,
        )
        await session.commit()

    assert result.row is not None and result.row.update_id == lower
