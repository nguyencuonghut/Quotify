"""Các biến thể claim SAI làm đối chứng cho S2 (kế hoạch 5.1, mục 4.5 và S0(c)).

Chúng chỉ để chứng minh bộ test BẮT được lỗi: mỗi biến thể là một cách "đơn giản hơn" nghe có vẻ
đúng nhưng hỏng khi đua nhau (kết quả đo ở `docs/quotify/analysis-chatbot-5-1/s0/pg/`). TUYỆT ĐỐI
không dùng trong `app/`. Biến thể `real` bọc `BotInbox.claim` thật để chạy cùng một bộ kiểm tra.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.bot_inbox import BotInbox

_LOCK = text(
    "SELECT pg_advisory_xact_lock(hashtextextended('bot:chat:' || CAST(:chat_id AS BIGINT), 0))"
)
_LIVE = text(
    """
    SELECT 1 FROM bot_updates
    WHERE chat_id = :chat_id AND status = 'processing' AND lease_until > :now LIMIT 1
    """
)
_HEAD = text(
    """
    SELECT update_id, status, lease_until, attempts FROM bot_updates
    WHERE chat_id = :chat_id AND status IN ('queued','processing')
    ORDER BY update_id LIMIT 1
    """
)
_TAKE_GUARDED = text(
    """
    UPDATE bot_updates
       SET status = 'processing', lease_until = :lease_until, attempts = attempts + 1,
           started_at = coalesce(started_at, :now)
     WHERE update_id = :id AND status IN ('queued','processing')
 RETURNING update_id, attempts
    """
)
_TAKE_UNGUARDED = text(
    """
    UPDATE bot_updates
       SET status = 'processing', lease_until = :lease_until, attempts = attempts + 1,
           started_at = coalesce(started_at, :now)
     WHERE update_id = :id
 RETURNING update_id, attempts
    """
)
_POSTCHECK = text(
    """
    SELECT count(*) FROM bot_updates
    WHERE chat_id = :chat_id AND status = 'processing' AND lease_until > :now
    """
)


@dataclass(frozen=True, slots=True)
class Claim:
    update_id: int
    attempts: int
    # Số dòng `processing` còn lease của chat NGAY SAU khi claim, trong cùng giao dịch: phải là 1.
    live_after: int


ClaimFn = Callable[[AsyncSession, int, datetime, float], Awaitable[Claim | None]]


async def _finish(
    session: AsyncSession,
    chat_id: int,
    now: datetime,
    row: object | None,
) -> Claim | None:
    if row is None:
        return None
    live = (await session.execute(_POSTCHECK, {"chat_id": chat_id, "now": now})).scalar_one()
    return Claim(row.update_id, row.attempts, live)  # type: ignore[attr-defined]


def _lease(now: datetime, lease_s: float) -> datetime:
    return now + timedelta(seconds=lease_s)


async def real(session: AsyncSession, chat_id: int, now: datetime, lease_s: float) -> Claim | None:
    """Thuật toán thật của `BotInbox` (số lần thử đặt rất lớn để chaos không bị `failed`)."""
    result = await BotInbox(session).claim(
        chat_id,
        now=now,
        lease_seconds=lease_s,
        max_attempts=10_000,
    )
    if result.row is None:
        return None
    live = (await session.execute(_POSTCHECK, {"chat_id": chat_id, "now": now})).scalar_one()
    return Claim(result.row.update_id, result.row.attempts, live)


async def unguarded_take(
    session: AsyncSession, chat_id: int, now: datetime, lease_s: float
) -> Claim | None:
    """Như thật nhưng `UPDATE` nhận dòng KHÔNG có điều kiện `status`: lệnh hoàn tất của worker cũ
    chen vào giữa lúc đọc đầu hàng đợi và lúc nhận làm sẽ bị ghi đè, dòng đã xong bị hồi sinh."""
    await session.execute(_LOCK, {"chat_id": chat_id})
    if (await session.execute(_LIVE, {"chat_id": chat_id, "now": now})).first():
        return None
    head = (await session.execute(_HEAD, {"chat_id": chat_id})).first()
    if head is None or (head.status == "queued" and head.lease_until and head.lease_until > now):
        return None
    row = (
        await session.execute(
            _TAKE_UNGUARDED,
            {"id": head.update_id, "now": now, "lease_until": _lease(now, lease_s)},
        )
    ).first()
    return await _finish(session, chat_id, now, row)


async def headlock(
    session: AsyncSession, chat_id: int, now: datetime, lease_s: float
) -> Claim | None:
    """Khóa dòng đầu hàng đợi đơn thuần: không advisory lock, không điều kiện lease cả chat."""
    head = (
        await session.execute(
            text(
                """
                SELECT update_id FROM bot_updates
                WHERE chat_id = :chat_id
                  AND (status = 'queued' OR (status = 'processing' AND lease_until <= :now))
                ORDER BY update_id LIMIT 1 FOR UPDATE
                """
            ),
            {"chat_id": chat_id, "now": now},
        )
    ).first()
    if head is None:
        return None
    row = (
        await session.execute(
            _TAKE_GUARDED,
            {"id": head.update_id, "now": now, "lease_until": _lease(now, lease_s)},
        )
    ).first()
    return await _finish(session, chat_id, now, row)


async def headlock_headcheck(
    session: AsyncSession, chat_id: int, now: datetime, lease_s: float
) -> Claim | None:
    """Khóa dòng đầu cộng kiểm tra dòng đầu: qua bài đua thuần, hỏng khi tin đến lệch thứ tự."""
    head = (
        await session.execute(
            text(
                """
                SELECT update_id, lease_until FROM bot_updates
                WHERE chat_id = :chat_id AND status IN ('queued','processing')
                ORDER BY update_id LIMIT 1 FOR UPDATE
                """
            ),
            {"chat_id": chat_id},
        )
    ).first()
    if head is None or (head.lease_until is not None and head.lease_until > now):
        return None
    row = (
        await session.execute(
            _TAKE_GUARDED,
            {"id": head.update_id, "now": now, "lease_until": _lease(now, lease_s)},
        )
    ).first()
    return await _finish(session, chat_id, now, row)


async def advisory_nolive(
    session: AsyncSession, chat_id: int, now: datetime, lease_s: float
) -> Claim | None:
    """Có advisory lock nhưng THIẾU điều kiện "không có dòng đang chạy còn lease"."""
    await session.execute(_LOCK, {"chat_id": chat_id})
    head = (
        await session.execute(
            text(
                """
                SELECT update_id FROM bot_updates
                WHERE chat_id = :chat_id
                  AND (status = 'queued' OR (status = 'processing' AND lease_until <= :now))
                ORDER BY update_id LIMIT 1
                """
            ),
            {"chat_id": chat_id, "now": now},
        )
    ).first()
    if head is None:
        return None
    row = (
        await session.execute(
            _TAKE_GUARDED,
            {"id": head.update_id, "now": now, "lease_until": _lease(now, lease_s)},
        )
    ).first()
    return await _finish(session, chat_id, now, row)


async def skip_locked(
    session: AsyncSession, chat_id: int, now: datetime, lease_s: float
) -> Claim | None:
    """`FOR UPDATE SKIP LOCKED`: bên thứ hai nhảy cóc sang dòng sau khi dòng đầu đang chạy."""
    head = (
        await session.execute(
            text(
                """
                SELECT update_id FROM bot_updates
                WHERE chat_id = :chat_id AND status = 'queued'
                ORDER BY update_id LIMIT 1 FOR UPDATE SKIP LOCKED
                """
            ),
            {"chat_id": chat_id},
        )
    ).first()
    if head is None:
        return None
    row = (
        await session.execute(
            _TAKE_GUARDED,
            {"id": head.update_id, "now": now, "lease_until": _lease(now, lease_s)},
        )
    ).first()
    return await _finish(session, chat_id, now, row)


async def nolock_noguard(
    session: AsyncSession, chat_id: int, now: datetime, lease_s: float
) -> Claim | None:
    """Đọc đầu hàng đợi không khóa rồi `UPDATE` chỉ theo `update_id`."""
    head = (await session.execute(_HEAD, {"chat_id": chat_id})).first()
    if head is None:
        return None
    row = (
        await session.execute(
            _TAKE_UNGUARDED,
            {"id": head.update_id, "now": now, "lease_until": _lease(now, lease_s)},
        )
    ).first()
    return await _finish(session, chat_id, now, row)


async def due_filter(
    session: AsyncSession, chat_id: int, now: datetime, lease_s: float
) -> Claim | None:
    """Nhận dòng "đến hạn" nhỏ nhất: nhảy cóc qua dòng đang chờ thử lại (backoff)."""
    await session.execute(_LOCK, {"chat_id": chat_id})
    if (await session.execute(_LIVE, {"chat_id": chat_id, "now": now})).first():
        return None
    head = (
        await session.execute(
            text(
                """
                SELECT update_id FROM bot_updates
                WHERE chat_id = :chat_id
                  AND ((status = 'queued' AND (lease_until IS NULL OR lease_until <= :now))
                       OR status = 'processing')
                ORDER BY update_id LIMIT 1
                """
            ),
            {"chat_id": chat_id, "now": now},
        )
    ).first()
    if head is None:
        return None
    row = (
        await session.execute(
            _TAKE_GUARDED,
            {"id": head.update_id, "now": now, "lease_until": _lease(now, lease_s)},
        )
    ).first()
    return await _finish(session, chat_id, now, row)


VARIANTS: dict[str, ClaimFn] = {
    "real": real,
    "unguarded_take": unguarded_take,
    "headlock": headlock,
    "headlock_headcheck": headlock_headcheck,
    "advisory_nolive": advisory_nolive,
    "skip_locked": skip_locked,
    "nolock_noguard": nolock_noguard,
    "due_filter": due_filter,
}
