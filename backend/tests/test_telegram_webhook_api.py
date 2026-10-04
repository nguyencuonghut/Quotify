from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.exc import OperationalError
from telegram_fakes import (
    WEBHOOK_SECRET,
    FakeStore,
    Outbox,
    make_client,
    make_session_factory,
    make_update,
)

from app.api.v1.telegram import get_telegram_runner
from app.core.config import Settings, get_settings
from app.services.telegram_update_runner import TelegramUpdateRunner

WEBHOOK_URL = "/api/v1/telegram/webhook"
SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"


def build_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "app_env": "test",
        "telegram_enabled": True,
        "telegram_mode": "webhook",
        "telegram_webhook_secret": WEBHOOK_SECRET,
        "telegram_bot_token": "123456789:AAFakeTokenFakeTokenFakeTokenFake12",
        **overrides,
    }
    return Settings.model_validate(values)


@dataclass
class Harness:
    app: FastAPI
    client: AsyncClient
    store: FakeStore
    outbox: Outbox

    async def post(
        self,
        payload: Any,
        *,
        secret: str | None = WEBHOOK_SECRET,
        raw: bytes | None = None,
        content_type: str = "application/json",
    ) -> Any:
        headers = {"Content-Type": content_type}
        if secret is not None:
            headers[SECRET_HEADER] = secret
        content = raw if raw is not None else json.dumps(payload).encode()
        return await self.client.post(WEBHOOK_URL, content=content, headers=headers)

    def use_settings(self, settings: Settings) -> None:
        self.app.dependency_overrides[get_settings] = lambda: settings


@pytest.fixture
async def harness(app: FastAPI, client: AsyncClient) -> AsyncIterator[Harness]:
    store = FakeStore()
    outbox = Outbox()
    telegram_client, http_client = make_client(outbox)
    runner = TelegramUpdateRunner(
        session_factory=make_session_factory(store),
        client=telegram_client,
    )
    app.dependency_overrides[get_settings] = lambda: build_settings()
    app.dependency_overrides[get_telegram_runner] = lambda: runner
    yield Harness(app=app, client=client, store=store, outbox=outbox)
    app.dependency_overrides.clear()
    await http_client.aclose()


@pytest.mark.asyncio
async def test_valid_help_command_gets_a_vietnamese_reply(harness: Harness) -> None:
    response = await harness.post(make_update(1, "/help"))

    assert response.status_code == 200
    messages = harness.outbox.sent_messages()
    assert len(messages) == 1
    assert messages[0]["chat_id"] == 111
    assert messages[0]["parse_mode"] == "HTML"
    assert "Các lệnh" in messages[0]["text"]
    assert "/stop" in messages[0]["text"]


@pytest.mark.asyncio
async def test_unknown_text_gets_a_hint_to_use_help(harness: Harness) -> None:
    response = await harness.post(make_update(1, "xin chào"))

    assert response.status_code == 200
    assert "/help" in harness.outbox.sent_messages()[0]["text"]


@pytest.mark.asyncio
async def test_help_command_addressed_to_the_bot_is_recognized(harness: Harness) -> None:
    await harness.post(make_update(1, "/help@quotify_dev_bot"))

    assert "Các lệnh" in harness.outbox.sent_messages()[0]["text"]


@pytest.mark.asyncio
async def test_duplicate_update_id_is_not_answered_twice(harness: Harness) -> None:
    first = await harness.post(make_update(7, "/help"))
    second = await harness.post(make_update(7, "/help"))

    assert first.status_code == second.status_code == 200
    assert len(harness.outbox.sent_messages()) == 1
    assert harness.store.processed == {7}


@pytest.mark.asyncio
@pytest.mark.parametrize("secret", [None, "wrong-secret"])
async def test_missing_or_wrong_secret_is_forbidden(harness: Harness, secret: str | None) -> None:
    response = await harness.post(make_update(1), secret=secret)

    assert response.status_code == 403
    assert harness.outbox.sent_messages() == []
    assert harness.store.processed == set()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"telegram_enabled": False},
        {"telegram_mode": "polling"},
        {"telegram_webhook_secret": ""},
    ],
)
@pytest.mark.parametrize("body", [b'{"update_id": 1}', b"{rac", b"[]"])
async def test_webhook_is_hidden_when_the_feature_is_off(
    harness: Harness,
    overrides: dict[str, Any],
    body: bytes,
) -> None:
    harness.use_settings(build_settings(**overrides))

    response = await harness.post(None, raw=body)

    assert response.status_code == 404
    assert harness.outbox.requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [b"{rac", b"[]", b'"text"', b"null", b'{"no_update_id": 1}', b""])
async def test_garbage_bodies_are_acknowledged_without_error(
    harness: Harness,
    body: bytes,
) -> None:
    response = await harness.post(None, raw=body)

    assert response.status_code == 200
    assert harness.outbox.requests == []


@pytest.mark.asyncio
async def test_content_type_does_not_matter_for_a_valid_update(harness: Harness) -> None:
    response = await harness.post(make_update(3, "/help"), content_type="text/plain")

    assert response.status_code == 200
    assert len(harness.outbox.sent_messages()) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("chat_type", ["group", "supergroup", "channel"])
async def test_non_private_chats_are_ignored_silently(harness: Harness, chat_type: str) -> None:
    response = await harness.post(make_update(1, "/help", chat_type=chat_type))

    assert response.status_code == 200
    assert harness.outbox.sent_messages() == []
    # Vẫn ghi nhận update đã xử lý, để Telegram không gửi lại.
    assert harness.store.processed == {1}


@pytest.mark.asyncio
async def test_updates_without_a_message_are_acknowledged(harness: Harness) -> None:
    response = await harness.post({"update_id": 5, "edited_message": {"text": "x"}})

    assert response.status_code == 200
    assert harness.outbox.sent_messages() == []


@pytest.mark.asyncio
async def test_telegram_send_failure_does_not_fail_the_webhook(harness: Harness) -> None:
    harness.outbox.status_code = 400

    response = await harness.post(make_update(4, "/help"))

    assert response.status_code == 200
    assert harness.store.processed == {4}


@pytest.mark.asyncio
async def test_poison_update_is_recorded_answered_and_not_retried(harness: Harness) -> None:
    harness.store.fail_next = [ValueError("boom")]

    response = await harness.post(make_update(8, "/help"))

    assert response.status_code == 200
    assert harness.store.processed == {8}
    assert harness.store.rollbacks >= 1
    messages = harness.outbox.sent_messages()
    assert len(messages) == 1
    assert "tạm thời" in messages[0]["text"]


@pytest.mark.asyncio
async def test_transient_database_failure_asks_telegram_to_retry(harness: Harness) -> None:
    harness.store.fail_next = [OperationalError("INSERT", {}, Exception("connection lost"))]

    response = await harness.post(make_update(9, "/help"))

    assert response.status_code == 503
    assert harness.store.processed == set()
    assert harness.outbox.sent_messages() == []

    retry = await harness.post(make_update(9, "/help"))

    assert retry.status_code == 200
    assert harness.store.processed == {9}
    assert len(harness.outbox.sent_messages()) == 1


@pytest.mark.asyncio
async def test_webhook_is_not_listed_in_the_openapi_schema(client: AsyncClient) -> None:
    schema = (await client.get("/openapi.json")).json()

    assert WEBHOOK_URL not in schema["paths"]
