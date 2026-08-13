from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.material import Material
    from app.models.quote_version import QuoteVersion
    from app.models.user import User


class QuoteLine(Base):
    __tablename__ = "quote_lines"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    quote_version_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("quote_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    material_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("materials.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    price_original: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    unit: Mapped[str] = mapped_column(String(10), nullable=False)
    delivery_month: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    line_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    
    # Provenance fields for USD/MT (quy đổi giá); cũng cho phép lưu tỷ giá tham
    # khảo (không dùng để quy đổi) trên dòng VND/KG, xem QuotePricingService.
    exchange_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    exchange_rate_source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    exchange_rate_source_mode: Mapped[str | None] = mapped_column(String(30), nullable=True)  # 'auto' | 'manual_past' | 'manual_fallback' | 'manual_reference'
    exchange_rate_entered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exchange_rate_manual_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    exchange_rate_actor_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Conversion cost/tax at freeze time
    import_tax_rate_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    processing_cost_vnd_per_kg: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    
    # Final calculated price
    price_converted_vnd_per_kg: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    
    # Free-text note for this line (e.g. from historical backfill import)
    note: Mapped[str | None] = mapped_column(Text(), nullable=True)

    # Purchase decision fields
    purchase_marked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    purchase_marked_by_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
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

    version: Mapped[QuoteVersion] = relationship(back_populates="lines")
    material: Mapped[Material] = relationship()
    exchange_rate_actor: Mapped[User | None] = relationship(foreign_keys=[exchange_rate_actor_id])
    purchase_marked_by: Mapped[User | None] = relationship(foreign_keys=[purchase_marked_by_id])
