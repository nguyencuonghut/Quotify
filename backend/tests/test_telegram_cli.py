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
    def __init__(
        self,
        *,
        username: str = "quotify_dev_bot",
        webhook_url: str = "",
        max_connections: int | None = None,
    ) -> None:
        self.username = username
        self.webhook_url = webhook_url
        self.max_connections = max_connections
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
            if self.max_connections is not None:  # Telegram chỉ trả khi webhook đã đặt
                result["max_connections"] = self.max_connections
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


def _registered_payload(recorder: Recorder) -> dict[str, Any]:
    request = next(r for r in recorder.requests if r.url.path.endswith("/setWebhook"))
    return json.loads(request.content)  # type: ignore[no-any-return]


@pytest.mark.asyncio
async def test_set_webhook_passes_an_explicit_max_connections() -> None:
    recorder = Recorder()
    client, http_client = build(recorder)
    out, err = io.StringIO(), io.StringIO()

    code = await set_webhook_command(
        client, cli_settings(), yes=True, out=out, err=err, max_connections=5
    )
    await http_client.aclose()

    assert code == 0
    assert _registered_payload(recorder)["max_connections"] == 5
    assert "max_connections=5" in out.getvalue()  # người chạy thấy giá trị sẽ đặt


@pytest.mark.asyncio
async def test_set_webhook_on_production_defaults_to_one_connection_at_a_time() -> None:
    recorder = Recorder()
    client, http_client = build(recorder)
    out, err = io.StringIO(), io.StringIO()

    code = await set_webhook_command(
        client, cli_settings(app_env="production"), yes=True, out=out, err=err
    )
    await http_client.aclose()

    assert code == 0
    assert _registered_payload(recorder)["max_connections"] == 1  # một update tại một thời điểm


@pytest.mark.asyncio
async def test_set_webhook_outside_production_leaves_the_telegram_default() -> None:
    recorder = Recorder()
    client, http_client = build(recorder)
    out, err = io.StringIO(), io.StringIO()

    code = await set_webhook_command(
        client, cli_settings(app_env="development"), yes=True, out=out, err=err
    )
    await http_client.aclose()

    assert code == 0
    assert "max_connections" not in _registered_payload(recorder)
    assert "max_connections" not in out.getvalue()


@pytest.mark.asyncio
async def test_an_explicit_max_connections_wins_over_the_production_default() -> None:
    recorder = Recorder()
    client, http_client = build(recorder)
    out, err = io.StringIO(), io.StringIO()

    await set_webhook_command(
        client,
        cli_settings(app_env="production"),
        yes=True,
        out=out,
        err=err,
        max_connections=3,
    )
    await http_client.aclose()

    assert _registered_payload(recorder)["max_connections"] == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [0, -1, 101])
async def test_set_webhook_rejects_a_max_connections_telegram_would_refuse(bad: int) -> None:
    recorder = Recorder()
    client, http_client = build(recorder)
    out, err = io.StringIO(), io.StringIO()

    code = await set_webhook_command(
        client, cli_settings(), yes=True, out=out, err=err, max_connections=bad
    )
    await http_client.aclose()

    assert code == 1
    assert recorder.mutating_calls() == []
    assert "1" in err.getvalue() and "100" in err.getvalue()


@pytest.mark.asyncio
async def test_a_dry_run_shows_max_connections_without_registering() -> None:
    recorder = Recorder()
    client, http_client = build(recorder)
    out, err = io.StringIO(), io.StringIO()

    code = await set_webhook_command(
        client, cli_settings(app_env="production"), yes=False, out=out, err=err
    )
    await http_client.aclose()

    assert code == 3 and recorder.mutating_calls() == []
    assert "max_connections=1" in out.getvalue()


def test_the_set_command_has_a_max_connections_option() -> None:
    from app.telegram_cli import _build_parser

    parser = _build_parser()

    assert parser.parse_args(["set", "--yes", "--max-connections", "2"]).max_connections == 2
    assert parser.parse_args(["set"]).max_connections is None
    with pytest.raises(SystemExit):
        parser.parse_args(["set", "--max-connections", "abc"])


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


async def _registered_commands(
    *, chatbot_enabled: bool, telegram_enabled: bool
) -> tuple[list[str], str]:
    # Hai cờ luôn được đặt rõ: `Settings` đọc cả `.env` của máy dev nên không thể tin mặc định.
    settings = {"chatbot_enabled": chatbot_enabled, "telegram_enabled": telegram_enabled}
    recorder = Recorder()
    client, http_client = build(recorder)
    out = io.StringIO()

    code = await commands_command(
        client, cli_settings(**settings), yes=True, out=out, err=io.StringIO()
    )
    await http_client.aclose()

    assert code == 0
    payload = json.loads(
        next(r for r in recorder.requests if r.url.path.endswith("/setMyCommands")).content
    )
    assert all(item["description"] for item in payload["commands"])
    assert payload["scope"] == {"type": "all_private_chats"}
    return [item["command"] for item in payload["commands"]], out.getvalue()


@pytest.mark.asyncio
async def test_commands_registers_only_the_basic_commands_while_the_chatbot_is_off() -> None:
    commands, printed = await _registered_commands(chatbot_enabled=False, telegram_enabled=True)

    # `/limit` thuộc chatbot: chưa bật thì chưa đưa vào menu (người dùng gõ sẽ nhận lệnh lạ).
    assert commands == ["start", "stop", "help"]
    assert "/start, /stop, /help" in printed and "/limit" not in printed


