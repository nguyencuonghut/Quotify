"""Telegram giả cho test E2E: chỉ thư viện chuẩn, không cần mạng, không cần token thật.

Nhận mọi `POST /bot<token>/<method>` như Bot API. `sendMessage` được ghi lại để test đọc bằng
`GET /__sent`; `POST /__block` giả lập người dùng chặn bot (lần gửi sau trả 403); `POST /__reset`
xóa trạng thái. Chạy: `python scripts/fake_telegram_server.py --port 8081`.
"""

from __future__ import annotations

import argparse
import json
import threading
from email.parser import BytesParser
from email.policy import HTTP
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse


def parse_multipart(content_type: str, body: bytes) -> tuple[dict[str, Any], dict[str, bytes]]:
    """Tách body `multipart/form-data` thành (trường văn bản, tệp tải lên)."""
    message = BytesParser(policy=HTTP).parsebytes(
        b"Content-Type: " + content_type.encode() + b"\r\n\r\n" + body
    )
    fields: dict[str, Any] = {}
    files: dict[str, bytes] = {}
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if not isinstance(name, str):
            continue
        payload = part.get_payload(decode=True)
        raw = payload if isinstance(payload, bytes) else b""
        if part.get_filename():
            files[name] = raw
        else:
            fields[name] = raw.decode()
    return fields, files


def _as_int(value: Any) -> Any:
    # multipart gửi mọi trường dưới dạng chuỗi; chat_id được trả lại dạng số như JSON.
    return int(value) if isinstance(value, str) and value.lstrip("-").isdigit() else value


class _State:
    def __init__(self, bot_username: str) -> None:
        self.bot_username = bot_username
        self.lock = threading.Lock()
        self.sent: list[dict[str, Any]] = []
        self.edits: list[dict[str, Any]] = []
        self.callback_answers: list[dict[str, Any]] = []
        self.blocked_chats: set[int] = set()


def _make_handler(state: _State) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return  # không in request ra log: URL của Bot API chứa token

        def _reply(self, payload: Any, status: int = 200) -> None:
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or 0)
            if not length:
                return {}
            raw = self.rfile.read(length)
            content_type = self.headers.get("Content-Type") or ""
            if content_type.startswith("multipart/form-data"):
                fields, files = parse_multipart(content_type, raw)
                for name, content in files.items():
                    fields[f"{name}_bytes"] = len(content)
                return fields
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self._reply({"ok": True})
            elif parsed.path == "/__sent":
                chat = parse_qs(parsed.query).get("chat_id")
                with state.lock:
                    items = list(state.sent)
                if chat:
                    items = [item for item in items if str(item["chat_id"]) == chat[0]]
                self._reply(items)
            elif parsed.path == "/__edits":
                with state.lock:
                    self._reply(list(state.edits))
            elif parsed.path == "/__callback_answers":
                with state.lock:
                    self._reply(list(state.callback_answers))
            else:
                self._reply({"ok": False, "error_code": 404, "description": "Not Found"}, 404)

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            data = self._read_json()
            if path == "/__reset":
                with state.lock:
                    state.sent.clear()
                    state.edits.clear()
                    state.callback_answers.clear()
                    state.blocked_chats.clear()
                self._reply({"ok": True})
            elif path == "/__block":
                with state.lock:
                    state.blocked_chats.add(int(data["chat_id"]))
                self._reply({"ok": True})
            elif path.startswith("/bot"):
                self._handle_bot_method(path.rsplit("/", 1)[-1], data)
            else:
                self._reply({"ok": False, "error_code": 404, "description": "Not Found"}, 404)

        def _handle_bot_method(self, method: str, data: dict[str, Any]) -> None:
            if method == "getMe":
                self._reply(
                    {
                        "ok": True,
                        "result": {"id": 1, "is_bot": True, "username": state.bot_username},
                    }
                )
            elif method in ("sendMessage", "sendPhoto"):
                with state.lock:
                    if _as_int(data.get("chat_id", 0)) in state.blocked_chats:
                        self._reply(
                            {
                                "ok": False,
                                "error_code": 403,
                                "description": "Forbidden: bot was blocked by the user",
                            },
                            403,
                        )
                        return
                    message_id = len(state.sent) + 1
                    item: dict[str, Any] = {
                        "message_id": message_id,
                        "chat_id": _as_int(data.get("chat_id")),
                        "text": data.get("text"),
                        "parse_mode": data.get("parse_mode"),
                    }
                    if method == "sendPhoto":
                        item["caption"] = data.get("caption")
                        item["photo_bytes"] = data.get("photo_bytes", 0)
                        item["reply_markup"] = data.get("reply_markup")
                    state.sent.append(item)
                self._reply({"ok": True, "result": {"message_id": message_id}})
            elif method in ("editMessageText", "editMessageCaption", "editMessageReplyMarkup"):
                with state.lock:
                    state.edits.append({"method": method, **data})
                self._reply({"ok": True, "result": {"message_id": data.get("message_id")}})
            elif method == "answerCallbackQuery":
                with state.lock:
                    state.callback_answers.append(data)
                self._reply({"ok": True, "result": True})
            else:
                self._reply({"ok": True, "result": True})

    return Handler


def make_server(
    host: str, port: int, *, bot_username: str = "quotify_e2e_bot"
) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), _make_handler(_State(bot_username)))


def main() -> None:
    parser = argparse.ArgumentParser(description="Telegram Bot API giả cho test E2E.")
    parser.add_argument("--host", default="0.0.0.0")  # noqa: S104 - chỉ chạy trong mạng compose test
    parser.add_argument("--port", type=int, default=8081)
    parser.add_argument("--bot-username", default="quotify_e2e_bot")
    args = parser.parse_args()
    make_server(args.host, args.port, bot_username=args.bot_username).serve_forever()


if __name__ == "__main__":
    main()
