from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TelegramProcessedUpdate(Base):
    """Các `update_id` Telegram đã xử lý, để chống xử lý trùng khi Telegram gửi lại."""

    __tablename__ = "telegram_processed_updates"

    # `update_id` do Telegram cấp, không tự tăng ở phía mình.
    update_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