@pytest.mark.asyncio
async def test_commands_adds_limit_once_the_chatbot_is_on() -> None:
    commands, printed = await _registered_commands(chatbot_enabled=True, telegram_enabled=True)

    assert commands == ["start", "stop", "help", "limit"]
    assert "/start, /stop, /help, /limit" in printed  # liệt kê đúng những lệnh đã đăng ký


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("chatbot_enabled", "telegram_enabled"),
    [(True, False), (False, True), (False, False)],
    ids=["chatbot-flag-only", "telegram-flag-only", "both-off"],
)
async def test_limit_needs_both_the_chatbot_and_the_telegram_flag(
    chatbot_enabled: bool, telegram_enabled: bool
) -> None:
    commands, _ = await _registered_commands(
        chatbot_enabled=chatbot_enabled, telegram_enabled=telegram_enabled
    )

    assert "limit" not in commands  # cùng điều kiện với việc chatbot thật sự nhận tin


@pytest.mark.asyncio
async def test_the_limit_command_is_described_in_vietnamese_for_the_bot_menu() -> None:
    from app.telegram_cli import BOT_COMMANDS

    description = next(c["description"] for c in BOT_COMMANDS if c["command"] == "limit")

    assert description == "Xem hạn mức sử dụng hôm nay"


@pytest.mark.asyncio
async def test_commands_without_yes_registers_nothing() -> None:
    recorder = Recorder()
    client, http_client = build(recorder)

    code = await commands_command(
        client, cli_settings(), yes=False, out=io.StringIO(), err=io.StringIO()
    )
    await http_client.aclose()

    assert code == 3
    assert recorder.mutating_calls() == []  # đăng ký lệnh lên bot luôn cần --yes rõ ràng


@pytest.mark.asyncio
@pytest.mark.parametrize("edge", [1, 100])
async def test_set_webhook_accepts_the_two_ends_of_the_range_telegram_allows(edge: int) -> None:
    recorder = Recorder()
    client, http_client = build(recorder)

    code = await set_webhook_command(
        client,
        cli_settings(),
        yes=True,
        out=io.StringIO(),
        err=io.StringIO(),
        max_connections=edge,
    )
    await http_client.aclose()

    assert code == 0
    assert _registered_payload(recorder)["max_connections"] == edge


@pytest.mark.asyncio
async def test_the_production_default_does_not_depend_on_how_app_env_is_capitalised() -> None:
    # Poller và bot-worker so `APP_ENV` không phân biệt hoa thường; CLI phải nhất quán với chúng.
    recorder = Recorder()
    client, http_client = build(recorder)

    await set_webhook_command(
        client,
        cli_settings(app_env="Production"),
        yes=True,
        out=io.StringIO(),
        err=io.StringIO(),
    )
    await http_client.aclose()

    assert _registered_payload(recorder)["max_connections"] == 1


def _run_main(
    monkeypatch: pytest.MonkeyPatch, recorder: Recorder, argv: list[str], **settings: Any
) -> int:
    from app import telegram_cli

    client, _http_client = build(recorder)
    monkeypatch.setattr(telegram_cli, "get_settings", lambda: cli_settings(**settings))
    monkeypatch.setattr(TelegramClient, "from_settings", classmethod(lambda cls, _settings: client))
    return telegram_cli.main(argv)


def test_the_command_line_option_reaches_the_registered_webhook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = Recorder()

    code = _run_main(monkeypatch, recorder, ["set", "--max-connections", "7", "--yes"])

    assert code == 0
    assert _registered_payload(recorder)["max_connections"] == 7


def test_the_command_line_without_the_option_still_gets_the_production_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = Recorder()

    code = _run_main(monkeypatch, recorder, ["set", "--yes"], app_env="production")

    assert code == 0
    assert _registered_payload(recorder)["max_connections"] == 1


@pytest.mark.asyncio
async def test_info_shows_how_many_updates_telegram_sends_at_once() -> None:
    recorder = Recorder(webhook_url="https://quotify.example.test/hook", max_connections=1)
    client, http_client = build(recorder)
    out = io.StringIO()

    await info_command(client, out=out, err=io.StringIO())
    await http_client.aclose()

    assert "max_connections: 1" in out.getvalue()  # đủ để kiểm việc đăng ký đã có hiệu lực


@pytest.mark.asyncio
async def test_the_set_preview_shows_the_current_max_connections_next_to_the_new_one() -> None:
    recorder = Recorder(webhook_url="https://old.example.test/hook", max_connections=40)
    client, http_client = build(recorder)
    out = io.StringIO()

    code = await set_webhook_command(
        client,
        cli_settings(app_env="production"),
        yes=False,
        out=out,
        err=io.StringIO(),
    )
    await http_client.aclose()

    assert code == 3
    text = out.getvalue()
    assert "max_connections hiện tại: 40" in text
    assert "max_connections=1" in text  # giá trị sẽ đặt


@pytest.mark.asyncio
async def test_the_preview_of_a_bot_without_a_webhook_does_not_invent_a_current_value() -> None:
    recorder = Recorder(webhook_url="")  # chưa đặt webhook: Telegram không trả max_connections
    client, http_client = build(recorder)
    out = io.StringIO()

    await set_webhook_command(client, cli_settings(), yes=False, out=out, err=io.StringIO())
    await http_client.aclose()

    assert "max_connections hiện tại" not in out.getvalue()
