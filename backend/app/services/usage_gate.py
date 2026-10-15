"""Cổng hạn mức sử dụng của chatbot (kế hoạch 5.1, mục 4.11, S10).

Cổng đứng ngay trước engine ở worker: đếm số lượt người dùng đã được trả lời trong ngày nghiệp vụ
(theo giờ Việt Nam, không theo UTC hay múi giờ máy chủ) và quyết định cho qua hay từ chối. Một
lượt thuộc ngày lúc câu trả lời được LƯU (chi phí phát sinh khi đó), cùng ngày mà cổng xét ở bước
kiểm: tin nhận 23:59 mà được trả lời 00:00:30 là lượt của ngày mới, nên không có lượt "miễn phí"
ở biên ngày.

Hai điều cổng **không** làm: không nhìn vai trò của người dùng (quản trị viên chịu cùng hạn mức như
mọi người, muốn khác thì ghi đè theo từng người ở `QuotaLimitSource`), và không khóa hay đếm nguyên
tử: mỗi chat chỉ chạy một dòng tại một thời điểm và mỗi người chỉ có một liên kết đang giữ nên các
bước "kiểm rồi mới làm" của một người luôn tuần tự (mục 4.11, điểm 5).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Any, Literal, Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

BUSINESS_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
# Tin có tệp (2C chưa có): ảnh và tài liệu. Dòng hộp thư hiện chỉ có `text`.
FILE_KINDS = frozenset({"photo", "document"})

_SQL_USAGE = text(
    """
    SELECT count(*) AS turns,
           count(*) FILTER (WHERE kind IN :file_kinds) AS files
      FROM bot_updates
     WHERE user_id = :user_id
       AND received_at >= :received_floor
       AND reply_saved_at >= :day_start AND reply_saved_at < :day_end
    """
).bindparams(bindparam("file_kinds", expanding=True))


def business_day_bounds(now: datetime) -> tuple[datetime, datetime]:
    """Đầu và cuối (UTC, nửa mở) của ngày nghiệp vụ chứa `now`.

    Tính ở Python rồi đổi sang UTC để truy vấn khoảng `received_at` dùng được chỉ mục; không dùng
    `received_at::date` vì kết quả phụ thuộc múi giờ của phiên DB.
    """
    if now.tzinfo is None:
        raise ValueError("`now` phải có múi giờ.")
    local = now.astimezone(BUSINESS_TIMEZONE)
    start = datetime.combine(local.date(), time.min, tzinfo=BUSINESS_TIMEZONE)
    end = datetime.combine(local.date() + timedelta(days=1), time.min, tzinfo=BUSINESS_TIMEZONE)
    return start.astimezone(UTC), end.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class QuotaLimits:
    """Hạn mức mỗi ngày của một người; `0` là không giới hạn loại đó."""

    turns: int
    files: int


class QuotaLimitSource(Protocol):
    """Nơi quyết định hạn mức của một người (5.6 thêm ghi đè theo người, mặc định hệ thống)."""

    async def limits_for(self, session: AsyncSession, user_id: UUID) -> QuotaLimits: ...


@dataclass(frozen=True, slots=True)
class FixedQuotaLimits:
    """Cùng một hạn mức cho mọi người (tầng biến môi trường của 5.1)."""

    limits: QuotaLimits

    async def limits_for(self, session: AsyncSession, user_id: UUID) -> QuotaLimits:
        return self.limits


@dataclass(frozen=True, slots=True)
class QuotaDecision:
    """Kết quả kiểm trước một lượt. Các số `*_used` là số lượt đã dùng TRƯỚC lượt này."""

    allowed: bool
    # Hạn mức làm cổng từ chối: "turns" hoặc "files" (None khi cho qua).
    reason: Literal["turns", "files"] | None
    used: int
    limit: int
    resets_at: datetime
    turns_used: int
    turns_limit: int
    files_used: int
    files_limit: int


@dataclass(frozen=True, slots=True)
class QuotaSummary:
    turns_used: int
    turns_limit: int
    files_used: int
    files_limit: int
    resets_at: datetime


class UsageGate(Protocol):
    async def check(
        self, session: AsyncSession, user_id: UUID, kind: str, *, now: datetime
    ) -> QuotaDecision: ...

    async def summary(
        self, session: AsyncSession, user_id: UUID, *, now: datetime
    ) -> QuotaSummary: ...


class TurnLimitGate:
    """Đếm lượt và lượt dùng tệp từ `bot_updates`."""

    def __init__(self, limits: QuotaLimitSource) -> None:
        self._limits = limits

    @property
    def limits(self) -> QuotaLimitSource:
        """Nơi quyết định hạn mức của từng người (để kiểm tra cấu hình đã vào đúng chỗ)."""
        return self._limits

    @classmethod
    def from_settings(cls, settings: Any) -> TurnLimitGate:
        return cls(
            FixedQuotaLimits(
                QuotaLimits(
                    turns=settings.bot_daily_turn_limit,
                    files=settings.bot_daily_file_limit,
                )
            )
        )

    async def _usage(
        self, session: AsyncSession, user_id: UUID, now: datetime
    ) -> tuple[int, int, datetime]:
        day_start, day_end = business_day_bounds(now)
        row = (
            await session.execute(
                _SQL_USAGE,
                {
                    "user_id": user_id,
                    "day_start": day_start,
                    "day_end": day_end,
                    # Cận dưới theo `received_at` chỉ để dùng chỉ mục (user, received_at): câu
                    # trả lời lưu trong ngày không thể thuộc tin nhận từ trước đó cả ngày.
                    "received_floor": day_start - timedelta(days=1),
                    "file_kinds": sorted(FILE_KINDS),
                },
            )
        ).one()
        return int(row.turns), int(row.files), day_end.astimezone(BUSINESS_TIMEZONE)

    async def check(
        self, session: AsyncSession, user_id: UUID, kind: str, *, now: datetime
    ) -> QuotaDecision:
        limits = await self._limits.limits_for(session, user_id)
        turns, files, resets_at = await self._usage(session, user_id, now)
        reason: Literal["turns", "files"] | None = None
        used, limit = turns, limits.turns
        if limits.turns > 0 and turns >= limits.turns:
            reason = "turns"
        elif kind in FILE_KINDS and limits.files > 0 and files >= limits.files:
            reason, used, limit = "files", files, limits.files
        return QuotaDecision(
            allowed=reason is None,
            reason=reason,
            used=used,
            limit=limit,
            resets_at=resets_at,
            turns_used=turns,
            turns_limit=limits.turns,
            files_used=files,
            files_limit=limits.files,
        )

    async def summary(self, session: AsyncSession, user_id: UUID, *, now: datetime) -> QuotaSummary:
        limits = await self._limits.limits_for(session, user_id)
        turns, files, resets_at = await self._usage(session, user_id, now)
        return QuotaSummary(turns, limits.turns, files, limits.files, resets_at)
