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


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.mark.asyncio
async def test_send_photo_is_multipart_with_photo_caption_and_json_reply_markup() -> None:
    from scripts.fake_telegram_server import parse_multipart

    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 77}})

    client, http_client = make_client(httpx.MockTransport(handler))
    markup = {"inline_keyboard": [[{"text": "Đã xem", "callback_data": "ack:1"}]]}

    message_id = await client.send_photo(555, PNG_BYTES, "<b>Giá</b> tăng", reply_markup=markup)
    await http_client.aclose()

    assert message_id == 77
    assert seen[0].url.path == f"/bot{FAKE_TOKEN}/sendPhoto"
    content_type = seen[0].headers["content-type"]
    assert content_type.startswith("multipart/form-data")
    fields, files = parse_multipart(content_type, seen[0].content)
    assert files == {"photo": PNG_BYTES}
    assert fields["chat_id"] == "555"
    assert fields["caption"] == "<b>Giá</b> tăng"
    assert fields["parse_mode"] == "HTML"
    assert json.loads(fields["reply_markup"]) == markup


@pytest.mark.asyncio
async def test_send_photo_rejects_caption_over_1024_before_any_request() -> None:
    from app.integrations.telegram import TelegramMessageTooLongError

    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    client, http_client = make_client(httpx.MockTransport(handler))

    with pytest.raises(TelegramMessageTooLongError):
        await client.send_photo(1, PNG_BYTES, "x" * 1025)
    assert requests == []

    assert await client.send_photo(1, PNG_BYTES, "x" * 1024) == 1
    await http_client.aclose()
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_send_photo_network_error_does_not_leak_the_token() -> None:
    import traceback

    from app.integrations.telegram import TelegramNetworkError

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    client, http_client = make_client(httpx.MockTransport(handler))

    with pytest.raises(TelegramNetworkError) as exc_info:
        await client.send_photo(1, PNG_BYTES, "cap")
    await http_client.aclose()

    error = exc_info.value
    assert FAKE_TOKEN not in "".join(traceback.format_exception(error))
    assert error.__cause__ is None
    assert error.__suppress_context__ is True


@pytest.mark.asyncio
async def test_answer_callback_query_payload() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"ok": True, "result": True})

    client, http_client = make_client(httpx.MockTransport(handler))

    await client.answer_callback_query("cb1")
    await client.answer_callback_query("cb2", "Đã ghi nhận", show_alert=True)
    await http_client.aclose()

    assert seen[0].url.path.endswith("/answerCallbackQuery")
    assert json.loads(seen[0].content) == {"callback_query_id": "cb1"}
    assert json.loads(seen[1].content) == {
        "callback_query_id": "cb2",
        "text": "Đã ghi nhận",
        "show_alert": True,
    }


@pytest.mark.asyncio
async def test_edit_methods_send_expected_payloads_and_report_success() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 9}})

    client, http_client = make_client(httpx.MockTransport(handler))
    markup = {"inline_keyboard": [[{"text": "A", "callback_data": "a"}]]}

    assert await client.edit_message_text(5, 9, "Mới", reply_markup=markup) is True
    assert await client.edit_message_caption(5, 9, "Cap mới") is True
    assert await client.edit_message_reply_markup(5, 9) is True
    await http_client.aclose()

    assert [r.url.path.rsplit("/", 1)[-1] for r in seen] == [
        "editMessageText",
        "editMessageCaption",
        "editMessageReplyMarkup",
    ]
    text_payload = json.loads(seen[0].content)
    assert text_payload["text"] == "Mới"
    assert text_payload["message_id"] == 9
    assert text_payload["parse_mode"] == "HTML"
    assert text_payload["reply_markup"] == markup
    assert json.loads(seen[1].content)["caption"] == "Cap mới"
    assert json.loads(seen[2].content) == {
        "chat_id": 5,
        "message_id": 9,
        "reply_markup": {"inline_keyboard": []},
    }


@pytest.mark.asyncio
async def test_edit_not_modified_is_success_but_other_400_still_raises() -> None:
    from app.integrations.telegram import TelegramApiError

    not_modified = "Bad Request: message is not modified: specified new message content"
    descriptions = iter(
        [
            not_modified,
            not_modified,
            not_modified,
            "Bad Request: there is no text in the message to edit",
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={"ok": False, "error_code": 400, "description": next(descriptions)},
        )

    client, http_client = make_client(httpx.MockTransport(handler))

    assert await client.edit_message_text(1, 2, "x") is False
    assert await client.edit_message_caption(1, 2, "x") is False
    assert await client.edit_message_reply_markup(1, 2) is False
    with pytest.raises(TelegramApiError) as exc_info:
        await client.edit_message_text(1, 2, "x")
    await http_client.aclose()

    assert exc_info.value.error_code == 400


@pytest.mark.asyncio
async def test_edit_length_limits_are_checked_before_any_request() -> None:
    from app.integrations.telegram import TelegramMessageTooLongError

    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "result": True})

    client, http_client = make_client(httpx.MockTransport(handler))

    with pytest.raises(TelegramMessageTooLongError):
        await client.edit_message_text(1, 2, "x" * 4097)
    with pytest.raises(TelegramMessageTooLongError):
        await client.edit_message_caption(1, 2, "x" * 1025)
    await http_client.aclose()

    assert requests == []


@pytest.mark.asyncio
async def test_send_message_can_be_silent() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 7}})

    client, http_client = make_client(httpx.MockTransport(handler))

    await client.send_message(1, "a", disable_notification=True)
    await client.send_message(1, "b")
    await http_client.aclose()

    assert json.loads(seen[0].content)["disable_notification"] is True
    assert "disable_notification" not in json.loads(seen[1].content)
