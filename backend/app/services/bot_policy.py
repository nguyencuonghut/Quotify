from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.usage_gate import TurnLimitGate, UsageGate


@dataclass(frozen=True, slots=True)
class ChatbotPolicy:
    """Ai được chuyển tin cho chatbot: cờ bật và danh sách người dùng thử (kế hoạch 5.1, KT17).

    Tắt thì hành vi của bot y hệt trước khi có chatbot. `pilot_emails=None` nghĩa là mọi người
    đã liên kết; có giá trị thì CHỈ những email này (so không phân biệt hoa thường), và tập rỗng
    nghĩa là không ai (đóng khi cấu hình có nhưng chỉ toàn dấu phẩy).
    """

    enabled: bool = False
    pilot_emails: frozenset[str] | None = None
    # Số tin đang chờ xử lý tối đa của một chat; vượt thì tin mới bị từ chối, không vào hộp thư.
    max_pending_per_chat: int = 5
    # Cổng hạn mức mỗi ngày (S10), phục vụ lệnh `/limit`; `None` thì lệnh đó là lệnh lạ. Việc chặn
    # thật nằm ở worker, nên đây chỉ để người dùng xem số liệu.
    usage_gate: UsageGate | None = None

    def allows(self, email: str | None) -> bool:
        if not self.enabled:
            return False
        if self.pilot_emails is None:
            return True
        return email is not None and email.strip().lower() in self.pilot_emails

    @classmethod
    def from_settings(cls, settings: Any) -> ChatbotPolicy:
        raw = settings.chatbot_pilot_user_emails
        # Rỗng (hoặc chỉ khoảng trắng) là không giới hạn; có giá trị mà không có email nào thì đóng.
        emails: frozenset[str] | None = (
            frozenset(item.strip().lower() for item in raw.split(",") if item.strip())
            if raw.strip()
            else None
        )
        # Chatbot đi qua Telegram nên cần cả cờ Telegram.
        return cls(
            enabled=bool(settings.chatbot_enabled and settings.telegram_enabled),
            pilot_emails=emails,
            max_pending_per_chat=settings.bot_max_pending_per_chat,
            usage_gate=TurnLimitGate.from_settings(settings),
        )
