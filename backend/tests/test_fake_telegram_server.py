from __future__ import annotations

import threading
import time
from collections.abc import Iterator

import httpx
import pytest

from scripts.fake_telegram_server import make_server


@pytest.fixture
def base_url() -> Iterator[str]:
    server = make_server("127.0.0.1", 0, bot_username="quotify_e2e_bot")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_health_endpoint_is_ok(base_url: str) -> None:
    assert httpx.get(f"{base_url}/health").status_code == 200


def test_get_me_reports_the_configured_username_for_any_token(base_url: str) -> None:
    response = httpx.post(f"{base_url}/bot1234:whatever-token/getMe", json={})

    assert response.json() == {
        "ok": True,
        "result": {"id": 1, "is_bot": True, "username": "quotify_e2e_bot"},
    }


def test_sent_messages_are_recorded_and_can_be_listed_and_reset(base_url: str) -> None:
    first = httpx.post(
        f"{base_url}/botT/sendMessage",
        json={"chat_id": 555, "text": "Xin chào", "parse_mode": "HTML"},
    )
    httpx.post(f"{base_url}/botT/sendMessage", json={"chat_id": 777, "text": "Khác"})

    assert first.json()["ok"] is True
    assert first.json()["result"]["message_id"] == 1
    sent = httpx.get(f"{base_url}/__sent").json()
    assert [(m["chat_id"], m["text"]) for m in sent] == [(555, "Xin chào"), (777, "Khác")]
    assert httpx.get(f"{base_url}/__sent", params={"chat_id": 777}).json() == [sent[1]]

    httpx.post(f"{base_url}/__reset")
    assert httpx.get(f"{base_url}/__sent").json() == []


def test_other_bot_methods_succeed_without_side_effects(base_url: str) -> None:
    for method in ("setWebhook", "deleteWebhook", "setMyCommands"):
        response = httpx.post(f"{base_url}/botT/{method}", json={})
        assert response.json() == {"ok": True, "result": True}
    assert httpx.get(f"{base_url}/__sent").json() == []


def test_a_chat_can_be_marked_as_blocking_the_bot(base_url: str) -> None:
    httpx.post(f"{base_url}/__block", json={"chat_id": 999})

    blocked = httpx.post(f"{base_url}/botT/sendMessage", json={"chat_id": 999, "text": "x"})

    assert blocked.status_code == 403
    assert blocked.json() == {
        "ok": False,
        "error_code": 403,
        "description": "Forbidden: bot was blocked by the user",
    }
    assert httpx.get(f"{base_url}/__sent").json() == []


def test_send_photo_multipart_is_recorded_and_returns_message_id(base_url: str) -> None:
    response = httpx.post(
        f"{base_url}/botT/sendPhoto",
        data={
            "chat_id": "555",
            "caption": "Biểu đồ giá",
            "parse_mode": "HTML",
            "reply_markup": '{"inline_keyboard": []}',
        },
        files={"photo": ("chart.png", b"\x89PNG" + b"\x00" * 10, "image/png")},
    )

    assert response.json() == {"ok": True, "result": {"message_id": 1}}
    [item] = httpx.get(f"{base_url}/__sent").json()
    assert item["chat_id"] == 555
    assert item["caption"] == "Biểu đồ giá"
    assert item["photo_bytes"] == 14
    assert item["reply_markup"] == '{"inline_keyboard": []}'
    assert httpx.get(f"{base_url}/__sent", params={"chat_id": 555}).json() == [item]


def test_send_photo_to_a_blocked_chat_returns_403(base_url: str) -> None:
    httpx.post(f"{base_url}/__block", json={"chat_id": 999})

    response = httpx.post(
        f"{base_url}/botT/sendPhoto",
        data={"chat_id": "999", "caption": "x"},
        files={"photo": ("chart.png", b"png", "image/png")},
    )

    assert response.status_code == 403
    assert httpx.get(f"{base_url}/__sent").json() == []


