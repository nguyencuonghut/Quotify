"""Telegram giả cho test E2E: chỉ thư viện chuẩn, không cần mạng, không cần token thật.

Nhận mọi `POST /bot<token>/<method>` như Bot API. `sendMessage` được ghi lại để test đọc bằng
`GET /__sent`; `POST /__block` giả lập người dùng chặn bot (lần gửi sau trả 403); `POST /__reset`
xóa trạng thái. Chạy: `python scripts/fake_telegram_server.py --port 8081`.
"""

from __future__ import annotations

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse


class _State:
    def __init__(self, bot_username: str) -> None:
        self.bot_username = bot_username
        self.lock = threading.Lock()
        self.sent: list[dict[str, Any]] = []
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
            data = json.loads(self.rfile.read(length))
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
            else:
                self._reply({"ok": False, "error_code": 404, "description": "Not Found"}, 404)

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            data = self._read_json()
            if path == "/__reset":
                with state.lock:
                    state.sent.clear()
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
            elif method == "sendMessage":
                with state.lock:
                    if int(data.get("chat_id", 0)) in state.blocked_chats:
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
                    state.sent.append(
                        {
                            "message_id": message_id,
                            "chat_id": data.get("chat_id"),
                            "text": data.get("text"),
                            "parse_mode": data.get("parse_mode"),
                        }
                    )
                self._reply({"ok": True, "result": {"message_id": message_id}})
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
