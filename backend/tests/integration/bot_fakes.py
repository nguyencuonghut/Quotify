"""Engine và client Telegram giả dùng chung cho các test của worker chatbot (ranh giới hệ thống)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.integrations.telegram import TelegramNetworkError
from app.services import bot_reply_sender
from app.services.chat_engine import ChatReply, ChatTurn


class ScriptedEngine:
    """Engine giả theo kịch bản: mỗi lần gọi lấy một bước (ngoại lệ thì ném, chuỗi thì trả lời)."""

    def __init__(self, *steps: BaseException | str) -> None:
        self._steps = list(steps)
        self.calls = 0

    async def reply(self, turn: ChatTurn) -> ChatReply:
        self.calls += 1
        step = self._steps.pop(0) if self._steps else "ok"
        if isinstance(step, BaseException):
            raise step
        return ChatReply(step)


class GateEngine:
    """Kẹt cho đến khi được mở; ghi lại là đã bắt đầu."""

    def __init__(self, answer: str = "ok") -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.calls = 0
        self._answer = answer

    async def reply(self, turn: ChatTurn) -> ChatReply:
        self.calls += 1
        self.started.set()
        await self.release.wait()
        return ChatReply(self._answer)


class RecordingClient:
    """Client Telegram giả: ghi lại mọi lần gọi.

    `steps`: kịch bản cho từng lần `send_message` (None là thành công, ngoại lệ thì ném); hết kịch
    bản thì thành công. `fail_first` lần đầu hoặc `always_fail` thì lỗi mạng (không cần kịch bản).
    """

    def __init__(
        self,
        *steps: BaseException | None,
        fail_first: int = 0,
        always_fail: bool = False,
    ) -> None:
        self._steps = list(steps)
        self._fail_first = fail_first
        self._always_fail = always_fail
        self.attempts: list[tuple[int, str]] = []
        self.sent: list[tuple[int, str]] = []
        self.kwargs: list[dict[str, Any]] = []
        self.chat_actions: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text_: str, **kwargs: Any) -> int:
        self.attempts.append((chat_id, text_))
        self.kwargs.append(kwargs)
        if self._steps:
            step = self._steps.pop(0)
            if step is not None:
                raise step
        elif self._always_fail or len(self.attempts) <= self._fail_first:
            raise TelegramNetworkError("Không thể gọi Telegram (sendMessage): ConnectError.")
        self.sent.append((chat_id, text_))
        return 1

    async def send_chat_action(self, chat_id: int, action: str = "typing") -> bool:
        self.chat_actions.append((chat_id, action))
        return True


class FakeClock:
    """Đồng hồ giả cho đường gửi: `wait` không ngủ thật mà chỉ đẩy thời gian đi."""

    def __init__(self) -> None:
        self._now = 1000.0
        self.waited: list[float] = []

    def now(self) -> float:
        return self._now

    async def wait(self, seconds: float) -> None:
        self.waited.append(seconds)
        self._now += seconds

    def install(self, monkeypatch: pytest.MonkeyPatch) -> FakeClock:
        monkeypatch.setattr(bot_reply_sender, "_now", self.now)
        monkeypatch.setattr(bot_reply_sender, "_wait", self.wait)
        return self
