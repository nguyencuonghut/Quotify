from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.supplier import Supplier
    from app.models.user import User
    from app.models.quote_version import QuoteVersion


class Quote(Base):
    __tablename__ = "quotes"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    # PK là UUID (không sắp thứ tự được), và `created_at` có thể trùng nhau
    # hàng loạt khi import theo lô cùng 1 transaction (`func.now()` trả về
    # thời điểm bắt đầu transaction, không đổi trong suốt transaction đó) —
    # cột tự tăng này là tie-breaker DUY NHẤT phản ánh đúng thứ tự tạo, kể cả
    # khi nhiều Quote được tạo trong cùng 1 transaction. Dùng để giữ nguyên
    # nhóm các dòng theo NCC/thứ tự nhập liệu khi sort theo cột khác bị trùng
    # giá trị (vd. sort theo "Ngày nhận" — xem `QuoteQueryService`).
    sequence_number: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=False),
        nullable=False,
        unique=True,
    )
    supplier_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_by_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
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

    supplier: Mapped[Supplier] = relationship()
    created_by: Mapped[User | None] = relationship()
    versions: Mapped[list[QuoteVersion]] = relationship(
        back_populates="quote",
        cascade="all, delete-orphan",
        order_by="QuoteVersion.version_number.asc()",
    )
