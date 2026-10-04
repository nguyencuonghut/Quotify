from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest
from telegram_fakes import FAKE_TOKEN

from app.core.config import Settings
from app.integrations.telegram import TelegramClient
from app.services.telegram_update_runner import TelegramTemporaryError
from app.telegram_poller import check_poller_preconditions, run_poller


def settings_for(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "app_env": "development",
        "telegram_enabled": True,
        "telegram_mode": "polling",
        "telegram_bot_token": FAKE_TOKEN,
        **overrides,
    }
    return Settings.model_validate(values)


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({}, None),
        ({"app_env": "production"}, "production"),
        ({"telegram_enabled": False}, "TELEGRAM_ENABLED"),
        ({"telegram_mode": "webhook"}, "TELEGRAM_MODE"),
        ({"telegram_bot_token": ""}, "TELEGRAM_BOT_TOKEN"),
    ],
)
def test_poller_refuses_to_run_in_the_wrong_environment(
    overrides: dict[str, Any],
    expected: str | None,
) -> None:
    problem = check_poller_preconditions(settings_for(**overrides))

    if expected is None:
        assert problem is None
    else:
        assert problem is not None
        assert expected in problem


class FakeRunner:
    def __init__(self, stop: asyncio.Event, *, fail_on: int | None = None) -> None:
        self.stop = stop
        self.processed: list[int] = []
        self.fail_on = fail_on

    async def process(self, payload: dict[str, Any]) -> None:
        if payload["update_id"] == self.fail_on:
            self.fail_on = None
            raise TelegramTemporaryError
        self.processed.append(payload["update_id"])


class Telegram:
    """Telegram giả: trả các lô update theo thứ tự và ghi lại request."""

    def __init__(self, batches: list[Any], stop: asyncio.Event) -> None:
        self.batches = batches
        self.stop = stop
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        method = request.url.path.rsplit("/", 1)[-1]
        if method == "deleteWebhook":
            return httpx.Response(200, json={"ok": True, "result": True})
        batch = self.batches.pop(0) if self.batches else []
        if not self.batches:
            self.stop.set()
        if isinstance(batch, Exception):
            raise batch
        return httpx.Response(200, json={"ok": True, "result": batch})

    def calls(self, method: str) -> list[dict[str, Any]]:
        return [
            json.loads(request.content)
            for request in self.requests
            if request.url.path.endswith(f"/{method}")
        ]


def build(batches: list[Any], *, fail_on: int | None = None) -> tuple[Any, ...]:
    stop = asyncio.Event()
    telegram = Telegram(batches, stop)
    http_client = httpx.AsyncClient(transport=httpx.MockTransport(telegram.handler))
    client = TelegramClient(token=FAKE_TOKEN, http_client=http_client)
    runner = FakeRunner(stop, fail_on=fail_on)
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    return stop, telegram, client, runner, sleeps, fake_sleep, http_client


@pytest.mark.asyncio
async def test_poller_deletes_the_webhook_first_then_advances_the_offset() -> None:
    stop, telegram, client, runner, _sleeps, fake_sleep, http_client = build(
        [[{"update_id": 10}, {"update_id": 11}], []],
    )

    await run_poller(client, runner, stop, sleep=fake_sleep)
    await http_client.aclose()

    assert telegram.requests[0].url.path.endswith("/deleteWebhook")
    polls = telegram.calls("getUpdates")
    assert "offset" not in polls[0]
    assert polls[1]["offset"] == 12
    assert polls[0]["allowed_updates"] == ["message", "my_chat_member"]
    assert runner.processed == [10, 11]


@pytest.mark.asyncio
async def test_poller_does_not_advance_past_an_update_that_failed_temporarily() -> None:
    stop, telegram, client, runner, sleeps, fake_sleep, http_client = build(
        [[{"update_id": 20}, {"update_id": 21}], [{"update_id": 20}, {"update_id": 21}], []],
        fail_on=20,
    )

    await run_poller(client, runner, stop, sleep=fake_sleep)
    await http_client.aclose()

    polls = telegram.calls("getUpdates")
    assert "offset" not in polls[1]  # lỗi tạm thời: chưa xác nhận update 20
    assert polls[2]["offset"] == 22
    assert runner.processed == [20, 21]
    assert sleeps and sleeps[0] > 0


@pytest.mark.asyncio
async def test_poller_backs_off_on_network_errors_and_keeps_running() -> None:
    stop, telegram, client, runner, sleeps, fake_sleep, http_client = build(
        [httpx.ConnectError("boom"), [{"update_id": 30}], []],
    )

    await run_poller(client, runner, stop, sleep=fake_sleep)
    await http_client.aclose()

    assert runner.processed == [30]
    assert len(sleeps) == 1


@pytest.mark.asyncio
async def test_poller_stops_promptly_when_asked() -> None:
    stop, telegram, client, runner, _sleeps, fake_sleep, http_client = build([[]])
    stop.set()

    await run_poller(client, runner, stop, sleep=fake_sleep)
    await http_client.aclose()

    assert telegram.calls("getUpdates") == []
