from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

TELEGRAM_ACCOUNT_HOLDING_STATUSES = ("active", "blocked")
_HOLDING_WHERE = text("status IN ('active','blocked')")


class TelegramAccount(Base):
    """Liên kết giữa một người dùng Quotify và một tài khoản Telegram.

    Một người dùng chỉ giữ tối đa một liên kết "đang giữ" (`active` hoặc `blocked`) và một tài
    khoản Telegram chỉ gắn với tối đa một người dùng. Hai ràng buộc này do partial unique index
    đảm bảo, nên đua nhau liên kết cũng không tạo được hai bản ghi.
    """

    __tablename__ = "telegram_accounts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active','revoked','blocked')",
            name="ck_telegram_accounts_status",
        ),
        CheckConstraint(
            "revoked_reason IS NULL OR revoked_reason IN "
            "('replaced','user_unlink','stop_command','owner_inactive')",
            name="ck_telegram_accounts_revoked_reason",
        ),
        Index(
            "uq_telegram_accounts_holding_telegram_user",
            "telegram_user_id",
            unique=True,
            postgresql_where=_HOLDING_WHERE,
        ),
        Index(
            "uq_telegram_accounts_holding_user",
            "user_id",
            unique=True,
            postgresql_where=_HOLDING_WHERE,
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # Lưu không có '@'; giao diện tự thêm.
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
