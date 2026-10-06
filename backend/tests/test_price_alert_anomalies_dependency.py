from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.api.v1.price_alert_anomalies import get_telegram_client_for_review
from app.core.config import Settings
from app.integrations.telegram import TelegramClient


def settings(**overrides: Any) -> Settings:
    return Settings.model_validate(
        {
            "app_env": "test",
            "otel_enabled": False,
            "otel_exporter_otlp_endpoint": None,
            "telegram_enabled": True,
            "telegram_bot_token": "123456789:AAFakeTokenFakeTokenFakeTokenFake12",
            **overrides,
        }
    )


def request_with(runner: object | None) -> Any:
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(telegram_runner=runner)))


async def drive(generator: Any) -> Any:
    client = await generator.__anext__()
    return client, generator


async def test_without_telegram_there_is_no_client() -> None:
    client, generator = await drive(
        get_telegram_client_for_review(request_with(None), settings(telegram_enabled=False))
    )
    assert client is None
    with pytest.raises(StopAsyncIteration):
        await generator.__anext__()


async def test_a_client_made_for_one_request_is_closed_afterwards(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed: list[TelegramClient] = []

    async def record_close(self: TelegramClient) -> None:
        closed.append(self)

    monkeypatch.setattr(TelegramClient, "aclose", record_close)

    client, generator = await drive(get_telegram_client_for_review(request_with(None), settings()))
    assert isinstance(client, TelegramClient) and closed == []
    with pytest.raises(StopAsyncIteration):
        await generator.__anext__()

    assert closed == [client]


async def test_the_webhook_runner_client_is_shared_and_never_closed_here(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shared = TelegramClient(token="123456789:AAFakeTokenFakeTokenFakeTokenFake12")
    closed: list[TelegramClient] = []

    async def record_close(self: TelegramClient) -> None:
        closed.append(self)

    monkeypatch.setattr(TelegramClient, "aclose", record_close)

    client, generator = await drive(
        get_telegram_client_for_review(request_with(SimpleNamespace(client=shared)), settings())
    )
    with pytest.raises(StopAsyncIteration):
        await generator.__anext__()

    assert client is shared and closed == []


async def test_a_missing_token_means_no_client() -> None:
    client, _ = await drive(
        get_telegram_client_for_review(request_with(None), settings(telegram_bot_token=""))
    )
    assert client is None
