from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from arq.cron import next_cron

import app.worker as worker
from app.services.price_alert_scan import ScanOutcome


def _price_alert_cron() -> Any:
    [job] = [
        job for job in worker.WorkerSettings.cron_jobs if job.coroutine is worker.poll_price_alerts
    ]
    return job


def test_the_worker_runs_cron_in_vietnam_time() -> None:
    assert worker.WorkerSettings.timezone == ZoneInfo("Asia/Ho_Chi_Minh")


def test_the_scan_cron_is_registered_every_30_seconds_and_unique() -> None:
    job = _price_alert_cron()

    assert job.second == {0, 30}
    assert job.unique is True
    assert worker.poll_price_alerts in worker.WorkerSettings.functions


def test_consecutive_scan_runs_are_30_seconds_apart() -> None:
    job = _price_alert_cron()
    start = datetime(2026, 10, 5, 8, 0, 5, tzinfo=UTC)

    first = next_cron(start, second=job.second, microsecond=job.microsecond)
    second = next_cron(first, second=job.second, microsecond=job.microsecond)

    assert (first.second, second.second) == (30, 0)
    assert second - first == timedelta(seconds=30)


def test_the_existing_backup_cron_is_still_registered() -> None:
    assert any(
        job.coroutine is worker.poll_and_run_scheduled_backups
        for job in worker.WorkerSettings.cron_jobs
    )


class _FakeSession:
    def __init__(self) -> None:
        self.committed = False

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True


@pytest.mark.asyncio
async def test_the_scan_task_does_nothing_when_telegram_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(worker, "get_settings", lambda: SimpleNamespace(telegram_enabled=False))

    def factory() -> Any:
        raise AssertionError("không được mở session khi TELEGRAM_ENABLED=false")

    await worker.poll_price_alerts({"session_factory": factory})


@pytest.mark.asyncio
async def test_the_scan_task_runs_the_service_and_commits(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _FakeSession()
    calls: list[tuple[object, datetime]] = []

    class FakeService:
        def __init__(self, given_session: object, *, seed_user_id: object) -> None:
            calls.append((seed_user_id, datetime.min))

        async def run_once(self, now: datetime) -> ScanOutcome:
            calls.append(("run_once", now))
            return ScanOutcome("idle")

    async def fake_seed(_session: object, email: str) -> str:
        return f"seed:{email}"

    monkeypatch.setattr(
        worker,
        "get_settings",
        lambda: SimpleNamespace(telegram_enabled=True, auth_seed_admin_email="admin@example.com"),
    )
    monkeypatch.setattr(worker, "PriceAlertScanService", FakeService)
    monkeypatch.setattr(worker, "get_seed_user_id", fake_seed)

    await worker.poll_price_alerts({"session_factory": lambda: session})

    assert calls[0][0] == "seed:admin@example.com"
    assert calls[1][0] == "run_once"
    assert calls[1][1].tzinfo is not None
    assert session.committed is True
