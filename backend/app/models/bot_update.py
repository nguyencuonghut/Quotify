from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

BOT_UPDATE_OPEN_STATUSES = ("queued", "processing")
_OPEN_WHERE = text("status IN ('queued','processing')")


class BotUpdate(Base):
    """Hộp thư của chatbot: một dòng cho mỗi tin nhắn Telegram cần chatbot trả lời.

    Postgres là nguồn sự thật về trạng thái; hàng đợi arq chỉ để đánh thức worker (kế hoạch 5.1,
    KT2 và KT3). Nội dung tin và câu trả lời chỉ lưu tạm và bị xóa khi dòng kết thúc.
    """

    __tablename__ = "bot_updates"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','processing','replied','failed','dropped')",
            name="ck_bot_updates_status",
        ),
        CheckConstraint("kind IN ('text')", name="ck_bot_updates_kind"),
        # Claim theo chat chỉ nhìn các dòng còn mở.
        Index("ix_bot_updates_chat_open", "chat_id", "update_id", postgresql_where=_OPEN_WHERE),
        Index("ix_bot_updates_status_received", "status", "received_at"),
        # Đếm hạn mức theo người dùng mỗi ngày (S10).
        Index("ix_bot_updates_user_received", "user_id", "received_at"),
    )

    # `update_id` do Telegram cấp, cùng giá trị với `telegram_processed_updates.update_id`.
    update_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(12), nullable=False, server_default="text")
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="queued")
    # Nội dung chỉ lưu tạm: xóa khi dòng vào trạng thái kết thúc (giảm dữ liệu cá nhân lưu lại).
    payload_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    reply_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_parts: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    # Tăng mỗi lần claim; cũng là "mã rào chắn" của lần claim đó.
    attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Danh mục cố định, không lưu nguyên văn ngoại lệ.
    error_category: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # Đặt khi lưu câu trả lời của engine: cơ sở đếm lượt đã tiêu tốn engine (hạn mức, S10).
    reply_saved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
