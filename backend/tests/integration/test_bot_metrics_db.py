"""Số đo của chatbot tính khi Prometheus scrape, trên PostgreSQL thật (kế hoạch 5.1, S7, KT12).

Worker không có cổng metric nên backend đọc thẳng hộp thư `bot_updates`. DB tạm dùng chung cả phiên
test nên mỗi test bắt đầu từ hộp thư trống.
"""

from __future__ import annotations

import asyncio
import re
import time
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from db_helpers import create_user, next_telegram_id, next_update_id
from fastapi import FastAPI
from prometheus_client import generate_latest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import bot_metrics as bot_metrics_module
from app.core.bot_metrics import BotMetrics, set_active_bot_metrics
from app.core.config import Settings
from app.core.observability import install_observability
from app.core.price_alert_metrics import set_active_metrics
from app.services.bot_inbox import BotInbox

NOW = datetime(2026, 10, 14, 3, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
async def _empty_inbox(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[None]:
    async with session_factory() as session:
        await session.execute(text("delete from bot_updates"))
        await session.commit()
    yield


async def _insert(
    sf: async_sessionmaker[AsyncSession],
    *,
    status: str = "queued",
    chat_id: int | None = None,
    user_id: uuid.UUID | None = None,
    received_ago: float = 0,
    finished_ago: float = 0,
    lease_in: float | None = None,
    error_category: str | None = None,
    base: datetime = NOW,
) -> int:
    """Chèn một dòng ở trạng thái tùy ý. `lease_in` là số giây từ `base` đến `lease_until`.

    `base` mặc định là `NOW` cố định; test đi qua route `/metrics` (giờ thật) phải truyền giờ thật.
    """
    update_id = next_update_id()
    chat = chat_id if chat_id is not None else next_telegram_id()
    owner = user_id if user_id is not None else await create_user(sf)
    async with sf() as session:
        await session.execute(
            text(
                "insert into bot_updates (update_id, chat_id, telegram_user_id, user_id, status, "
                "lease_until, received_at, error_category, finished_at) "
                "values (:id, :chat, :chat, :user, :status, :lease, :received, :category, "
                ":finished)"
            ),
            {
                "id": update_id,
                "chat": chat,
                "user": owner,
                "status": status,
                "lease": None if lease_in is None else base + timedelta(seconds=lease_in),
                "received": base - timedelta(seconds=received_ago),
                "category": error_category,
                "finished": base - timedelta(seconds=finished_ago)
                if status in ("replied", "failed", "dropped")
                else None,
            },
        )
        await session.commit()
    return update_id


async def _oldest(sf: async_sessionmaker[AsyncSession]) -> datetime | None:
    async with sf() as session:
        return await BotInbox(session).oldest_claimable_received_at(now=NOW)


async def test_an_empty_inbox_has_no_claimable_row(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    assert await _oldest(session_factory) is None


async def test_a_fresh_queued_row_is_claimable_and_the_oldest_of_several_wins(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _insert(session_factory, received_ago=30)
    await _insert(session_factory, received_ago=300)  # cũ nhất
    await _insert(session_factory, received_ago=5)

    assert await _oldest(session_factory) == NOW - timedelta(seconds=300)


async def test_rows_waiting_behind_a_live_run_or_a_retry_backoff_are_not_claimable(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user = await create_user(session_factory)
    busy_chat, waiting_chat = next_telegram_id(), next_telegram_id()
    await _insert(
        session_factory,
        status="processing",
        chat_id=busy_chat,
        user_id=user,
        received_ago=500,
        lease_in=120,  # đang chạy, lease còn hạn
    )
    await _insert(session_factory, chat_id=busy_chat, user_id=user, received_ago=400)  # xếp sau
    await _insert(
        session_factory,
        chat_id=waiting_chat,
        user_id=user,
        received_ago=300,
        lease_in=60,  # đang chờ thử lại (backoff)
    )
    await _insert(session_factory, chat_id=waiting_chat, user_id=user, received_ago=200)

    assert await _oldest(session_factory) is None  # hàng chờ hợp lệ không làm cảnh báo nổ oan


async def test_an_expired_lease_and_a_retry_that_is_due_are_claimable_again(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _insert(session_factory, status="processing", received_ago=700, lease_in=-1)
    await _insert(session_factory, received_ago=500, lease_in=-30)  # queued, đến hạn thử lại

    assert await _oldest(session_factory) == NOW - timedelta(seconds=700)


async def test_finished_rows_are_never_claimable(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    for status in ("replied", "failed", "dropped"):
        await _insert(session_factory, status=status, received_ago=900)

    assert await _oldest(session_factory) is None


@pytest.mark.parametrize(
    "rows",
    [
        [],
        [{"received_ago": 40}],
        [{"status": "processing", "received_ago": 40, "lease_in": 100}],
        [{"status": "processing", "received_ago": 40, "lease_in": -100}],
        [{"received_ago": 40, "lease_in": 100}],
        [{"received_ago": 40, "lease_in": -100}],
        [{"status": "replied", "received_ago": 40}],
    ],
)
async def test_the_metric_and_the_sweep_agree_on_which_chats_need_attention(
    session_factory: async_sessionmaker[AsyncSession],
    rows: list[dict[str, object]],
) -> None:
    for row in rows:
        await _insert(session_factory, **row)  # type: ignore[arg-type]

    async with session_factory() as session:
        inbox = BotInbox(session)
        swept = await inbox.pending_chats(now=NOW, stale_seconds=0)
        oldest = await inbox.oldest_claimable_received_at(now=NOW)

    assert (oldest is not None) == bool(swept)


# --- số đo tính lúc scrape -----------------------------------------------------------------------


def value_of(name: str, labels: str = "") -> float | None:
    pattern = rf"^{name}{re.escape(labels)} ([0-9.eE+-]+)$"
    for line in generate_latest().decode().splitlines():
        match = re.match(pattern, line)
        if match:
            return float(match.group(1))
    return None


@pytest.fixture
async def metrics(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[BotMetrics]:
    instance = BotMetrics(session_factory, ttl_seconds=0, chatbot_enabled=lambda: True)
    set_active_bot_metrics(instance)
    yield instance
    set_active_bot_metrics(None)


async def test_updates_are_counted_by_status_with_open_rows_of_any_age_and_finished_ones_of_24h(
    session_factory: async_sessionmaker[AsyncSession],
    metrics: BotMetrics,
) -> None:
    await _insert(session_factory, status="queued", received_ago=3 * 86400)  # mở: tính dù cũ
    await _insert(session_factory, status="processing", received_ago=60, lease_in=100)
    await _insert(session_factory, status="replied", received_ago=3600)
    await _insert(session_factory, status="replied", received_ago=2 * 3600)
    await _insert(session_factory, status="replied", received_ago=23 * 3600 + 50 * 60)  # sát biên
    await _insert(session_factory, status="replied", received_ago=24 * 3600 + 10 * 60)  # vừa quá
    await _insert(session_factory, status="replied", received_ago=25 * 3600)  # quá 24 giờ: bỏ
    await _insert(session_factory, status="failed", received_ago=10 * 3600)
    await _insert(session_factory, status="dropped", received_ago=30 * 3600)  # quá 24 giờ: bỏ

    await metrics.refresh(NOW)

    assert value_of("quotify_bot_updates", '{status="queued"}') == 1
    assert value_of("quotify_bot_updates", '{status="processing"}') == 1
    assert value_of("quotify_bot_updates", '{status="replied"}') == 3
    assert value_of("quotify_bot_updates", '{status="failed"}') == 1
    assert value_of("quotify_bot_updates", '{status="dropped"}') == 0  # có mặt, bằng 0
    assert value_of("quotify_bot_metrics_up") == 1
    assert value_of("quotify_bot_enabled") == 1


async def test_the_oldest_age_is_published_only_while_someone_is_waiting(
    session_factory: async_sessionmaker[AsyncSession],
    metrics: BotMetrics,
) -> None:
    await metrics.refresh(NOW)
    assert value_of("quotify_bot_queued_oldest_age_seconds") is None  # không ai chờ: không có số đo

    await _insert(session_factory, received_ago=300)
    await _insert(session_factory, received_ago=20)
    await metrics.refresh(NOW)

    assert value_of("quotify_bot_queued_oldest_age_seconds") == 300


async def test_a_clock_that_runs_behind_never_makes_the_age_negative(
    session_factory: async_sessionmaker[AsyncSession],
    metrics: BotMetrics,
) -> None:
    await _insert(session_factory, received_ago=-45)  # máy ghi nhận chạy nhanh hơn 45 giây

    await metrics.refresh(NOW)

    assert value_of("quotify_bot_queued_oldest_age_seconds") == 0


async def test_recent_failures_count_only_failed_rows_that_finished_in_the_last_30_minutes(
    session_factory: async_sessionmaker[AsyncSession],
    metrics: BotMetrics,
) -> None:
    await _insert(session_factory, status="failed", received_ago=900, finished_ago=5 * 60)
    await _insert(session_factory, status="failed", received_ago=900, finished_ago=29 * 60)
    await _insert(session_factory, status="failed", received_ago=900, finished_ago=31 * 60)  # cũ
    await _insert(session_factory, status="replied", received_ago=900, finished_ago=60)
    await _insert(session_factory, status="dropped", received_ago=900, finished_ago=60)

    await metrics.refresh(NOW)

    assert value_of("quotify_bot_recent_failures") == 2
    # Dòng lỗi cũ vẫn nằm trong gauge 24 giờ: hai gauge có vai trò khác nhau.
    assert value_of("quotify_bot_updates", '{status="failed"}') == 3


async def test_recent_failures_are_published_as_zero_when_there_are_none(
    metrics: BotMetrics,
) -> None:
    await metrics.refresh(NOW)

    assert value_of("quotify_bot_recent_failures") == 0  # có mặt bằng 0, để luật cảnh báo thấy


async def test_quota_denials_are_counted_for_the_last_24_hours_only(
    session_factory: async_sessionmaker[AsyncSession],
    metrics: BotMetrics,
) -> None:
    await _insert(
        session_factory, status="dropped", error_category="quota_exceeded", received_ago=60
    )
    await _insert(
        session_factory, status="dropped", error_category="quota_exceeded", received_ago=3600
    )
    await _insert(
        session_factory, status="dropped", error_category="quota_exceeded", received_ago=26 * 3600
    )
    await _insert(session_factory, status="dropped", error_category="expired", received_ago=60)
    await _insert(
        session_factory, status="failed", error_category="quota_exceeded", received_ago=60
    )

    await metrics.refresh(NOW)

    assert (
        value_of("quotify_bot_quota_denied") == 2
    )  # chỉ `dropped` kèm `quota_exceeded`, trong 24 giờ


async def test_with_the_chatbot_off_nothing_about_the_queue_is_published(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # Tắt công tắc khẩn cấp để lại dòng `queued`: tuổi của chúng tăng mãi, không được làm ai bị gọi.
    await _insert(session_factory, received_ago=3 * 86400)
    off = BotMetrics(session_factory, ttl_seconds=0, chatbot_enabled=lambda: False)
    set_active_bot_metrics(off)
    try:
        await off.refresh(NOW)

        assert value_of("quotify_bot_enabled") == 0
        assert value_of("quotify_bot_metrics_up") == 1
        assert value_of("quotify_bot_queued_oldest_age_seconds") is None
        assert value_of("quotify_bot_updates", '{status="queued"}') is None
        assert value_of("quotify_bot_quota_denied") is None
    finally:
        set_active_bot_metrics(None)


async def test_a_database_failure_keeps_the_scrape_alive_and_flags_the_metrics_as_down(
    metrics: BotMetrics,
) -> None:
    def broken() -> AsyncSession:
        raise ConnectionError("db down")

    failing = BotMetrics(broken, ttl_seconds=0, chatbot_enabled=lambda: True)  # type: ignore[arg-type]
    set_active_bot_metrics(failing)

    await failing.refresh(NOW)

    assert value_of("quotify_bot_metrics_up") == 0
    assert value_of("quotify_bot_updates", '{status="queued"}') is None  # không phát số cũ như mới


async def test_after_a_failure_the_old_numbers_are_not_served_as_if_they_were_fresh(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _insert(session_factory, received_ago=100)
    calls: list[int] = []

    def flaky() -> AsyncSession:
        calls.append(1)
        if len(calls) > 1:
            raise ConnectionError("db down")
        return session_factory()

    instance = BotMetrics(flaky, ttl_seconds=0, chatbot_enabled=lambda: True)  # type: ignore[arg-type]
    set_active_bot_metrics(instance)
    try:
        await instance.refresh(NOW)
        assert value_of("quotify_bot_queued_oldest_age_seconds") == 100

        await instance.refresh(NOW)

        assert value_of("quotify_bot_metrics_up") == 0
        assert value_of("quotify_bot_queued_oldest_age_seconds") is None
    finally:
        set_active_bot_metrics(None)


async def test_results_are_cached_for_the_ttl_so_scrapes_stay_cheap(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    clock = [1000.0]
    opened: list[int] = []

    def counting() -> AsyncSession:
        opened.append(1)
        return session_factory()

    instance = BotMetrics(
        counting, ttl_seconds=15, clock=lambda: clock[0], chatbot_enabled=lambda: True
    )  # type: ignore[arg-type]

    await instance.refresh(NOW)
    await instance.refresh(NOW)
    first_round = len(opened)
    clock[0] += 16
    await instance.refresh(NOW)

    assert first_round == 1  # lần thứ hai nằm trong TTL: không chạm DB
    assert len(opened) == 2  # hết TTL thì đọc lại


async def test_a_database_that_hangs_is_cut_by_the_timeout_instead_of_hanging_the_scrape(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    class _Hangs:
        async def __aenter__(self) -> AsyncSession:
            await asyncio.sleep(3600)  # treo "mãi mãi": chỉ hạn chờ mới cứu được
            raise AssertionError("không tới được đây")

        async def __aexit__(self, *exc_info: object) -> None:
            return None

    instance = BotMetrics(
        lambda: _Hangs(),  # type: ignore[arg-type, return-value]
        ttl_seconds=0,
        timeout_seconds=0.2,
        chatbot_enabled=lambda: True,
    )

    started = time.monotonic()
    await asyncio.wait_for(instance.refresh(NOW), timeout=5)  # không có hạn chờ thì test treo ở đây
    elapsed = time.monotonic() - started

    assert instance.ok is False and instance.snapshot is None
    assert elapsed < 2  # bị cắt ở khoảng 0,2 giây, không phải đợi lâu


async def test_the_metrics_endpoint_serves_the_bot_numbers_computed_at_scrape_time(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Dựng route `/metrics` thật nhưng trỏ vào database tạm của test.
    monkeypatch.setattr("app.db.session.get_sessionmaker", lambda: session_factory)
    monkeypatch.setattr(bot_metrics_module, "_chatbot_enabled_from_settings", lambda: True)
    settings = Settings(_env_file=None, METRICS_ENABLED=True)  # type: ignore[call-arg]
    app = FastAPI()
    install_observability(app, settings)
    real_now = datetime.now(UTC)  # route dùng giờ thật: dữ liệu mẫu cũng phải tính theo giờ thật
    await _insert(session_factory, received_ago=3600, base=real_now)  # claim được, đã chờ lâu
    await _insert(session_factory, status="replied", received_ago=60, base=real_now)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(settings.metrics_path)
    finally:
        set_active_bot_metrics(None)
        set_active_metrics(None)

    assert response.status_code == 200
    body = response.text
    assert 'quotify_bot_updates{status="queued"} 1.0' in body
    assert 'quotify_bot_updates{status="replied"} 1.0' in body
    assert "quotify_bot_metrics_up 1.0" in body and "quotify_bot_enabled 1.0" in body
    # Nguồn thông báo giá cùng route không được rớt mất khi thêm nguồn chatbot.
    assert "quotify_price_alert_metrics_up 1.0" in body
    assert "quotify_price_alert_enabled 0.0" in body
    age = re.search(r"^quotify_bot_queued_oldest_age_seconds ([0-9.e+]+)$", body, re.MULTILINE)
    assert age is not None and float(age.group(1)) >= 3600  # tuổi tính theo giờ thật của scrape


async def test_each_scrape_serves_the_numbers_of_the_app_that_was_scraped(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Collector là toàn cục: cài app thứ hai không được làm app thứ nhất đọc số của app kia."""
    monkeypatch.setattr("app.db.session.get_sessionmaker", lambda: session_factory)
    monkeypatch.setattr(bot_metrics_module, "_chatbot_enabled_from_settings", lambda: True)
    settings = Settings(_env_file=None, METRICS_ENABLED=True)  # type: ignore[call-arg]
    first, second = FastAPI(), FastAPI()
    install_observability(first, settings)
    install_observability(second, settings)  # cài sau: collector đang trỏ vào app này

    def broken() -> AsyncSession:
        raise ConnectionError("db down")

    second.state.bot_metrics = BotMetrics(broken, chatbot_enabled=lambda: True)  # type: ignore[arg-type]
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=first), base_url="http://test"
        ) as client:
            body = (await client.get(settings.metrics_path)).text
    finally:
        set_active_bot_metrics(None)
        set_active_metrics(None)

    assert "quotify_bot_metrics_up 1.0" in body  # số của app được scrape, không phải app kia (hỏng)


@pytest.mark.parametrize(
    ("chatbot", "telegram", "expected"),
    [(True, True, True), (True, False, False), (False, True, False), (False, False, False)],
)
def test_the_default_gate_needs_both_the_chatbot_and_the_telegram_flags(
    monkeypatch: pytest.MonkeyPatch,
    chatbot: bool,
    telegram: bool,
    expected: bool,
) -> None:
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None, CHATBOT_ENABLED=chatbot, TELEGRAM_ENABLED=telegram
    )
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings)

    assert bot_metrics_module._chatbot_enabled_from_settings() is expected
