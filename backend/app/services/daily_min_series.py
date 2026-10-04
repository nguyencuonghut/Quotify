from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Quote, QuoteLine, QuoteVersion


@dataclass(frozen=True, slots=True)
class DailyMinPoint:
    received_date: date
    price: Decimal
    line_id: UUID
    version_id: UUID


async def get_daily_min_series(
    session: AsyncSession,
    *,
    material_id: UUID,
    delivery_month: date,
    start: date,
    end: date,
    exclude_line_ids: Collection[UUID] = (),
) -> list[DailyMinPoint]:
    """Giá quy đổi thấp nhất mỗi ngày nhận (`received_date`) của một chuỗi, theo thứ tự ngày.

    Chuỗi là (vật tư, tháng của `delivery_month`). Điều kiện giống dashboard: version `confirmed`,
    phiếu chưa hủy. Dòng trong `exclude_line_ids` bị bỏ trước khi lấy giá thấp nhất, nên điểm của
    ngày được tính lại và ngày hết dòng thì không còn điểm.
    """
    month = func.date_trunc("month", QuoteLine.delivery_month)
    statement = (
        select(
            QuoteVersion.received_date,
            QuoteLine.price_converted_vnd_per_kg,
            QuoteLine.id,
            QuoteVersion.id,
        )
        .join(QuoteVersion, QuoteVersion.id == QuoteLine.quote_version_id)
        .join(Quote, Quote.id == QuoteVersion.quote_id)
        .where(
            QuoteLine.material_id == material_id,
            month == func.date_trunc("month", delivery_month),
            QuoteVersion.status == "confirmed",
            QuoteVersion.confirmed_at.is_not(None),
            Quote.cancelled_at.is_(None),
            QuoteVersion.received_date >= start,
            QuoteVersion.received_date <= end,
        )
        .distinct(QuoteVersion.received_date)
        .order_by(
            QuoteVersion.received_date,
            QuoteLine.price_converted_vnd_per_kg,
            QuoteVersion.confirmed_at,
            QuoteLine.id,
        )
    )
    if exclude_line_ids:
        statement = statement.where(QuoteLine.id.not_in(list(exclude_line_ids)))

    rows = (await session.execute(statement)).all()
    return [
        DailyMinPoint(received_date=row[0], price=row[1], line_id=row[2], version_id=row[3])
        for row in rows
    ]
