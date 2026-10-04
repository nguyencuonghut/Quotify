from __future__ import annotations

import threading
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
