"""Cổng giữa đường ống chatbot và "bộ não" (LLM, công cụ, bộ nhớ) - kế hoạch 5.1, mục 4.6.

Đường ống chỉ biết cổng này; 5.2 đến 5.6 cài `ChatEngine` thật mà không đụng hàng đợi, khóa
hay đường gửi tin.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.bot_principal import BotPrincipal
from app.services.telegram_bot_messages import STUB_REPLY_TEXT


class ChatEngineTemporaryError(Exception):
    """Lỗi tạm thời của engine (hết thời gian, lỗi mạng, 5xx, 429): đường ống thử lại được."""


class ChatEngineError(Exception):
    """Lỗi cuối của engine (cấu hình, chính sách): không thử lại."""


@dataclass(frozen=True, slots=True)
class ChatTurn:
    update_id: int
    chat_id: int
    telegram_user_id: int
    # Người dùng ACTIVE và quyền, nạp mới ở mỗi tin.
    principal: BotPrincipal
    # `repr=False`: nội dung tin không được lọt vào log.
    text: str = field(repr=False)
    # Có múi giờ (UTC); đổi sang Asia/Ho_Chi_Minh ở nơi hiển thị.
    received_at: datetime
    # Gọi như `async_sessionmaker` để mở một phiên chỉ đọc (rào chắn, không phải ranh giới bảo
    # mật, RC-27); `None` khi ngữ cảnh không có (vd test). Mỗi lần gọi công cụ mở một phiên ngắn,
    # không commit.
    readonly_session_factory: Callable[[], AsyncSession] | None = None


@dataclass(frozen=True, slots=True)
class ChatReply:
    text: str


class ChatEngine(Protocol):
    async def reply(self, turn: ChatTurn) -> ChatReply: ...


class StubChatEngine:
    """Trả một câu cố định, để chạy thử đường ống đủ từ đầu đến cuối khi chưa có LLM.

    `delay_seconds` chỉ để thử trên dev (mô phỏng LLM chậm); production luôn là 0.
    """

    def __init__(self, delay_seconds: float = 0.0) -> None:
        self._delay = delay_seconds

    async def reply(self, turn: ChatTurn) -> ChatReply:
        if self._delay > 0:
            await asyncio.sleep(self._delay)
        return ChatReply(STUB_REPLY_TEXT)
