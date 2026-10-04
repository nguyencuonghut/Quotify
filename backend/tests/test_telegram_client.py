from __future__ import annotations

import json

import httpx
import pytest

from app.integrations.telegram import TelegramClient

FAKE_TOKEN = "123456789:AAFakeTokenFakeTokenFakeTokenFake12"


def make_client(
    handler: httpx.MockTransport | None = None,
    *,
    api_base_url: str = "https://api.telegram.org",
) -> tuple[TelegramClient, httpx.AsyncClient]:
    http_client = httpx.AsyncClient(transport=handler)
    client = TelegramClient(
        token=FAKE_TOKEN,
        api_base_url=api_base_url,
        timeout_seconds=5,
        http_client=http_client,
    )
    return client, http_client


@pytest.mark.asyncio
async def test_get_me_returns_bot_info() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "ok": True,
                "result": {
                    "id": 987654321,
                    "is_bot": True,
                    "first_name": "Quotify Dev",
                    "username": "quotify_dev_bot",
                },
            },
        )

    client, http_client = make_client(httpx.MockTransport(handler))

    bot = await client.get_me()
    await http_client.aclose()

    assert bot.id == 987654321
    assert bot.username == "quotify_dev_bot"
    assert bot.first_name == "Quotify Dev"
    assert len(seen) == 1
    assert seen[0].url.path == f"/bot{FAKE_TOKEN}/getMe"
    assert json.loads(seen[0].content or b"{}") == {}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "body", "expected_type", "expected_retry_after"),
    [
        (401, {"ok": False, "error_code": 401, "description": "Unauthorized"}, None, None),
        (
            403,
            {"ok": False, "error_code": 403, "description": "Forbidden: bot was blocked"},
            "forbidden",
            None,
        ),
        (
            429,
            {
                "ok": False,
                "error_code": 429,
                "description": "Too Many Requests",
                "parameters": {"retry_after": 7},
            },
            "rate_limit",
            7,
        ),
        (400, {"ok": False, "error_code": 400, "description": "Bad Request"}, None, None),
    ],
)
async def test_api_errors_are_mapped_to_typed_exceptions(
    status_code: int,
    body: dict[str, object],
    expected_type: str | None,
    expected_retry_after: int | None,
) -> None:
    from app.integrations.telegram import (
        TelegramApiError,
        TelegramForbiddenError,
        TelegramRateLimitError,
    )

    client, http_client = make_client(
        httpx.MockTransport(lambda request: httpx.Response(status_code, json=body)),
    )

    with pytest.raises(TelegramApiError) as exc_info:
        await client.get_me()
    await http_client.aclose()

    error = exc_info.value
    assert error.error_code == status_code
    assert error.retry_after == expected_retry_after
    if expected_type == "forbidden":
        assert isinstance(error, TelegramForbiddenError)
    elif expected_type == "rate_limit":
        assert isinstance(error, TelegramRateLimitError)
    else:
        assert not isinstance(error, TelegramForbiddenError | TelegramRateLimitError)


@pytest.mark.asyncio
async def test_non_json_response_is_reported_as_api_error() -> None:
    from app.integrations.telegram import TelegramApiError

    client, http_client = make_client(
        httpx.MockTransport(lambda request: httpx.Response(502, text="<html>bad gateway</html>")),
    )

    with pytest.raises(TelegramApiError) as exc_info:
        await client.get_me()
    await http_client.aclose()

    assert exc_info.value.error_code == 502


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "raised",
    [
        httpx.ConnectError(f"boom https://api.telegram.org/bot{FAKE_TOKEN}/getMe"),
        httpx.ReadTimeout(f"timeout https://api.telegram.org/bot{FAKE_TOKEN}/getMe"),
    ],
)
async def test_network_errors_never_leak_the_token(raised: httpx.HTTPError) -> None:
    import traceback

    from app.integrations.telegram import TelegramNetworkError

    def handler(request: httpx.Request) -> httpx.Response:
        raise raised

    client, http_client = make_client(httpx.MockTransport(handler))

    with pytest.raises(TelegramNetworkError) as exc_info:
        await client.get_me()
    await http_client.aclose()

    error = exc_info.value
    rendered = "".join(traceback.format_exception(error))
    assert FAKE_TOKEN not in str(error)
    assert FAKE_TOKEN not in repr(error)
    assert FAKE_TOKEN not in rendered
    assert error.__cause__ is None
    assert error.__suppress_context__ is True


def test_client_repr_hides_the_token() -> None:
    client = TelegramClient(token=FAKE_TOKEN)

    assert FAKE_TOKEN not in repr(client)
    assert FAKE_TOKEN not in str(client)


@pytest.mark.asyncio
async def test_send_message_sends_html_and_returns_message_id() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 42}})

    client, http_client = make_client(httpx.MockTransport(handler))

    message_id = await client.send_message(555, "<b>Xin chào</b>")
    await http_client.aclose()

    assert message_id == 42
    payload = json.loads(seen[0].content)
    assert payload["chat_id"] == 555
    assert payload["text"] == "<b>Xin chào</b>"
    assert payload["parse_mode"] == "HTML"
    assert seen[0].url.path.endswith("/sendMessage")


@pytest.mark.asyncio
async def test_send_message_rejects_text_longer_than_telegram_limit() -> None:
    from app.integrations.telegram import TelegramMessageTooLongError

    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    client, http_client = make_client(httpx.MockTransport(handler))

    with pytest.raises(TelegramMessageTooLongError):
        await client.send_message(1, "x" * 4097)
    await http_client.aclose()

    assert requests == []


def test_escape_html_only_escapes_markup_characters() -> None:
    from app.integrations.telegram import escape_html

    assert escape_html("A & B <tag> 'q' \"d\"") == "A &amp; B &lt;tag&gt; 'q' \"d\""


@pytest.mark.asyncio
async def test_set_webhook_and_delete_webhook_payloads() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"ok": True, "result": True})

    client, http_client = make_client(httpx.MockTransport(handler))

    await client.set_webhook(
        url="https://example.test/api/v1/telegram/webhook",
        secret_token="s3cret_value-1",
        allowed_updates=["message", "my_chat_member"],
        drop_pending_updates=True,
    )
    await client.delete_webhook(drop_pending_updates=False)
    await http_client.aclose()

    assert json.loads(seen[0].content) == {
        "url": "https://example.test/api/v1/telegram/webhook",
        "secret_token": "s3cret_value-1",
        "allowed_updates": ["message", "my_chat_member"],
        "drop_pending_updates": True,
    }
    assert json.loads(seen[1].content) == {"drop_pending_updates": False}


@pytest.mark.asyncio
async def test_get_updates_uses_offset_and_a_longer_http_timeout() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={"ok": True, "result": [{"update_id": 10, "message": {"text": "/help"}}]},
        )

    client, http_client = make_client(httpx.MockTransport(handler))

    updates = await client.get_updates(
        offset=11,
        timeout_seconds=25,
        allowed_updates=["message"],
    )
    await http_client.aclose()

    assert updates == [{"update_id": 10, "message": {"text": "/help"}}]
    payload = json.loads(seen[0].content)
    assert payload["offset"] == 11
    assert payload["timeout"] == 25
    assert seen[0].extensions["timeout"]["read"] == 35
