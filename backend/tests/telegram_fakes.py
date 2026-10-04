"""Công cụ test dùng chung cho các test Telegram: session giả, transport giả, payload mẫu."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
from sqlalchemy.dialects import postgresql

from app.integrations.telegram import TelegramClient

FAKE_TOKEN = "123456789:AAFakeTokenFakeTokenFakeTokenFake12"
WEBHOOK_SECRET = "test_webhook_secret-123"


class FakeResult:
    def __init__(self, value: Any = None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> Any:
        return self._value

    def first(self) -> Any:
        return None


@dataclass
class FakeStore:
    """Trạng thái DB giả: chỉ ghi nhận dữ liệu khi `commit`, bỏ khi `rollback`."""

    processed: set[int] = field(default_factory=set)
    executed: list[str] = field(default_factory=list)
    commits: int = 0
    rollbacks: int = 0
    fail_next: list[Exception] = field(default_factory=list)
    fail_on_delete: Exception | None = None
    fail_on_update: Exception | None = None


class FakeSession:
    def __init__(self, store: FakeStore) -> None:
        self.store = store
        self._pending: set[int] = set()

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(self, *exc_info: object) -> bool:
        return False

    async def execute(self, statement: Any, *args: Any, **kwargs: Any) -> FakeResult:
        if self.store.fail_next:
            raise self.store.fail_next.pop(0)
        compiled = statement.compile(dialect=postgresql.dialect())  # type: ignore[no-untyped-call]
        sql = str(compiled)
        self.store.executed.append(sql)
        if sql.startswith("DELETE") and self.store.fail_on_delete is not None:
            raise self.store.fail_on_delete
        if sql.startswith("UPDATE") and self.store.fail_on_update is not None:
            raise self.store.fail_on_update
        if sql.startswith("INSERT INTO telegram_processed_updates"):
            update_id = compiled.params["update_id"]
            if update_id in self.store.processed or update_id in self._pending:
                return FakeResult(None)
            self._pending.add(update_id)
            return FakeResult(update_id)
        return FakeResult(None)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.store.processed |= self._pending
        self._pending = set()
        self.store.commits += 1

    async def rollback(self) -> None:
        self._pending = set()
        self.store.rollbacks += 1


def make_session_factory(store: FakeStore) -> Callable[[], FakeSession]:
    return lambda: FakeSession(store)


@dataclass
class Outbox:
    """Ghi lại mọi request gửi tới Telegram (qua MockTransport)."""

    requests: list[httpx.Request] = field(default_factory=list)
    status_code: int = 200
    # Chat bị Telegram từ chối (403 "bot was blocked"), các chat khác vẫn gửi được.
    forbidden_chat_ids: set[int] = field(default_factory=set)

    def sent_messages(self) -> list[dict[str, Any]]:
        return [
            json.loads(request.content)
            for request in self.requests
            if request.url.path.endswith("/sendMessage")
        ]

    def texts_to(self, chat_id: int) -> list[str]:
        return [item["text"] for item in self.sent_messages() if item["chat_id"] == chat_id]


def make_client(outbox: Outbox) -> tuple[TelegramClient, httpx.AsyncClient]:
    def handler(request: httpx.Request) -> httpx.Response:
        outbox.requests.append(request)
        chat_id = json.loads(request.content or b"{}").get("chat_id")
        if chat_id in outbox.forbidden_chat_ids:
            return httpx.Response(
                403,
                json={"ok": False, "error_code": 403, "description": "Forbidden: bot was blocked"},
            )
        if outbox.status_code != 200:
            return httpx.Response(
                outbox.status_code,
                json={"ok": False, "error_code": outbox.status_code, "description": "error"},
            )
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 99}})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return TelegramClient(token=FAKE_TOKEN, http_client=http_client), http_client


def make_update(
    update_id: int = 1,
    text: str = "/help",
    *,
    chat_type: str = "private",
    user_id: int = 111,
    chat_id: int | None = None,
    first_name: str = "An",
    username: str | None = None,
) -> dict[str, Any]:
    sender: dict[str, Any] = {"id": user_id, "is_bot": False, "first_name": first_name}
    if username is not None:
        sender["username"] = username
    return {
        "update_id": update_id,
        "message": {
            "message_id": 5,
            "date": 0,
            "text": text,
            "chat": {"id": chat_id if chat_id is not None else user_id, "type": chat_type},
            "from": sender,
        },
    }
