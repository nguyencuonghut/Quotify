from __future__ import annotations

from datetime import datetime, time
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Integer, String, Time, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BackupSchedule(Base):
    __tablename__ = "backup_schedules"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    frequency: Mapped[str] = mapped_column(String(50), nullable=False)  # daily / weekly / one_off
    day_of_week: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # 0-6 for weekly (0=Monday, 6=Sunday)
    time_of_day: Mapped[time] = mapped_column(Time, nullable=False)  # HH:MM:SS
    one_off_datetime: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
