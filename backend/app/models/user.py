from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Table, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.audit_log import AuditLog
    from app.models.refresh_token import RefreshToken
    from app.models.role import Role


class UserStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    LOCKED = "locked"


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    status: Mapped[UserStatus] = mapped_column(
        Enum(
            UserStatus,
            name="user_status_enum",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=UserStatus.ACTIVE,
    )
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    roles: Mapped[list[Role]] = relationship(
        secondary="user_roles",
        back_populates="users",
    )
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        back_populates="user",
    )
    audit_logs: Mapped[list[AuditLog]] = relationship(
        back_populates="actor_user",
    )


user_roles = Table(
    "user_roles",
    Base.metadata,
    Column(
        "user_id",
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "role_id",
        PGUUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)
