from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    PriceAlertEvent,
    PriceAlertMaterialThreshold,
    PriceAlertSetting,
    Quote,
    QuoteLine,
    QuoteVersion,
)
from app.services.daily_min_series import get_daily_min_series

ATTACH_PERCENT = Decimal("2.5")  # lệch dưới mức này so với điểm đang pending thì gắn vào thẻ đó
# Điểm bị gắn cờ bị loại khỏi tính toán khi chưa duyệt hoặc đã bị đánh dấu nhập sai (D12).
EXCLUDING_STATUSES = ("pending", "rejected")
_CENT = Decimal("0.01")
_MAX_REFERENCE_SHOWN = 3


@dataclass(frozen=True, slots=True)
class LinePrice:
    line_id: UUID
    price: Decimal


@dataclass(frozen=True, slots=True)
class AnomalyFinding:
    percent: Decimal
    median: Decimal
    reference_prices: list[Decimal]
    reference_point_count: int
    direction: str


def median(values: Sequence[Decimal]) -> Decimal:
    """Trung vị; số điểm chẵn là trung bình hai điểm giữa (D12)."""
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def evaluate_line(
    price: Decimal,
    reference_prices: Sequence[Decimal],
    threshold_percent: Decimal,
) -> AnomalyFinding | None:
    """Hàm thuần: dòng lệch từ ngưỡng trở lên so với trung vị các giá hợp lệ trước đó thì bị cờ.

    Chuỗi chưa có điểm hợp lệ nào (điểm đầu tiên) không bị gắn cờ được.
    """
    usable = [p for p in reference_prices if p > 0]
    if not usable:
        return None
    center = median(usable)
    percent = (price - center) / center * 100
    if abs(percent) < threshold_percent:
        return None
    return AnomalyFinding(
        percent=percent,
        median=center,
        reference_prices=list(usable[-_MAX_REFERENCE_SHOWN:]),
        reference_point_count=len(usable),
        direction="up" if percent > 0 else "down",
    )


async def excluded_line_ids(
    session: AsyncSession,
    material_id: UUID,
    delivery_month: date,
) -> set[UUID]:
    """Dòng bị gắn cờ chưa được xác nhận đúng của chuỗi: loại khỏi daily-min và điểm tham chiếu."""
    flagged = (
        await session.execute(
            select(PriceAlertEvent.quote_line_id, PriceAlertEvent.price_new, Quote.id)
            .join(QuoteVersion, QuoteVersion.id == PriceAlertEvent.quote_version_id)
            .join(Quote, Quote.id == QuoteVersion.quote_id)
            .where(
                PriceAlertEvent.kind == "anomaly",
                PriceAlertEvent.material_id == material_id,
                PriceAlertEvent.delivery_month == delivery_month.replace(day=1),
                PriceAlertEvent.review_status.in_(EXCLUDING_STATUSES),
                PriceAlertEvent.quote_line_id.is_not(None),
                Quote.cancelled_at.is_(None),
            ),
        )
    ).all()
    excluded = {line_id for line_id, _, _ in flagged if line_id is not None}
    # Phiếu được sửa và chốt lại sẽ sao chép dòng sang version mới (id khác): bản sao giữ nguyên
    # giá nhập sai vẫn phải bị loại, nếu không điểm sai quay lại đường giá.
    for _, price, quote_id in flagged:
        copies = (
            await session.execute(
                select(QuoteLine.id)
                .join(QuoteVersion, QuoteVersion.id == QuoteLine.quote_version_id)
                .where(
                    QuoteVersion.quote_id == quote_id,
                    QuoteLine.material_id == material_id,
                    func.date_trunc("month", QuoteLine.delivery_month)
                    == delivery_month.replace(day=1),
                    QuoteLine.price_converted_vnd_per_kg == price,
                ),
            )
        ).scalars()
        excluded.update(copies)
    return excluded


async def load_anomaly_percent(
    session: AsyncSession,
    material_id: UUID,
    settings: PriceAlertSetting,
) -> Decimal:
    override = (
        await session.execute(
            select(PriceAlertMaterialThreshold.anomaly_percent).where(
                PriceAlertMaterialThreshold.material_id == material_id,
            ),
        )
    ).scalar_one_or_none()
    return override if override is not None else settings.anomaly_percent


async def detect_line(
    session: AsyncSession,
    *,
    version_id: UUID,
    received_date: date,
    material_id: UUID,
    delivery_month: date,
    line: LinePrice,
    settings: PriceAlertSetting,
    now: datetime,
    scan_run_id: UUID | None,
) -> bool:
    """Gắn cờ một dòng nếu nghi nhập sai; trả `True` nếu đã tạo sự kiện bất thường."""
    month = delivery_month.replace(day=1)
    excluded = await excluded_line_ids(session, material_id, month)
    excluded.add(line.line_id)
    points = await get_daily_min_series(
        session,
        material_id=material_id,
        delivery_month=month,
        start=received_date - timedelta(days=settings.anomaly_lookback_days),
        end=received_date - timedelta(days=1),
        exclude_line_ids=excluded,
    )
    threshold = await load_anomaly_percent(session, material_id, settings)
    finding = evaluate_line(line.price, [p.price for p in points], threshold)
    if finding is None:
        return False

    pending = await _matching_pending_card(session, material_id, month, line.price)
    session.add(
        PriceAlertEvent(
            scan_run_id=scan_run_id,
            quote_version_id=version_id,
            material_id=material_id,
            delivery_month=month,
            kind="anomaly",
            quote_line_id=line.line_id,
            direction=finding.direction,
            percent_change=finding.percent.quantize(_CENT, rounding=ROUND_HALF_UP),
            price_new=line.price,
            price_ref=finding.median,
            received_date_new=received_date,
            reference_point_count=finding.reference_point_count,
            reference_prices=finding.reference_prices,
            review_status="pending",
            attached_to_event_id=pending,
            created_at=now,
        ),
    )
    await session.flush()
    return True


async def _matching_pending_card(
    session: AsyncSession,
    material_id: UUID,
    month: date,
    price: Decimal,
) -> UUID | None:
    """Điểm cùng mặt bằng (lệch dưới 2,5%) với một thẻ đang pending thì gắn vào thẻ đó (D12)."""
    rows = (
        await session.execute(
            select(PriceAlertEvent.id, PriceAlertEvent.price_new)
            .join(QuoteVersion, QuoteVersion.id == PriceAlertEvent.quote_version_id)
            .join(Quote, Quote.id == QuoteVersion.quote_id)
            .where(
                PriceAlertEvent.kind == "anomaly",
                PriceAlertEvent.material_id == material_id,
                PriceAlertEvent.delivery_month == month,
                PriceAlertEvent.review_status == "pending",
                PriceAlertEvent.attached_to_event_id.is_(None),
                Quote.cancelled_at.is_(None),
            )
            .order_by(PriceAlertEvent.sequence_number),
        )
    ).all()
    for event_id, pending_price in rows:
        if pending_price > 0 and abs(price - pending_price) / pending_price * 100 < ATTACH_PERCENT:
            return UUID(str(event_id))
    return None
