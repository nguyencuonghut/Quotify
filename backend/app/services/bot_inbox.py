"""Hộp thư của chatbot (kế hoạch 5.1, mục 4.4 và 4.5).

Chỉ `flush`/`execute`, không `commit`: người gọi (runner, worker) giữ ranh giới giao dịch.

Thuật toán claim đã chạy thật ở S0(c) (`docs/quotify/analysis-chatbot-5-1/`): mỗi chat chỉ một dòng
`processing` còn lease tại một thời điểm, theo thứ tự `update_id` trong khả năng. Các biến thể
đơn giản hơn (khóa dòng đầu, `SKIP LOCKED`, advisory lock không có điều kiện lease) đều hỏng.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bot_update import BotUpdate

# Phải ép kiểu: với asyncpg, nối chuỗi với số nguyên đã bind báo DataError (đo ở S0(c)).
_SQL_LOCK = text(
    "SELECT pg_advisory_xact_lock(hashtextextended('bot:chat:' || CAST(:chat_id AS BIGINT), 0))"
)
_SQL_LIVE = text(
    """
    SELECT 1 FROM bot_updates
    WHERE chat_id = :chat_id AND status = 'processing' AND lease_until > :now
    LIMIT 1
    """
)
_SQL_HEAD = text(
    """
    SELECT update_id, status, lease_until, attempts FROM bot_updates
    WHERE chat_id = :chat_id AND status IN ('queued','processing')
    ORDER BY update_id
    LIMIT 1
    """
)
_SQL_EXHAUST = text(
    """
    UPDATE bot_updates
       SET status = 'failed', error_category = 'lease_exhausted', finished_at = :now,
           payload_text = NULL, reply_text = NULL
     WHERE update_id = :id AND status IN ('queued','processing')
    """
)
# Điều kiện `status IN (...)` là bắt buộc: thiếu nó thì lệnh hoàn tất của worker cũ chen vào giữa
# lúc đọc đầu hàng đợi và lúc nhận làm sẽ bị ghi đè, dòng đã xong bị "hồi sinh" (đo ở S0(c)).
_SQL_TAKE = text(
    """
    UPDATE bot_updates
       SET status = 'processing', lease_until = :lease_until, attempts = attempts + 1,
           started_at = coalesce(started_at, :now)
     WHERE update_id = :id AND status IN ('queued','processing')
 RETURNING update_id, chat_id, telegram_user_id, user_id, kind, payload_text, reply_text,
           attempts, received_at, sent_parts
    """
)
# Mọi ghi kết quả đều có rào chắn: chỉ chủ sở hữu của lần claim (đúng `attempts`) mới ghi được.
_SQL_SAVE_REPLY = text(
    """
    UPDATE bot_updates SET reply_text = :text, reply_saved_at = :now
     WHERE update_id = :id AND status = 'processing' AND attempts = :attempts
    """
)
_SQL_SAVE_SENT_PARTS = text(
    """
    UPDATE bot_updates SET sent_parts = :parts
     WHERE update_id = :id AND status = 'processing' AND attempts = :attempts
    """
)
# Đưa dòng về hàng đợi để thử lại sau `retry_at` (backoff). Giữ nguyên `reply_text` nếu đã lưu, để
# lần sau chỉ gửi lại câu đã có mà không gọi engine lần hai.
_SQL_REQUEUE = text(
    """
    UPDATE bot_updates SET status = 'queued', lease_until = :retry_at
     WHERE update_id = :id AND status = 'processing' AND attempts = :attempts
    """
)
# Kết thúc dòng bằng `failed` hoặc `dropped` và xóa nội dung (chỉ giữ siêu dữ liệu).
_SQL_END = text(
    """
    UPDATE bot_updates
       SET status = :status, error_category = :category, finished_at = :now,
           payload_text = NULL, reply_text = NULL
     WHERE update_id = :id AND status = 'processing' AND attempts = :attempts
    """
)
# Nhả lease (khi worker bị hủy): dòng claim lại được ngay, không phải chờ lease hết hạn.
_SQL_RELEASE = text(
    """
    UPDATE bot_updates SET lease_until = :now
     WHERE update_id = :id AND status = 'processing' AND attempts = :attempts
    """
)
_SQL_OWNS = text(
    """
    SELECT 1 FROM bot_updates
     WHERE update_id = :id AND status = 'processing' AND attempts = :attempts
    """
)
# Chat có dòng claim được mà chưa ai nhận: `queued` vào đủ lâu (chuông có thể đã mất), `queued` đã
# đến hạn thử lại, hoặc `processing` đã hết lease (worker chết). Bỏ chat đang có dòng chạy còn lease
# hoặc dòng đầu đang chờ thử lại: đánh chuông cho chúng chỉ là chuông thừa (claim sẽ trả rỗng).
_SQL_PENDING = text(
    """
    SELECT DISTINCT ON (b.chat_id) b.chat_id, b.update_id
      FROM bot_updates b
     WHERE b.status IN ('queued','processing')
       AND ((b.status = 'queued' AND b.lease_until IS NULL AND b.received_at <= :cutoff)
         OR (b.status = 'queued' AND b.lease_until IS NOT NULL AND b.lease_until <= :now)
         OR (b.status = 'processing' AND b.lease_until <= :now))
       AND NOT EXISTS (
            SELECT 1 FROM bot_updates p
             WHERE p.chat_id = b.chat_id
               AND ((p.status = 'processing' AND p.lease_until > :now)
                 OR (p.status = 'queued' AND p.lease_until > :now)))
     ORDER BY b.chat_id, b.update_id
     LIMIT :limit
    """
)
_SQL_DELETE_FINISHED = text(
    """
    DELETE FROM bot_updates
     WHERE status IN ('replied','failed','dropped') AND finished_at < :cutoff
    """
)
_SQL_COMPLETE = text(
    """
    UPDATE bot_updates
       SET status = 'replied', finished_at = :now, payload_text = NULL, reply_text = NULL
     WHERE update_id = :id AND status = 'processing' AND attempts = :attempts
    """
)


@dataclass(frozen=True, slots=True)
class ClaimedRow:
    update_id: int
    chat_id: int
    telegram_user_id: int
    user_id: UUID
    kind: str
    # `repr=False`: nội dung tin không được lọt vào log khi ai đó `logger("%s", row)`.
    payload_text: str | None = field(repr=False)
    reply_text: str | None = field(repr=False)
    attempts: int
    received_at: datetime
    # Số phần của câu trả lời đã gửi xong: lần claim sau gửi tiếp từ phần chưa gửi.
    sent_parts: int = 0


@dataclass(frozen=True, slots=True)
class PendingChat:
    chat_id: int
    # Dòng cũ nhất còn claim được của chat: dùng làm `_job_id` của chuông (`bot:<update_id>`).
    update_id: int


@dataclass(frozen=True, slots=True)
class ClaimResult:
    row: ClaimedRow | None
    # Các dòng bị chuyển `failed` (hết số lần thử) trong lúc claim; câu xin lỗi gửi SAU commit.
    exhausted: tuple[int, ...] = ()


class BotInboxError(Exception):
    """Lỗi ghi hộp thư. Thông điệp KHÔNG bao giờ chứa nội dung tin.

    SQLAlchemy kèm cả tham số của câu lệnh lỗi (tức nội dung tin hay câu trả lời) vào thông điệp
    ngoại lệ, và log lỗi sẽ in ra. `transient` cho biết lỗi hạ tầng tạm thời (thử lại được).
    """

    def __init__(self, message: str, *, transient: bool = False) -> None:
        super().__init__(message)
        self.transient = transient


@contextmanager
def _without_content(operation: str, *, keep_transient: bool = False) -> Iterator[None]:
    """Đổi lỗi DB của một lệnh có nội dung thành `BotInboxError` không chứa tham số.

    `keep_transient`: để lỗi hạ tầng tạm thời đi qua nguyên vẹn khi người gọi (runner của webhook)
    tự phân loại và chỉ log tên lỗi.
    """
    try:
        yield
    except (OperationalError, InterfaceError) as exc:
        if keep_transient:
            raise
        raise BotInboxError(
            f"{operation} thất bại ({type(exc.orig or exc).__name__}).",
            transient=True,
        ) from None
    except DBAPIError as exc:
        raise BotInboxError(f"{operation} thất bại ({type(exc.orig or exc).__name__}).") from None


def _require_aware(value: datetime, name: str) -> None:
    # asyncpg coi datetime không múi giờ là giờ địa phương của tiến trình (đo ở S0(c)).
    if value.tzinfo is None:
        raise ValueError(f"{name} phải có múi giờ.")


class BotInbox:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def enqueue(
        self,
        *,
        update_id: int,
        chat_id: int,
        telegram_user_id: int,
        user_id: UUID,
        text: str,
    ) -> None:
        with _without_content("Ghi hộp thư", keep_transient=True):
            self.session.add(
                BotUpdate(
                    update_id=update_id,
                    chat_id=chat_id,
                    telegram_user_id=telegram_user_id,
                    user_id=user_id,
                    kind="text",
                    status="queued",
                    payload_text=text,
                ),
            )
            await self.session.flush()

    async def claim(
        self,
        chat_id: int,
        *,
        now: datetime,
        lease_seconds: float,
        max_attempts: int,
    ) -> ClaimResult:
        """Nhận dòng đầu hàng đợi của chat (một giao dịch ngắn; người gọi commit)."""
        _require_aware(now, "now")
        await self.session.execute(_SQL_LOCK, {"chat_id": chat_id})
        exhausted: list[int] = []
        while True:
            live = await self.session.execute(_SQL_LIVE, {"chat_id": chat_id, "now": now})
            if live.first() is not None:
                return ClaimResult(None, tuple(exhausted))
            head = (await self.session.execute(_SQL_HEAD, {"chat_id": chat_id})).first()
            if head is None:
                return ClaimResult(None, tuple(exhausted))
            # Đang chờ thử lại: chặn cả chat, không nhảy cóc sang dòng sau.
            if head.status == "queued" and head.lease_until is not None and head.lease_until > now:
                return ClaimResult(None, tuple(exhausted))
            if head.attempts >= max_attempts:
                await self.session.execute(_SQL_EXHAUST, {"id": head.update_id, "now": now})
                exhausted.append(head.update_id)
                continue
            taken = (
                await self.session.execute(
                    _SQL_TAKE,
                    {
                        "id": head.update_id,
                        "now": now,
                        "lease_until": now + timedelta(seconds=lease_seconds),
                    },
                )
            ).first()
            if taken is None:  # bị chen mất giữa lúc đọc và lúc nhận: đọc lại đầu hàng đợi
                continue
            return ClaimResult(
                ClaimedRow(
                    update_id=taken.update_id,
                    chat_id=taken.chat_id,
                    telegram_user_id=taken.telegram_user_id,
                    user_id=taken.user_id,
                    kind=taken.kind,
                    payload_text=taken.payload_text,
                    reply_text=taken.reply_text,
                    attempts=taken.attempts,
                    received_at=taken.received_at,
                    sent_parts=taken.sent_parts,
                ),
                tuple(exhausted),
            )

    async def save_reply(self, update_id: int, attempts: int, text_: str, *, now: datetime) -> bool:
        """Lưu câu trả lời trước khi gửi. `False` nếu dòng không còn thuộc về lần claim này."""
        _require_aware(now, "now")
        with _without_content("Lưu câu trả lời"):
            result = await self.session.execute(
                _SQL_SAVE_REPLY,
                {"id": update_id, "attempts": attempts, "text": text_, "now": now},
            )
        return bool(getattr(result, "rowcount", 0) == 1)

    async def save_sent_parts(self, update_id: int, attempts: int, parts: int) -> bool:
        """Ghi số phần đã gửi xong. `False` nếu dòng không còn thuộc về lần claim này."""
        result = await self.session.execute(
            _SQL_SAVE_SENT_PARTS,
            {"id": update_id, "attempts": attempts, "parts": parts},
        )
        return bool(getattr(result, "rowcount", 0) == 1)

    async def requeue(
        self,
        update_id: int,
        attempts: int,
        *,
        retry_at: datetime,
        now: datetime,
    ) -> bool:
        """Đưa dòng về `queued` chờ đến `retry_at`. `False` nếu không còn của lần claim này."""
        _require_aware(retry_at, "retry_at")
        _require_aware(now, "now")
        result = await self.session.execute(
            _SQL_REQUEUE,
            {"id": update_id, "attempts": attempts, "retry_at": retry_at},
        )
        return bool(getattr(result, "rowcount", 0) == 1)

    async def end(
        self,
        update_id: int,
        attempts: int,
        *,
        status: str,
        category: str,
        now: datetime,
    ) -> bool:
        """Kết thúc dòng bằng `failed` hoặc `dropped` kèm danh mục lỗi cố định."""
        if status not in ("failed", "dropped"):
            raise ValueError("status phải là failed hoặc dropped.")
        _require_aware(now, "now")
        result = await self.session.execute(
            _SQL_END,
            {
                "id": update_id,
                "attempts": attempts,
                "status": status,
                "category": category,
                "now": now,
            },
        )
        return bool(getattr(result, "rowcount", 0) == 1)

    async def release_lease(self, update_id: int, attempts: int, *, now: datetime) -> bool:
        """Nhả lease của dòng đang xử lý (worker bị hủy). `False` nếu không còn của lần claim."""
        _require_aware(now, "now")
        result = await self.session.execute(
            _SQL_RELEASE,
            {"id": update_id, "attempts": attempts, "now": now},
        )
        return bool(getattr(result, "rowcount", 0) == 1)

    async def pending_chats(
        self,
        *,
        now: datetime,
        stale_seconds: float,
        limit: int = 500,
    ) -> list[PendingChat]:
        """Các chat cần đánh chuông lại. Chỉ đọc: không đổi trạng thái dòng nào."""
        _require_aware(now, "now")
        result = await self.session.execute(
            _SQL_PENDING,
            {"now": now, "cutoff": now - timedelta(seconds=stale_seconds), "limit": limit},
        )
        return [PendingChat(row.chat_id, row.update_id) for row in result]

    async def delete_finished_before(self, cutoff: datetime) -> int:
        """Xóa dòng đã kết thúc (`replied`, `failed`, `dropped`) trước `cutoff`. Trả số dòng xóa."""
        _require_aware(cutoff, "cutoff")
        result = await self.session.execute(_SQL_DELETE_FINISHED, {"cutoff": cutoff})
        return int(getattr(result, "rowcount", 0) or 0)

    async def owns(self, update_id: int, attempts: int) -> bool:
        """Dòng còn `processing` và đúng lần claim này (kiểm lần cuối trước khi gửi)."""
        row = await self.session.execute(_SQL_OWNS, {"id": update_id, "attempts": attempts})
        return row.first() is not None

    async def complete(self, update_id: int, attempts: int, *, now: datetime) -> bool:
        """Đánh dấu đã trả lời và xóa nội dung. `False` nếu dòng đã thuộc về lần claim khác."""
        _require_aware(now, "now")
        result = await self.session.execute(
            _SQL_COMPLETE,
            {"id": update_id, "attempts": attempts, "now": now},
        )
        return bool(getattr(result, "rowcount", 0) == 1)
