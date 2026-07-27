from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.material import Material


class MaterialType(Base):
    __tablename__ = "material_types"
    __table_args__ = (
        CheckConstraint("status in ('active', 'inactive')", name="ck_material_types_status"),
        CheckConstraint("code = upper(btrim(code))", name="ck_material_types_code_normalized"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(150), index=True)
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    materials: Mapped[list[Material]] = relationship(
        back_populates="material_type",
        cascade="save-update, merge",
    )
