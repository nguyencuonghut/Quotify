from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    PriceAlertScannedVersion,
    Quote,
    QuoteLine,
    QuoteVersion,
)
from app.services.working_days import working_days_between

BUSINESS_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
SCAN_OVERLAP = timedelta(minutes=5)


@dataclass(frozen=True, slots=True)
class VersionToScan:
    version_id: UUID
    quote_id: UUID
    received_date: date
    confirmed_at: datetime
    quote_created_by_id: UUID | None


@dataclass(frozen=True, slots=True)
class LineRef:
    line_id: UUID
    material_id: UUID
    delivery_month: date
    price: Decimal


def trigger_delay_working_days(received_date: date, confirmed_at: datetime) -> int:
    """Số ngày làm việc từ ngày nhận đến ngày chốt tính theo giờ VN (D6). Chốt cùng ngày là 0."""
    return working_days_between(received_date, confirmed_at.astimezone(BUSINESS_TIMEZONE).date())


def is_trigger_source(
    *,
    quote_created_by_id: UUID | None,
    seed_user_id: UUID | None,
    received_date: date,
    confirmed_at: datetime,
    max_delay_working_days: int,
) -> bool:
    """D6: không do tài khoản seed (import) tạo và trễ không quá N ngày làm việc.

    NULL-safe: người tạo NULL không bị coi là tài khoản seed. Phiếu đã hủy được loại từ lúc chọn
    version cần quét, không xét lại ở đây.
    """
    if seed_user_id is not None and quote_created_by_id == seed_user_id:
        return False
    return trigger_delay_working_days(received_date, confirmed_at) <= max_delay_working_days


async def select_versions_to_scan(
    session: AsyncSession,
    *,
    watermark: datetime,
    limit: int | None = None,
) -> list[VersionToScan]:
    """L3: version đã chốt, phiếu chưa hủy, chưa quét, `confirmed_at` sau watermark trừ 5 phút."""
    statement = (
        select(
            QuoteVersion.id,
            QuoteVersion.quote_id,
            QuoteVersion.received_date,
            QuoteVersion.confirmed_at,
            Quote.created_by_id,
        )
        .join(Quote, Quote.id == QuoteVersion.quote_id)
        .outerjoin(
            PriceAlertScannedVersion,
            PriceAlertScannedVersion.version_id == QuoteVersion.id,
        )
        .where(
            QuoteVersion.status == "confirmed",
            QuoteVersion.confirmed_at.is_not(None),
            QuoteVersion.confirmed_at > watermark - SCAN_OVERLAP,
            Quote.cancelled_at.is_(None),
            PriceAlertScannedVersion.version_id.is_(None),
        )
        .order_by(QuoteVersion.confirmed_at, QuoteVersion.id)
    )
    if limit is not None:
        statement = statement.limit(limit)
    rows = (await session.execute(statement)).all()
    return [
        VersionToScan(
            version_id=row[0],
            quote_id=row[1],
            received_date=row[2],
            confirmed_at=row[3],
            quote_created_by_id=row[4],
        )
        for row in rows
    ]


def select_candidate_lines(
    new_lines: Sequence[LineRef],
    source_lines: Sequence[LineRef] | None,
    *,
    new_received_date: date,
    source_received_date: date | None,
    source_was_scanned: bool,
) -> list[LineRef]:
    """L1: dòng của bản mới tham gia đánh giá.

    Mọi dòng là ứng viên khi không có bản nguồn, bản nguồn chưa quét, hoặc `received_date` đổi.
    Ngược lại so tập đa giá theo chuỗi (vật tư, tháng giao hàng): dòng của bản mới có giá không
    còn trong tập đa của bản nguồn là ứng viên. Dòng bị bỏ không tạo ứng viên.
    """
    if source_lines is None or not source_was_scanned or source_received_date != new_received_date:
        return list(new_lines)

    remaining: dict[tuple[UUID, date], Counter[Decimal]] = {}
    for line in source_lines:
        remaining.setdefault(_chain(line), Counter())[line.price] += 1

    candidates: list[LineRef] = []
    for line in new_lines:
        prices = remaining.get(_chain(line))
        if prices is not None and prices[line.price] > 0:
            prices[line.price] -= 1
            continue
        candidates.append(line)
    return candidates


def _chain(line: LineRef) -> tuple[UUID, date]:
    return line.material_id, line.delivery_month.replace(day=1)


async def load_version_lines(session: AsyncSession, version_id: UUID) -> list[LineRef]:
    rows = (
        await session.execute(
            select(
                QuoteLine.id,
                QuoteLine.material_id,
                QuoteLine.delivery_month,
                QuoteLine.price_converted_vnd_per_kg,
            )
            .where(QuoteLine.quote_version_id == version_id)
            .order_by(QuoteLine.line_order, QuoteLine.id),
        )
    ).all()
    return [LineRef(*row) for row in rows]


async def resolve_candidate_lines(session: AsyncSession, version: VersionToScan) -> list[LineRef]:
    """Dòng ứng viên của một version (L1). Một version mới có thể thay thế nhiều version cũ."""
    new_lines = await load_version_lines(session, version.version_id)
    sources = (
        await session.execute(
            select(QuoteVersion.id, QuoteVersion.received_date)
            .where(QuoteVersion.superseded_by_version_id == version.version_id)
            .order_by(QuoteVersion.version_number, QuoteVersion.id),
        )
    ).all()
    if not sources:
        return select_candidate_lines(
            new_lines,
            None,
            new_received_date=version.received_date,
            source_received_date=None,
            source_was_scanned=False,
        )

    source_ids = [row[0] for row in sources]
    scanned_count = (
        await session.execute(
            select(func.count()).where(PriceAlertScannedVersion.version_id.in_(source_ids)),
        )
    ).scalar_one()
    source_lines: list[LineRef] = []
    for source_id in source_ids:
        source_lines.extend(await load_version_lines(session, source_id))
    # Nhiều nguồn: cùng ngày khi mọi nguồn cùng ngày với bản mới, đã quét khi mọi nguồn đã quét.
    same_date = all(row[1] == version.received_date for row in sources)
    return select_candidate_lines(
        new_lines,
        source_lines,
        new_received_date=version.received_date,
        source_received_date=version.received_date if same_date else None,
        source_was_scanned=scanned_count == len(source_ids),
    )


async def record_scanned_version(
    session: AsyncSession,
    *,
    version_id: UUID,
    is_trigger_source: bool,
    trigger_delay_working_days: int | None,
    scan_run_id: UUID | None = None,
) -> None:
    """L2: ghi version đã quét; chạy lại không lỗi và không ghi đè."""
    await session.execute(
        pg_insert(PriceAlertScannedVersion)
        .values(
            version_id=version_id,
            is_trigger_source=is_trigger_source,
            trigger_delay_working_days=trigger_delay_working_days,
            scan_run_id=scan_run_id,
        )
        .on_conflict_do_nothing(index_elements=["version_id"]),
    )
