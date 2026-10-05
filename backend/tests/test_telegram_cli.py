from __future__ import annotations

import io
import json
from typing import Any

import httpx
import pytest

from app.core.config import Settings
from app.integrations.telegram import TelegramClient
from app.telegram_cli import (
    commands_command,
    delete_webhook_command,
    info_command,
    me_command,
    set_webhook_command,
)

FAKE_TOKEN = "123456789:AAFakeTokenFakeTokenFakeTokenFake12"


def make_client(
    username: str | None = "quotify_dev_bot",
) -> tuple[TelegramClient, httpx.AsyncClient]:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"ok": True, "result": {"id": 987654321, "username": username}},
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return TelegramClient(token=FAKE_TOKEN, http_client=http_client), http_client


@pytest.mark.asyncio
async def test_me_prints_the_bot_username_and_never_the_token() -> None:
    client, http_client = make_client()
    out, err = io.StringIO(), io.StringIO()

    code = await me_command(client, configured_username="quotify_dev_bot", out=out, err=err)
    await http_client.aclose()

    assert code == 0
    assert "@quotify_dev_bot" in out.getvalue()
    assert "987654321" in out.getvalue()
    assert FAKE_TOKEN not in out.getvalue() + err.getvalue()


@pytest.mark.asyncio
async def test_me_fails_when_configured_username_differs_from_the_real_bot() -> None:
    client, http_client = make_client(username="another_bot")
    out, err = io.StringIO(), io.StringIO()

    code = await me_command(client, configured_username="quotify_dev_bot", out=out, err=err)
    await http_client.aclose()

    assert code == 2
    assert "quotify_dev_bot" in err.getvalue()
    assert "another_bot" in err.getvalue()


@pytest.mark.asyncio
async def test_me_accepts_an_unset_configured_username() -> None:
    client, http_client = make_client()
    out, err = io.StringIO(), io.StringIO()

    code = await me_command(client, configured_username="", out=out, err=err)
    await http_client.aclose()

    assert code == 0
    assert err.getvalue() == ""


def test_main_reports_missing_token_without_a_traceback(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from app import telegram_cli
    from app.core.config import Settings

    monkeypatch.setattr(
        telegram_cli,
        "get_settings",
        lambda: Settings.model_validate({"telegram_bot_token": ""}),
    )

    code = telegram_cli.main(["me"])

    captured = capsys.readouterr()
    assert code == 1
    assert "TELEGRAM_BOT_TOKEN" in captured.err
    assert "Traceback" not in captured.err
    assert json.dumps(FAKE_TOKEN) not in captured.out + captured.err


# ----- set / delete / info / commands -----


class Recorder:
    def __init__(self, *, username: str = "quotify_dev_bot", webhook_url: str = "") -> None:
        self.username = username
        self.webhook_url = webhook_url
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        method = request.url.path.rsplit("/", 1)[-1]
        if method == "getMe":
            result: Any = {"id": 987654321, "username": self.username}
        elif method == "getWebhookInfo":
            result = {
                "url": self.webhook_url,
                "pending_update_count": 3,
                "last_error_message": "Wrong response from the webhook",
                "allowed_updates": ["message"],
            }
        else:
            result = True
        return httpx.Response(200, json={"ok": True, "result": result})

    def mutating_calls(self) -> list[str]:
        return [
            request.url.path.rsplit("/", 1)[-1]
            for request in self.requests
            if request.url.path.rsplit("/", 1)[-1] not in {"getMe", "getWebhookInfo"}
        ]


def build(recorder: Recorder) -> tuple[TelegramClient, httpx.AsyncClient]:
    http_client = httpx.AsyncClient(transport=httpx.MockTransport(recorder.handler))
    return TelegramClient(token=FAKE_TOKEN, http_client=http_client), http_client


def cli_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "telegram_bot_token": FAKE_TOKEN,
        "telegram_bot_username": "quotify_dev_bot",
        "telegram_webhook_url": "https://quotify.example.test/api/v1/telegram/webhook",
        "telegram_webhook_secret": "cli_secret-value_123",
        **overrides,
    }
    return Settings.model_validate(values)


