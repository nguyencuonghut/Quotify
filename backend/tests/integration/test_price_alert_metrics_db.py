"""Metric của thông báo giá tính khi Prometheus scrape, trên PostgreSQL thật (1C, Slice 7, M10)."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta

import pytest
from db_helpers import create_material, create_priced_line, ensure_role
from price_alert_scene import Scene
from prometheus_client import generate_latest
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from test_price_alert_anomaly_messages_db import flag, new_run, scene  # noqa: F401

from app.core.price_alert_metrics import PriceAlertMetrics, set_active_metrics
from app.models import (
    PriceAlertMessage,
    PriceAlertScanState,
    PriceAlertSetting,
    PriceFreshnessMaterial,
)

pytestmark = pytest.mark.integration

NOW = datetime(2056, 1, 10, 3, 0, tzinfo=UTC)


def value_of(name: str, labels: str = "") -> float | None:
    pattern = rf"^{name}{re.escape(labels)} ([0-9.eE+-]+)$"
    for line in generate_latest().decode().splitlines():
        match = re.match(pattern, line)
        if match:
            return float(match.group(1))
    return None


@pytest.fixture
async def metrics(
    scene: Scene,  # noqa: F811
    session_factory: async_sessionmaker[AsyncSession],
):
    await ensure_role(session_factory, "it-manager", ["price_alerts.receive_all"])
    instance = PriceAlertMetrics(session_factory, ttl_seconds=0, telegram_enabled=lambda: True)
    set_active_metrics(instance)
    yield instance
    set_active_metrics(None)


async def configure(
    sf: async_sessionmaker[AsyncSession], *, enabled: bool, last_run: datetime | None
) -> None:
    async with sf() as session:
        await session.execute(update(PriceAlertSetting).values(is_enabled=enabled))
        await session.execute(
            update(PriceAlertScanState).values(
                last_run_at=last_run,
                watermark_confirmed_at=None
                if last_run is None
                else last_run - timedelta(minutes=7),
            )
        )
        await session.commit()


async def add_message(
    sf: async_sessionmaker[AsyncSession],
    scene: Scene,  # noqa: F811
    *,
    status: str,
    age_minutes: int,
) -> None:
    user = await scene.person("it-manager")
    async with sf() as session:
        session.add(
            PriceAlertMessage(
                user_id=user,
                material_id=scene.material,
                local_date=date(2056, 1, 10),
                kind="change",
                level_max="large",
                direction="up",
                status=status,
                scan_run_id=None,
                created_at=NOW - timedelta(minutes=age_minutes),
            )
        )
        await session.commit()


async def test_scan_lag_is_the_age_of_the_last_heartbeat_while_the_feature_is_on(
    scene: Scene,  # noqa: F811
    metrics: PriceAlertMetrics,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await configure(session_factory, enabled=True, last_run=NOW - timedelta(minutes=3))

    await metrics.refresh(now=NOW)

    assert value_of("quotify_price_alert_enabled") == 1
    assert value_of("quotify_price_alert_scan_lag_seconds") == pytest.approx(180, abs=1)
    assert value_of("quotify_price_alert_watermark_lag_seconds") == pytest.approx(180 + 420, abs=1)
    assert value_of("quotify_price_alert_metrics_up") == 1


async def test_nothing_about_the_engine_is_published_while_the_feature_is_off(
    scene: Scene,  # noqa: F811
    metrics: PriceAlertMetrics,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await configure(session_factory, enabled=False, last_run=NOW - timedelta(minutes=30))

    await metrics.refresh(now=NOW)

    assert value_of("quotify_price_alert_enabled") == 0
    assert value_of("quotify_price_alert_scan_lag_seconds") is None
    assert value_of("quotify_price_alert_messages", '{status="pending"}') is None
    assert value_of("quotify_price_alert_anomalies_pending") is None


async def test_a_feature_that_never_ran_has_no_lag_to_report(
    scene: Scene,  # noqa: F811
    metrics: PriceAlertMetrics,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await configure(session_factory, enabled=True, last_run=None)

    await metrics.refresh(now=NOW)

    assert value_of("quotify_price_alert_enabled") == 1
    assert value_of("quotify_price_alert_scan_lag_seconds") is None


async def test_message_gauges_count_pending_sending_and_recent_failures(
    scene: Scene,  # noqa: F811
    metrics: PriceAlertMetrics,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await configure(session_factory, enabled=True, last_run=NOW)
    await metrics.refresh(now=NOW)
    before = {
        status: value_of("quotify_price_alert_messages", f'{{status="{status}"}}') or 0
        for status in ("pending", "sending", "failed")
    }
    await add_message(session_factory, scene, status="pending", age_minutes=20)
    await add_message(session_factory, scene, status="pending", age_minutes=1)
    await add_message(session_factory, scene, status="sending", age_minutes=2)
    await add_message(session_factory, scene, status="failed", age_minutes=60)
    await add_message(session_factory, scene, status="failed", age_minutes=60 * 30)
    await add_message(session_factory, scene, status="sent", age_minutes=5)

    await metrics.refresh(now=NOW)

    def delta(status: str) -> float:
        now_value = value_of("quotify_price_alert_messages", f'{{status="{status}"}}')
        assert now_value is not None
        return now_value - before[status]

    assert (delta("pending"), delta("sending"), delta("failed")) == (2, 1, 1)
    assert (value_of("quotify_price_alert_oldest_pending_message_age_seconds") or 0) >= 20 * 60


async def test_pending_anomaly_cards_are_counted_without_their_attached_points(
    scene: Scene,  # noqa: F811
    metrics: PriceAlertMetrics,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await configure(session_factory, enabled=True, last_run=NOW)
    await metrics.refresh(now=NOW)
    before = value_of("quotify_price_alert_anomalies_pending") or 0
    run = await new_run(session_factory)
    card = await flag(session_factory, run, scene.material, None)
    await flag(session_factory, run, scene.material, None, attached_to=card, price=980)

    await metrics.refresh(now=NOW)

    assert (value_of("quotify_price_alert_anomalies_pending") or 0) - before == 1


async def test_a_database_failure_keeps_the_scrape_alive_and_flags_the_metrics_as_down(
    scene: Scene,  # noqa: F811
) -> None:
    def broken_factory() -> AsyncSession:
        raise RuntimeError("database down")

    instance = PriceAlertMetrics(broken_factory, ttl_seconds=0)  # type: ignore[arg-type]
    set_active_metrics(instance)
    try:
        await instance.refresh(now=NOW)

        assert value_of("quotify_price_alert_metrics_up") == 0
        assert value_of("quotify_price_alert_scan_lag_seconds") is None
    finally:
        set_active_metrics(None)


async def test_results_are_cached_for_the_ttl_so_scrapes_stay_cheap(
    scene: Scene,  # noqa: F811
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    calls = 0

    def counting_factory() -> AsyncSession:
        nonlocal calls
        calls += 1
        return session_factory()

    instance = PriceAlertMetrics(
        counting_factory, ttl_seconds=15, clock=lambda: 100.0, telegram_enabled=lambda: True
    )  # type: ignore[arg-type]

    await instance.refresh(now=NOW)
    first = calls
    await instance.refresh(now=NOW)

    assert first >= 1 and calls == first


async def test_after_a_failure_the_old_numbers_are_not_served_as_if_they_were_fresh(
    scene: Scene,  # noqa: F811
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await configure(session_factory, enabled=True, last_run=NOW)
    down = False

    def flaky_factory() -> AsyncSession:
        if down:
            raise RuntimeError("database down")
        return session_factory()

    instance = PriceAlertMetrics(flaky_factory, ttl_seconds=0, telegram_enabled=lambda: True)  # type: ignore[arg-type]
    set_active_metrics(instance)
    try:
        await instance.refresh(now=NOW)
        assert value_of("quotify_price_alert_scan_lag_seconds") is not None

        down = True
        await instance.refresh(now=NOW)

        assert value_of("quotify_price_alert_metrics_up") == 0
        assert value_of("quotify_price_alert_scan_lag_seconds") is None
    finally:
        set_active_metrics(None)


async def test_with_telegram_switched_off_the_stopped_scan_does_not_page_anyone(
    scene: Scene,  # noqa: F811
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """TELEGRAM_ENABLED=false dừng cron quét: không được báo "quét ngừng" như một sự cố."""
    await configure(session_factory, enabled=True, last_run=NOW - timedelta(hours=2))
    instance = PriceAlertMetrics(session_factory, ttl_seconds=0, telegram_enabled=lambda: False)
    set_active_metrics(instance)
    try:
        await instance.refresh(now=NOW)

        assert value_of("quotify_price_alert_enabled") == 0
        assert value_of("quotify_price_alert_scan_lag_seconds") is None
    finally:
        set_active_metrics(None)


async def _watch(
    sf: async_sessionmaker[AsyncSession],
    material_id: object,
    *,
    watched: bool = True,
    interval: int = 7,
) -> None:
    async with sf() as session:
        session.add(
            PriceFreshnessMaterial(
                material_id=material_id,
                is_watched=watched,
                expected_interval_days=interval,
            )
        )
        await session.commit()


async def test_freshness_gauges_count_watched_and_overdue_materials(
    scene: Scene,  # noqa: F811
    metrics: PriceAlertMetrics,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await configure(session_factory, enabled=True, last_run=NOW)
    async with session_factory() as session:
        await session.execute(delete(PriceFreshnessMaterial))
        await session.commit()
    today = NOW.date()  # 10/01/2056, 10:00 giờ Việt Nam
    fresh, overdue, never, off = [await create_material(session_factory) for _ in range(4)]
    for material in (fresh, overdue, never):
        await _watch(session_factory, material)
    await _watch(session_factory, off, watched=False)
    await create_priced_line(
        session_factory, material_id=fresh, price=1, received_date=today - timedelta(days=1)
    )
    await create_priced_line(
        session_factory, material_id=overdue, price=1, received_date=today - timedelta(days=20)
    )
    await create_priced_line(
        session_factory, material_id=off, price=1, received_date=today - timedelta(days=20)
    )

    await metrics.refresh(now=NOW)

    assert value_of("quotify_price_freshness_watched_materials") == 3
    # Quá hạn gồm cả vật tư theo dõi mà chưa từng có giá, giống thẻ "Quá hạn" trên Dashboard.
    assert value_of("quotify_price_freshness_overdue_materials") == 2


async def test_freshness_gauges_are_zero_without_any_watch_config(
    scene: Scene,  # noqa: F811
    metrics: PriceAlertMetrics,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await configure(session_factory, enabled=True, last_run=NOW)
    async with session_factory() as session:
        await session.execute(delete(PriceFreshnessMaterial))
        await session.commit()

    await metrics.refresh(now=NOW)

    assert value_of("quotify_price_freshness_watched_materials") == 0
    assert value_of("quotify_price_freshness_overdue_materials") == 0


async def test_freshness_gauges_are_not_published_while_the_feature_is_off(
    scene: Scene,  # noqa: F811
    metrics: PriceAlertMetrics,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await configure(session_factory, enabled=False, last_run=NOW)

    await metrics.refresh(now=NOW)

    assert value_of("quotify_price_freshness_watched_materials") is None
    assert value_of("quotify_price_freshness_overdue_materials") is None


async def test_a_failing_freshness_query_does_not_take_the_engine_gauges_down(
    scene: Scene,  # noqa: F811
    metrics: PriceAlertMetrics,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.quotify_material_freshness_service import QuotifyMaterialFreshnessService

    async def broken(*args: object, **kwargs: object) -> None:
        raise RuntimeError("freshness query failed")

    monkeypatch.setattr(QuotifyMaterialFreshnessService, "get_material_freshness", broken)
    await configure(session_factory, enabled=True, last_run=NOW - timedelta(minutes=3))

    await metrics.refresh(now=NOW)

    assert value_of("quotify_price_alert_metrics_up") == 1
    assert value_of("quotify_price_alert_scan_lag_seconds") == pytest.approx(180, abs=1)
    assert value_of("quotify_price_freshness_watched_materials") is None
    assert value_of("quotify_price_freshness_overdue_materials") is None


@pytest.fixture(autouse=True)
async def _clean_watch_list_after(
    session_factory: async_sessionmaker[AsyncSession],
):
    """Các test độ mới của giá xóa cả bảng cấu hình theo dõi; dọn lại để không rò sang test khác."""
    yield
    async with session_factory() as session:
        await session.execute(delete(PriceFreshnessMaterial))
        await session.commit()
