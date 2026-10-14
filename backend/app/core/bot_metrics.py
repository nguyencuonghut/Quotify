"""Số đo của chatbot, tính khi Prometheus scrape (kế hoạch 5.1, mục 4.9 và KT12).

Worker bot không có cổng metric và Prometheus chỉ scrape backend, nên backend đọc thẳng hộp thư
`bot_updates`: vài truy vấn đếm nhẹ, cache `ttl_seconds` giữa các lần scrape, có hạn chờ; lỗi chỉ
làm `quotify_bot_metrics_up` về 0 và không bao giờ làm hỏng `/metrics`. Chỉ có số liệu về hàng đợi
(không bao giờ có nội dung tin) nên không có gì nhạy cảm để lộ.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from prometheus_client import REGISTRY
from prometheus_client.core import GaugeMetricFamily
from prometheus_client.registry import Collector
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bot_update import BOT_UPDATE_OPEN_STATUSES, BotUpdate

logger = logging.getLogger(__name__)

# Dòng đã kết thúc chỉ tính trong cửa sổ này; dòng đang mở (`queued`, `processing`) tính dù cũ.
WINDOW = timedelta(hours=24)
STATUSES = ("queued", "processing", "replied", "failed", "dropped")
# Cảnh báo lỗi nhìn vào cửa sổ ngắn này thay vì mức của gauge 24 giờ: gauge 24 giờ vừa tăng vừa giảm
# khi dòng cũ rơi khỏi cửa sổ nên `delta` có thể bỏ sót hay báo trễ một lỗi mới.
RECENT_FAILURE_WINDOW = timedelta(minutes=30)


@dataclass(frozen=True, slots=True)
class BotSnapshot:
    enabled: bool
    updates: dict[str, int] = field(default_factory=dict)
    queued_oldest_age_seconds: float | None = None
    quota_denied: int | None = None
    recent_failures: int | None = None


class BotMetrics:
    """Số đo hộp thư chatbot. Chatbot tắt thì chỉ báo `enabled=0`: dòng còn nằm lại hộp thư sau khi
    tắt công tắc khẩn cấp không được làm cảnh báo "hàng đợi kẹt" nổ mãi."""

    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
        *,
        ttl_seconds: float = 15.0,
        timeout_seconds: float = 2.0,
        clock: Callable[[], float] = time.monotonic,
        chatbot_enabled: Callable[[], bool] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._chatbot_enabled = chatbot_enabled or _chatbot_enabled_from_settings
        self._ttl = ttl_seconds
        self._timeout = timeout_seconds
        self._clock = clock
        self._refreshed_at: float | None = None
        self.snapshot: BotSnapshot | None = None
        self.ok = False

    async def refresh(self, now: datetime | None = None) -> None:
        if (
            self._ttl > 0
            and self._refreshed_at is not None
            and self._clock() - self._refreshed_at < self._ttl
        ):
            return
        moment = now or datetime.now(UTC)
        try:
            self.snapshot = await asyncio.wait_for(self._load(moment), self._timeout)
            self.ok = True
        except Exception as exc:
            logger.warning("bot.metrics_failed error=%s", type(exc).__name__)
            self.snapshot = None
            self.ok = False
        self._refreshed_at = self._clock()

    async def _load(self, now: datetime) -> BotSnapshot:
        # Nạp trễ: `app.services` kéo theo `app.auth` rồi `app.db.session`, mà `app.db.session` lại
        # nạp `app.core.observability` rồi module này (cùng lý do với `price_alert_metrics`).
        from app.services.bot_inbox import BotInbox

        if not self._chatbot_enabled():
            return BotSnapshot(enabled=False)
        async with self._session_factory() as session:
            rows = (
                await session.execute(
                    select(BotUpdate.status, func.count())
                    .where(
                        or_(
                            BotUpdate.status.in_(BOT_UPDATE_OPEN_STATUSES),
                            BotUpdate.received_at >= now - WINDOW,
                        )
                    )
                    .group_by(BotUpdate.status)
                )
            ).all()
            counts = {row[0]: int(row[1]) for row in rows}
            oldest = await BotInbox(session).oldest_claimable_received_at(now=now)
            quota_denied = (
                await session.execute(
                    select(func.count()).where(
                        and_(
                            BotUpdate.status == "dropped",
                            BotUpdate.error_category == "quota_exceeded",
                            BotUpdate.received_at >= now - WINDOW,
                        )
                    )
                )
            ).scalar_one()
            recent_failures = (
                await session.execute(
                    select(func.count()).where(
                        BotUpdate.status == "failed",
                        BotUpdate.finished_at >= now - RECENT_FAILURE_WINDOW,
                    )
                )
            ).scalar_one()
        return BotSnapshot(
            enabled=True,
            updates={status: counts.get(status, 0) for status in STATUSES},
            queued_oldest_age_seconds=_age(now, oldest),
            quota_denied=int(quota_denied),
            recent_failures=int(recent_failures),
        )


def _chatbot_enabled_from_settings() -> bool:
    from app.core.config import get_settings
    from app.services.bot_policy import ChatbotPolicy

    return ChatbotPolicy.from_settings(get_settings()).enabled


def _age(now: datetime, moment: datetime | None) -> float | None:
    return None if moment is None else max((now - moment).total_seconds(), 0.0)


_active: BotMetrics | None = None
_registered = False


def set_active_bot_metrics(metrics: BotMetrics | None) -> None:
    """Chọn nguồn số đo cho collector toàn cục và đăng ký collector đúng một lần."""
    global _active, _registered
    _active = metrics
    if not _registered:
        REGISTRY.register(_BotCollector())
        _registered = True


class _BotCollector(Collector):
    def collect(self) -> Iterator[Any]:
        metrics = _active
        if metrics is None:
            return
        yield GaugeMetricFamily(
            "quotify_bot_metrics_up",
            "1 nếu lần đọc DB gần nhất cho số đo chatbot thành công.",
            value=1.0 if metrics.ok else 0.0,
        )
        snapshot = metrics.snapshot
        if snapshot is None:
            return
        yield GaugeMetricFamily(
            "quotify_bot_enabled",
            "1 nếu chatbot đang bật (cờ môi trường và Telegram).",
            value=1.0 if snapshot.enabled else 0.0,
        )
        if not snapshot.enabled:
            return
        updates = GaugeMetricFamily(
            "quotify_bot_updates",
            "Số dòng hộp thư theo trạng thái: queued và processing (hiện tại), còn lại 24 giờ qua.",
            labels=["status"],
        )
        for status, count in snapshot.updates.items():
            updates.add_metric([status], float(count))
        yield updates
        if snapshot.queued_oldest_age_seconds is not None:
            yield GaugeMetricFamily(
                "quotify_bot_queued_oldest_age_seconds",
                "Tuổi của dòng claim được cũ nhất (không tính dòng xếp sau dòng đang chạy).",
                value=snapshot.queued_oldest_age_seconds,
            )
        if snapshot.recent_failures is not None:
            yield GaugeMetricFamily(
                "quotify_bot_recent_failures",
                "Số dòng failed kết thúc trong 30 phút qua (cơ sở của cảnh báo lỗi).",
                value=float(snapshot.recent_failures),
            )
        if snapshot.quota_denied is not None:
            yield GaugeMetricFamily(
                "quotify_bot_quota_denied",
                "Số dòng bị từ chối vì hết hạn mức trong 24 giờ qua.",
                value=float(snapshot.quota_denied),
            )