def test_edit_and_callback_methods_are_recorded_and_reset(base_url: str) -> None:
    for method in ("editMessageText", "editMessageCaption", "editMessageReplyMarkup"):
        response = httpx.post(
            f"{base_url}/botT/{method}", json={"chat_id": 5, "message_id": 8, "text": "t"}
        )
        assert response.json() == {"ok": True, "result": {"message_id": 8}}
    answer = httpx.post(f"{base_url}/botT/answerCallbackQuery", json={"callback_query_id": "c1"})

    assert answer.json() == {"ok": True, "result": True}
    edits = httpx.get(f"{base_url}/__edits").json()
    assert [e["method"] for e in edits] == [
        "editMessageText",
        "editMessageCaption",
        "editMessageReplyMarkup",
    ]
    assert httpx.get(f"{base_url}/__callback_answers").json() == [{"callback_query_id": "c1"}]

    httpx.post(f"{base_url}/__reset")
    assert httpx.get(f"{base_url}/__edits").json() == []
    assert httpx.get(f"{base_url}/__callback_answers").json() == []


def test_chat_actions_are_recorded_and_can_be_listed_and_reset(base_url: str) -> None:
    response = httpx.post(
        f"{base_url}/botT/sendChatAction", json={"chat_id": 555, "action": "typing"}
    )

    assert response.json() == {"ok": True, "result": True}
    assert httpx.get(f"{base_url}/__chat_actions").json() == [{"chat_id": 555, "action": "typing"}]
    assert httpx.get(f"{base_url}/__sent").json() == []  # không lẫn với tin nhắn

    httpx.post(f"{base_url}/__reset")
    assert httpx.get(f"{base_url}/__chat_actions").json() == []


def test_the_next_sends_can_be_made_to_fail_with_a_retry_after(base_url: str) -> None:
    httpx.post(f"{base_url}/__fail_next", json={"count": 2, "error_code": 429, "retry_after": 3})

    first = httpx.post(f"{base_url}/botT/sendMessage", json={"chat_id": 5, "text": "a"})
    second = httpx.post(f"{base_url}/botT/sendMessage", json={"chat_id": 5, "text": "b"})
    third = httpx.post(f"{base_url}/botT/sendMessage", json={"chat_id": 5, "text": "c"})

    assert first.status_code == second.status_code == 429
    assert first.json() == {
        "ok": False,
        "error_code": 429,
        "description": "Too Many Requests: retry after 3",
        "parameters": {"retry_after": 3},
    }
    assert third.json()["ok"] is True
    assert [m["text"] for m in httpx.get(f"{base_url}/__sent").json()] == ["c"]  # lần lỗi không ghi


def test_failures_without_a_retry_after_and_the_reset_of_the_failure_script(
    base_url: str,
) -> None:
    httpx.post(f"{base_url}/__fail_next", json={"count": 5, "error_code": 500})

    failed = httpx.post(f"{base_url}/botT/sendMessage", json={"chat_id": 5, "text": "a"})
    httpx.post(f"{base_url}/__reset")  # reset xóa luôn kịch bản lỗi còn lại
    fine = httpx.post(f"{base_url}/botT/sendMessage", json={"chat_id": 5, "text": "b"})

    assert failed.status_code == 500
    assert "parameters" not in failed.json()
    assert fine.json()["ok"] is True


def test_sends_can_be_delayed(base_url: str) -> None:
    httpx.post(f"{base_url}/__delay", json={"seconds": 0.3})

    started = time.monotonic()
    httpx.post(f"{base_url}/botT/sendMessage", json={"chat_id": 5, "text": "chậm"})

    assert time.monotonic() - started >= 0.3


def test_failure_descriptions_match_the_error_code(base_url: str) -> None:
    descriptions = {}
    for code in (429, 403, 500):
        httpx.post(f"{base_url}/__fail_next", json={"count": 1, "error_code": code})
        response = httpx.post(f"{base_url}/botT/sendMessage", json={"chat_id": 5, "text": "a"})
        descriptions[code] = response.json()["description"]

    assert descriptions == {
        429: "Too Many Requests",
        403: "Forbidden: bot was blocked by the user",
        500: "Internal Server Error",
    }
