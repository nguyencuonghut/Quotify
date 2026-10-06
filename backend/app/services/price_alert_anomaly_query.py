from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import Material, PriceAlertEvent, Quote, QuoteVersion, User
from app.services.price_alert_candidates import BUSINESS_TIMEZONE
from app.services.working_days import working_days_between

HISTORY_DAYS = 30
Status = Literal["pending", "resolved", "all"]
_RESOLVED = ("accepted", "rejected", "expired")


@dataclass(frozen=True, slots=True)
class AnomalyRow:
    id: UUID
    material_id: UUID
    material_name: str
    delivery_month: date
    received_date: date
    price_new: Decimal
    median: Decimal
    percent_change: Decimal
    reference_prices: list[Decimal]
    reference_point_count: int | None
    quote_id: UUID
    entered_by_name: str | None
    review_status: str
    attached_count: int
    age_working_days: int
    created_at: datetime
    reviewed_by_name: str | None
    reviewed_at: datetime | None


async def list_anomalies(
    session: AsyncSession,
    *,
    status: Status,
    material_id: UUID | None,
    limit: int,
    offset: int,
    now: datetime,
) -> tuple[list[AnomalyRow], int]:
    """Điểm bất thường gốc (không gồm điểm gắn kèm) để duyệt trên web (M6).

    `pending`: đang chờ và phiếu chưa hủy, cũ nhất trước. `resolved`: đã duyệt hoặc hết hạn trong
    30 ngày gần đây, mới nhất trước. `all`: cả hai.
    """
    entered_by = aliased(User)
    reviewer = aliased(User)
    attached = aliased(PriceAlertEvent)
    attached_count = (
        select(func.count())
        .where(attached.attached_to_event_id == PriceAlertEvent.id)
        .correlate(PriceAlertEvent)
        .scalar_subquery()
    )
    pending_clause = (PriceAlertEvent.review_status == "pending") & Quote.cancelled_at.is_(None)
    resolved_clause = PriceAlertEvent.review_status.in_(_RESOLVED) & (
        func.coalesce(PriceAlertEvent.reviewed_at, PriceAlertEvent.created_at)
        >= now - timedelta(days=HISTORY_DAYS)
    )
    clause = {
        "pending": pending_clause,
        "resolved": resolved_clause,
        "all": or_(pending_clause, resolved_clause),
    }[status]
    base = (
        select(PriceAlertEvent)
        .join(QuoteVersion, QuoteVersion.id == PriceAlertEvent.quote_version_id)
        .join(Quote, Quote.id == QuoteVersion.quote_id)
        .where(
            PriceAlertEvent.kind == "anomaly",
            PriceAlertEvent.attached_to_event_id.is_(None),
            clause,
        )
    )
    if material_id is not None:
        base = base.where(PriceAlertEvent.material_id == material_id)
    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()

    resolved_at = func.coalesce(PriceAlertEvent.reviewed_at, PriceAlertEvent.created_at)
    is_pending = PriceAlertEvent.review_status == "pending"
    # Chờ duyệt trước (cũ nhất trước), rồi đã xử lý (mới nhất trước).
    order = (
        [PriceAlertEvent.created_at.asc()]
        if status == "pending"
        else [resolved_at.desc()]
        if status == "resolved"
        else [
            case((is_pending, 0), else_=1),
            case((is_pending, PriceAlertEvent.created_at)).asc().nulls_last(),
            resolved_at.desc(),
        ]
    )
    rows = (
        await session.execute(
            select(
                PriceAlertEvent,
                Material.name,
                QuoteVersion.quote_id,
                entered_by.full_name,
                reviewer.full_name,
                attached_count,
            )
            .join(QuoteVersion, QuoteVersion.id == PriceAlertEvent.quote_version_id)
            .join(Quote, Quote.id == QuoteVersion.quote_id)
            .join(Material, Material.id == PriceAlertEvent.material_id)
            .outerjoin(entered_by, entered_by.id == QuoteVersion.created_by_id)
            .outerjoin(reviewer, reviewer.id == PriceAlertEvent.reviewed_by_id)
            .where(
                PriceAlertEvent.kind == "anomaly",
                PriceAlertEvent.attached_to_event_id.is_(None),
                clause,
                *([PriceAlertEvent.material_id == material_id] if material_id else []),
            )
            .order_by(*order, PriceAlertEvent.sequence_number)
            .limit(limit)
            .offset(offset)
        )
    ).all()
    today = now.astimezone(BUSINESS_TIMEZONE).date()
    items = [
        AnomalyRow(
            id=event.id,
            material_id=event.material_id,
            material_name=name,
            delivery_month=event.delivery_month,
            received_date=event.received_date_new,
            price_new=event.price_new,
            median=event.price_ref,
            percent_change=event.percent_change,
            reference_prices=list(event.reference_prices or []),
            reference_point_count=event.reference_point_count,
            quote_id=quote_id,
            entered_by_name=entered_name,
            review_status=event.review_status or "pending",
            attached_count=count,
            age_working_days=working_days_between(
                event.created_at.astimezone(BUSINESS_TIMEZONE).date(), today
            ),
            created_at=event.created_at,
            reviewed_by_name=reviewer_name,
            reviewed_at=event.reviewed_at,
        )
        for event, name, quote_id, entered_name, reviewer_name, count in rows
    ]
    return items, int(total)


@dataclass(frozen=True, slots=True)
class QuoteLineKey:
    """Một dòng của phiếu để tra trạng thái giá bất thường."""

    line_id: UUID
    quote_id: UUID
    material_id: UUID
    delivery_month: date
    price: Decimal


def _month(value: date) -> date:
    return value.replace(day=1)


async def anomaly_status_by_line(
    session: AsyncSession,
    lines: Sequence[QuoteLineKey],
) -> dict[UUID, str]:
    """Trạng thái duyệt giá bất thường của từng dòng (M11); dòng chưa bị gắn cờ không có mặt.

    Mỗi dòng có tối đa một sự kiện (chỉ mục duy nhất theo version và dòng). Phiếu được sửa và
    chốt lại sao chép dòng sang version mới (id khác); bản sao giữ nguyên giá nên mang trạng
    thái của dòng gốc, cùng cách `excluded_line_ids` nhận ra bản sao (phiếu, vật tư, tháng, giá).
    """
    if not lines:
        return {}
    rows = (
        await session.execute(
            select(
                PriceAlertEvent.quote_line_id,
                QuoteVersion.quote_id,
                PriceAlertEvent.material_id,
                PriceAlertEvent.delivery_month,
                PriceAlertEvent.price_new,
                PriceAlertEvent.review_status,
            )
            .join(QuoteVersion, QuoteVersion.id == PriceAlertEvent.quote_version_id)
            .where(
                PriceAlertEvent.kind == "anomaly",
                PriceAlertEvent.review_status.is_not(None),
                QuoteVersion.quote_id.in_({line.quote_id for line in lines}),
            )
            .order_by(PriceAlertEvent.sequence_number)
        )
    ).all()
    direct: dict[UUID, str] = {}
    by_copy: dict[tuple[UUID, UUID, date, Decimal], str] = {}
    for line_id, quote_id, material_id, month, price, status in rows:
        if not status:
            continue
        if line_id is not None:
            direct[line_id] = status
        by_copy[(quote_id, material_id, _month(month), price)] = status
    result: dict[UUID, str] = {}
    for line in lines:
        status = direct.get(line.line_id) or by_copy.get(
            (line.quote_id, line.material_id, _month(line.delivery_month), line.price)
        )
        if status:
            result[line.line_id] = status
    return result
