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
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    PriceAlertEvent,
    PriceAlertMessage,
    PriceAlertScanState,
    PriceAlertSetting,
    Quote,
    QuoteVersion,
)

logger = logging.getLogger(__name__)

FAILED_WINDOW = timedelta(hours=24)


@dataclass(frozen=True, slots=True)
class PriceAlertSnapshot:
    enabled: bool
    scan_lag_seconds: float | None = None
    watermark_lag_seconds: float | None = None
    messages: dict[str, int] = field(default_factory=dict)
    oldest_pending_age_seconds: float | None = None
    anomalies_pending: int | None = None


class PriceAlertMetrics:
    """Số đo của engine thông báo giá, tính khi Prometheus scrape (M10).

    Worker không có cổng metric nên backend đọc thẳng DB: vài truy vấn đếm nhẹ, cache `ttl_seconds`
    giữa các lần scrape, có hạn chờ; lỗi chỉ làm `quotify_price_alert_metrics_up` về 0 và không
    bao giờ làm hỏng `/metrics`.
    """

    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
        *,
        ttl_seconds: float = 15.0,
        timeout_seconds: float = 2.0,
        clock: Callable[[], float] = time.monotonic,
        telegram_enabled: Callable[[], bool] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._telegram_enabled = telegram_enabled or _telegram_enabled_from_settings
        self._ttl = ttl_seconds
        self._timeout = timeout_seconds
        self._clock = clock
        self._refreshed_at: float | None = None
        self.snapshot: PriceAlertSnapshot | None = None
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
            logger.warning("price_alert.metrics_failed error=%s", type(exc).__name__)
            self.snapshot = None
            self.ok = False
        self._refreshed_at = self._clock()

    async def _load(self, now: datetime) -> PriceAlertSnapshot:
        async with self._session_factory() as session:
            enabled = bool(
                (await session.execute(select(PriceAlertSetting.is_enabled))).scalar_one_or_none()
            )
            # `TELEGRAM_ENABLED=false` dừng cron quét: coi như engine không chạy, không báo nhầm.
            if not enabled or not self._telegram_enabled():
                return PriceAlertSnapshot(enabled=False)

            state = (
                await session.execute(
                    select(
                        PriceAlertScanState.last_run_at,
                        PriceAlertScanState.watermark_confirmed_at,
                    )
                )
            ).first()
            last_run, watermark = state if state else (None, None)

            count_rows = (
                await session.execute(
                    select(PriceAlertMessage.status, func.count())
                    .where(PriceAlertMessage.status.in_(("pending", "sending")))
                    .group_by(PriceAlertMessage.status)
                )
            ).all()
            counts: dict[str, int] = {row[0]: int(row[1]) for row in count_rows}
            failed = (
                await session.execute(
                    select(func.count()).where(
                        PriceAlertMessage.status == "failed",
                        PriceAlertMessage.created_at >= now - FAILED_WINDOW,
                    )
                )
            ).scalar_one()
            oldest = (
                await session.execute(
                    select(func.min(PriceAlertMessage.created_at)).where(
                        PriceAlertMessage.status == "pending"
                    )
                )
            ).scalar_one()
            anomalies = (
                await session.execute(
                    select(func.count())
                    .select_from(PriceAlertEvent)
                    .join(QuoteVersion, QuoteVersion.id == PriceAlertEvent.quote_version_id)
                    .join(Quote, Quote.id == QuoteVersion.quote_id)
                    .where(
                        PriceAlertEvent.kind == "anomaly",
                        PriceAlertEvent.review_status == "pending",
                        PriceAlertEvent.attached_to_event_id.is_(None),
                        Quote.cancelled_at.is_(None),
                    )
                )
            ).scalar_one()

        return PriceAlertSnapshot(
            enabled=True,
            scan_lag_seconds=_age(now, last_run),
            watermark_lag_seconds=_age(now, watermark),
            messages={
                "pending": int(counts.get("pending", 0)),
                "sending": int(counts.get("sending", 0)),
                "failed": int(failed),
            },
            oldest_pending_age_seconds=_age(now, oldest),
            anomalies_pending=int(anomalies),
        )


def _telegram_enabled_from_settings() -> bool:
    from app.core.config import get_settings

    return bool(get_settings().telegram_enabled)


def _age(now: datetime, moment: datetime | None) -> float | None:
    return None if moment is None else max((now - moment).total_seconds(), 0.0)


_active: PriceAlertMetrics | None = None
_registered = False


def set_active_metrics(metrics: PriceAlertMetrics | None) -> None:
    """Chọn nguồn số đo cho collector toàn cục và đăng ký collector đúng một lần."""
    global _active, _registered
    _active = metrics
    if not _registered:
        REGISTRY.register(_PriceAlertCollector())
        _registered = True


class _PriceAlertCollector(Collector):
    def collect(self) -> Iterator[Any]:
        metrics = _active
        if metrics is None:
            return
        up = GaugeMetricFamily(
            "quotify_price_alert_metrics_up",
            "1 nếu lần đọc DB gần nhất cho số đo thông báo giá thành công.",
            value=1.0 if metrics.ok else 0.0,
        )
        yield up
        snapshot = metrics.snapshot
        if snapshot is None:
            return
        yield GaugeMetricFamily(
            "quotify_price_alert_enabled",
            "1 nếu thông báo biến động giá đang bật.",
            value=1.0 if snapshot.enabled else 0.0,
        )
        if not snapshot.enabled:
            return
        if snapshot.scan_lag_seconds is not None:
            yield GaugeMetricFamily(
                "quotify_price_alert_scan_lag_seconds",
                "Giây kể từ nhịp tim quét gần nhất.",
                value=snapshot.scan_lag_seconds,
            )
        if snapshot.watermark_lag_seconds is not None:
            yield GaugeMetricFamily(
                "quotify_price_alert_watermark_lag_seconds",
                "Giây kể từ mốc phiếu đã quét tới.",
                value=snapshot.watermark_lag_seconds,
            )
        messages = GaugeMetricFamily(
            "quotify_price_alert_messages",
            "Số tin: pending, sending (hiện tại) và failed (24 giờ gần nhất).",
            labels=["status"],
        )
        for status, count in snapshot.messages.items():
            messages.add_metric([status], float(count))
        yield messages
        if snapshot.oldest_pending_age_seconds is not None:
            yield GaugeMetricFamily(
                "quotify_price_alert_oldest_pending_message_age_seconds",
                "Tuổi của tin pending cũ nhất.",
                value=snapshot.oldest_pending_age_seconds,
            )
        if snapshot.anomalies_pending is not None:
            yield GaugeMetricFamily(
                "quotify_price_alert_anomalies_pending",
                "Số thẻ giá bất thường gốc đang chờ duyệt.",
                value=float(snapshot.anomalies_pending),
            )
