"""Công cụ test dùng chung cho các test Telegram: session giả, transport giả, payload mẫu."""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
from sqlalchemy.dialects import postgresql

from app.integrations.telegram import TelegramClient
from scripts.fake_telegram_server import parse_multipart

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
    # Phản hồi dựng sẵn theo phương thức (vd `sendMessage`), lấy lần lượt; hết thì trả lời thường.
    scripted: dict[str, list[tuple[int, dict[str, Any]]]] = field(default_factory=dict)

    def script(self, method: str, *responses: tuple[int, dict[str, Any]]) -> None:
        """Lên kịch bản các phản hồi kế tiếp của một phương thức: (mã HTTP, thân JSON)."""
        self.scripted.setdefault(method, []).extend(responses)

    def chat_actions(self) -> list[dict[str, Any]]:
        return [
            json.loads(request.content)
            for request in self.requests
            if request.url.path.endswith("/sendChatAction")
        ]

    def sent_photos(self) -> list[dict[str, Any]]:
        """Các sendPhoto đã gửi: trường form + `photo_bytes` (kích thước tệp ảnh)."""
        photos: list[dict[str, Any]] = []
        for request in self.requests:
            if request.url.path.endswith("/sendPhoto"):
                fields, files = parse_multipart(request.headers["content-type"], request.content)
                photos.append({**fields, "photo_bytes": len(files.get("photo", b""))})
        return photos

    def edits(self) -> list[dict[str, Any]]:
        names = ("editMessageText", "editMessageCaption", "editMessageReplyMarkup")
        return [
            {"method": request.url.path.rsplit("/", 1)[-1], **json.loads(request.content)}
            for request in self.requests
            if request.url.path.rsplit("/", 1)[-1] in names
        ]

    def callback_answers(self) -> list[dict[str, Any]]:
        return [
            json.loads(request.content)
            for request in self.requests
            if request.url.path.endswith("/answerCallbackQuery")
        ]

    def sent_messages(self) -> list[dict[str, Any]]:
        return [
            json.loads(request.content)
            for request in self.requests
            if request.url.path.endswith("/sendMessage")
        ]

    def texts_to(self, chat_id: int) -> list[str]:
        return [item["text"] for item in self.sent_messages() if item["chat_id"] == chat_id]


class FakeBotDispatcher:
    """Bên đánh chuông giả của đường ống chatbot: ghi lại các lần `notify`."""

    def __init__(self) -> None:
        self.notified: list[tuple[int, int]] = []

    async def notify(self, chat_id: int, update_id: int) -> None:
        self.notified.append((chat_id, update_id))

    async def aclose(self) -> None:
        return None


def make_client(outbox: Outbox) -> tuple[TelegramClient, httpx.AsyncClient]:
    def handler(request: httpx.Request) -> httpx.Response:
        outbox.requests.append(request)
        content_type = request.headers.get("content-type", "")
        if content_type.startswith("multipart/form-data"):
            fields, _ = parse_multipart(content_type, request.content)
            chat_id: Any = int(fields["chat_id"]) if "chat_id" in fields else None
        else:
            chat_id = json.loads(request.content or b"{}").get("chat_id")
        queued = outbox.scripted.get(request.url.path.rsplit("/", 1)[-1])
        if queued:
            status, body = queued.pop(0)
            return httpx.Response(status, json=body)
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


# Phần thân tối thiểu của từng loại tin không phải văn bản (đúng khóa của Bot API, không tệp thật).
_MEDIA_BODIES: dict[str, dict[str, Any]] = {
    # Ảnh thật là một mảng nhiều cỡ; GIF thật có cả `animation` lẫn `document`.
    "photo": {
        "photo": [
            {"file_id": "p-s", "file_unique_id": "u1", "width": 90, "height": 90},
            {"file_id": "p-m", "file_unique_id": "u2", "width": 320, "height": 320},
            {"file_id": "p-l", "file_unique_id": "u3", "width": 800, "height": 800},
        ]
    },
    "document": {"document": {"file_id": "d1", "file_unique_id": "u4", "file_name": "bao-gia.pdf"}},
    "voice": {"voice": {"file_id": "v1", "file_unique_id": "u5", "duration": 3}},
    "sticker": {"sticker": {"file_id": "s1", "file_unique_id": "u6", "width": 512, "height": 512}},
    "animation": {
        "animation": {"file_id": "g1", "file_unique_id": "u7", "duration": 2},
        "document": {"file_id": "g1", "file_unique_id": "u7", "file_name": "vui.mp4"},
    },
}


def make_media_update(
    update_id: int,
    kind: str,
    *,
    user_id: int = 111,
    chat_type: str = "private",
    caption: str | None = None,
    media_group_id: str | None = None,
) -> dict[str, Any]:
    """Update của tin KHÔNG có `text` (ảnh, tài liệu, giọng nói, sticker), tùy chọn `caption`.

    `media_group_id` giống nhau cho mọi ảnh của một album (mỗi ảnh vẫn là một update riêng).
    """
    payload = make_update(update_id, "", chat_type=chat_type, user_id=user_id)
    message = payload["message"]
    del message["text"]
    message.update(copy.deepcopy(_MEDIA_BODIES[kind]))
    if caption is not None:
        message["caption"] = caption
    if media_group_id is not None:
        message["media_group_id"] = media_group_id
    return payload
