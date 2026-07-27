from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.supplier_contact import SupplierContact
    from app.models.supplier_material import SupplierMaterial


class Supplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = (
        CheckConstraint(
            "supplier_type in ('domestic', 'international')",
            name="ck_suppliers_supplier_type",
        ),
        CheckConstraint("status in ('active', 'inactive')", name="ck_suppliers_status"),
        CheckConstraint("code = upper(btrim(code))", name="ck_suppliers_code_normalized"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    supplier_type: Mapped[str] = mapped_column(String(30), index=True)
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active")
    tax_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    contacts: Mapped[list[SupplierContact]] = relationship(
        back_populates="supplier",
        cascade="all, delete-orphan",
    )
    supplier_materials: Mapped[list[SupplierMaterial]] = relationship(
        back_populates="supplier",
        cascade="all, delete-orphan",
    )