@pytest.mark.asyncio
async def test_set_webhook_without_yes_only_describes_what_it_would_do() -> None:
    recorder = Recorder(webhook_url="https://old.example.test/hook")
    client, http_client = build(recorder)
    out, err = io.StringIO(), io.StringIO()

    code = await set_webhook_command(client, cli_settings(), yes=False, out=out, err=err)
    await http_client.aclose()

    assert code == 3
    assert recorder.mutating_calls() == []
    assert "@quotify_dev_bot" in out.getvalue()
    assert "https://old.example.test/hook" in out.getvalue()
    assert "--yes" in out.getvalue()


@pytest.mark.asyncio
async def test_set_webhook_with_yes_registers_it_without_printing_secrets() -> None:
    recorder = Recorder()
    client, http_client = build(recorder)
    out, err = io.StringIO(), io.StringIO()

    code = await set_webhook_command(client, cli_settings(), yes=True, out=out, err=err)
    await http_client.aclose()

    assert code == 0
    assert recorder.mutating_calls() == ["setWebhook"]
    payload = json.loads(
        next(r for r in recorder.requests if r.url.path.endswith("/setWebhook")).content
    )
    assert payload["url"] == "https://quotify.example.test/api/v1/telegram/webhook"
    assert payload["secret_token"] == "cli_secret-value_123"
    assert payload["allowed_updates"] == ["message", "my_chat_member", "callback_query"]
    printed = out.getvalue() + err.getvalue()
    assert "cli_secret-value_123" not in printed
    assert FAKE_TOKEN not in printed


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["telegram_webhook_url", "telegram_webhook_secret"])
async def test_set_webhook_requires_url_and_secret(missing: str) -> None:
    recorder = Recorder()
    client, http_client = build(recorder)
    out, err = io.StringIO(), io.StringIO()

    code = await set_webhook_command(
        client, cli_settings(**{missing: ""}), yes=True, out=out, err=err
    )
    await http_client.aclose()

    assert code == 1
    assert recorder.mutating_calls() == []


@pytest.mark.asyncio
async def test_set_webhook_refuses_when_the_token_belongs_to_another_bot() -> None:
    recorder = Recorder(username="production_bot")
    client, http_client = build(recorder)
    out, err = io.StringIO(), io.StringIO()

    code = await set_webhook_command(client, cli_settings(), yes=True, out=out, err=err)
    await http_client.aclose()

    assert code == 2
    assert recorder.mutating_calls() == []
    assert "production_bot" in err.getvalue()


@pytest.mark.asyncio
async def test_delete_webhook_needs_yes() -> None:
    recorder = Recorder(webhook_url="https://quotify.example.test/api/v1/telegram/webhook")
    client, http_client = build(recorder)

    refused = await delete_webhook_command(
        client, cli_settings(), yes=False, out=io.StringIO(), err=io.StringIO()
    )
    assert refused == 3
    assert recorder.mutating_calls() == []

    done = await delete_webhook_command(
        client, cli_settings(), yes=True, out=io.StringIO(), err=io.StringIO()
    )
    await http_client.aclose()

    assert done == 0
    assert recorder.mutating_calls() == ["deleteWebhook"]


@pytest.mark.asyncio
async def test_info_prints_the_webhook_state_without_secrets() -> None:
    recorder = Recorder(webhook_url="https://quotify.example.test/api/v1/telegram/webhook")
    client, http_client = build(recorder)
    out, err = io.StringIO(), io.StringIO()

    code = await info_command(client, out=out, err=err)
    await http_client.aclose()

    assert code == 0
    text = out.getvalue()
    assert "https://quotify.example.test/api/v1/telegram/webhook" in text
    assert "pending_update_count" in text
    assert "Wrong response from the webhook" in text
    assert FAKE_TOKEN not in text + err.getvalue()


@pytest.mark.asyncio
async def test_commands_registers_the_three_commands_for_private_chats() -> None:
    recorder = Recorder()
    client, http_client = build(recorder)

    code = await commands_command(
        client, cli_settings(), yes=True, out=io.StringIO(), err=io.StringIO()
    )
    await http_client.aclose()

    assert code == 0
    payload = json.loads(
        next(r for r in recorder.requests if r.url.path.endswith("/setMyCommands")).content
    )
    assert [item["command"] for item in payload["commands"]] == ["start", "stop", "help"]
    assert all(item["description"] for item in payload["commands"])
    assert payload["scope"] == {"type": "all_private_chats"}
