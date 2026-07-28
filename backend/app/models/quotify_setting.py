from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class QuotifySetting(Base):
    __tablename__ = "quotify_settings"
    __table_args__ = (
        CheckConstraint(
            "singleton_key = 'default'",
            name="ck_quotify_settings_singleton_key",
        ),
        CheckConstraint(
            "conversion_cost_vnd_per_kg >= 0",
            name="ck_quotify_settings_conversion_cost_non_negative",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    singleton_key: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        default="default",
        server_default="default",
    )
    conversion_cost_vnd_per_kg: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("200.00"),
        server_default="200.00",
    )
    updated_by_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    updated_by: Mapped[User | None] = relationship()
