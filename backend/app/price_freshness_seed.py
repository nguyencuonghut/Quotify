"""Nạp danh sách theo dõi độ mới của giá mặc định từ dữ liệu thật (Telegram 1D, Slice 4).

Với mỗi vật tư đang hoạt động, lấy các NGÀY nhận giá khác nhau (phiếu hợp lệ: đã chốt, chưa hủy)
trong cửa sổ gần nhất; vật tư có từ `--min-days` ngày trở lên được đề xuất theo dõi, chu kỳ kỳ vọng
theo khoảng cách trung bình giữa hai ngày liên tiếp (<= 5 ngày: 7; <= 12 ngày: 14; còn lại: 30).

    python -m app.price_freshness_seed                       # dry-run: chỉ in đề xuất
    python -m app.price_freshness_seed --csv de-xuat.csv     # dry-run và xuất CSV để duyệt
    python -m app.price_freshness_seed --apply               # nạp

`--apply` chỉ chèn vật tư CHƯA có cấu hình (kể cả hàng đã tắt theo dõi): không bao giờ ghi đè hay
bật lại lựa chọn của quản lý. Hàng được nạp có `updated_by_id` rỗng để phân biệt với hàng người sửa.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import TextIO
from uuid import UUID

from sqlalchemy import distinct, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import get_sessionmaker
from app.models import (
    Material,
    MaterialType,
    PriceFreshnessMaterial,
    Quote,
    QuoteLine,
    QuoteVersion,
)
from app.services.quotify_dashboard_service import BUSINESS_TIMEZONE

DEFAULT_MIN_DAYS = 3
DEFAULT_WINDOW_DAYS = 90
_TIERS: tuple[tuple[Decimal, int], ...] = ((Decimal("5"), 7), (Decimal("12"), 14))
_LONGEST_INTERVAL_DAYS = 30


@dataclass(frozen=True, slots=True)
class Suggestion:
    material_id: UUID
    material_code: str
    material_name: str
    material_type_name: str
    update_days: int
    mean_gap_days: Decimal
    last_received_date: date
    interval_days: int


def suggest_interval(mean_gap_days: Decimal) -> int:
    """Chu kỳ kỳ vọng (ngày) theo khoảng cách trung bình giữa hai ngày cập nhật."""
    for upper_bound, interval in _TIERS:
        if mean_gap_days <= upper_bound:
            return interval
    return _LONGEST_INTERVAL_DAYS


async def compute_suggestions(
    session: AsyncSession,
    *,
    today: date,
    min_days: int = DEFAULT_MIN_DAYS,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> list[Suggestion]:
    window_start = today - timedelta(days=window_days - 1)
    days = (
        select(
            QuoteLine.material_id.label("material_id"),
            func.count(distinct(QuoteVersion.received_date)).label("update_days"),
            func.min(QuoteVersion.received_date).label("first_day"),
            func.max(QuoteVersion.received_date).label("last_day"),
        )
        .select_from(QuoteLine)
        .join(QuoteVersion, QuoteLine.quote_version_id == QuoteVersion.id)
        .join(Quote, QuoteVersion.quote_id == Quote.id)
        .where(
            QuoteVersion.status == "confirmed",
            QuoteVersion.confirmed_at.is_not(None),
            Quote.cancelled_at.is_(None),
            QuoteVersion.received_date >= window_start,
            QuoteVersion.received_date <= today,
        )
        .group_by(QuoteLine.material_id)
        .having(func.count(distinct(QuoteVersion.received_date)) >= max(min_days, 2))
        .subquery()
    )
    rows = await session.execute(
        select(
            Material.id,
            Material.code,
            Material.name,
            MaterialType.name.label("type_name"),
            days.c.update_days,
            days.c.first_day,
            days.c.last_day,
        )
        .join(days, days.c.material_id == Material.id)
        .join(MaterialType, Material.material_type_id == MaterialType.id)
        .where(Material.status == "active")
        .order_by(Material.name.asc(), Material.code.asc()),
    )
    suggestions: list[Suggestion] = []
    for row in rows:
        mean_gap = Decimal((row.last_day - row.first_day).days) / Decimal(row.update_days - 1)
        suggestions.append(
            Suggestion(
                material_id=row.id,
                material_code=row.code,
                material_name=row.name,
                material_type_name=row.type_name,
                update_days=int(row.update_days),
                mean_gap_days=mean_gap.quantize(Decimal("0.01")),
                last_received_date=row.last_day,
                interval_days=suggest_interval(mean_gap),
            ),
        )
    return suggestions


async def apply_suggestions(session: AsyncSession, suggestions: list[Suggestion]) -> int:
    """Chèn các vật tư chưa có cấu hình; trả về số hàng thật sự được thêm."""
    inserted = 0
    for item in suggestions:
        result = await session.execute(
            pg_insert(PriceFreshnessMaterial)
            .values(
                material_id=item.material_id,
                is_watched=True,
                expected_interval_days=item.interval_days,
                updated_by_id=None,
            )
            .on_conflict_do_nothing(index_elements=[PriceFreshnessMaterial.material_id])
            .returning(PriceFreshnessMaterial.material_id),
        )
        if result.scalar_one_or_none() is not None:
            inserted += 1
    return inserted


_CSV_FIELDS = (
    "material_code",
    "material_name",
    "material_type_name",
    "update_days",
    "mean_gap_days",
    "last_received_date",
    "interval_days",
)


def _csv_text(value: str) -> str:
    """Ô văn bản bắt đầu bằng ký tự công thức bị Excel hiểu là công thức: thêm dấu nháy đơn."""
    return f"'{value}" if value[:1] in ("=", "+", "-", "@") else value


def _write_csv(path: Path, suggestions: list[Suggestion]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        for item in suggestions:
            writer.writerow(
                {
                    "material_code": _csv_text(item.material_code),
                    "material_name": _csv_text(item.material_name),
                    "material_type_name": _csv_text(item.material_type_name),
                    "update_days": item.update_days,
                    "mean_gap_days": item.mean_gap_days,
                    "last_received_date": item.last_received_date.isoformat(),
                    "interval_days": item.interval_days,
                },
            )


def _print_table(suggestions: list[Suggestion], out: TextIO) -> None:
    out.write(f"{'Mã':<10}{'Vật tư':<34}{'Loại':<14}{'Ngày':>5}{'TB (ngày)':>11}{'Chu kỳ':>8}\n")
    for item in suggestions:
        out.write(
            f"{item.material_code:<10}{item.material_name[:32]:<34}"
            f"{item.material_type_name[:12]:<14}{item.update_days:>5}"
            f"{item.mean_gap_days:>11}{item.interval_days:>8}\n",
        )
    by_interval = {7: 0, 14: 0, 30: 0}
    for item in suggestions:
        by_interval[item.interval_days] += 1
    out.write(
        f"Tổng {len(suggestions)} vật tư: chu kỳ 7 ngày {by_interval[7]}, "
        f"14 ngày {by_interval[14]}, 30 ngày {by_interval[30]}.\n",
    )


async def run(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    apply: bool,
    min_days: int,
    window_days: int,
    today: date,
    csv_path: Path | None,
    out: TextIO,
) -> int:
    async with session_factory() as session:
        suggestions = await compute_suggestions(
            session,
            today=today,
            min_days=min_days,
            window_days=window_days,
        )
        _print_table(suggestions, out)
        if csv_path is not None:
            _write_csv(csv_path, suggestions)
            out.write(f"Đã ghi đề xuất vào {csv_path}.\n")
        if not apply:
            out.write("Chế độ dry-run: chưa ghi gì. Thêm --apply để nạp.\n")
            return 0
        inserted = await apply_suggestions(session, suggestions)
        await session.commit()
    skipped = len(suggestions) - inserted
    out.write(f"Đã nạp {inserted} vật tư; bỏ qua {skipped} vật tư đã có cấu hình.\n")
    return 0


async def amain(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Nạp danh sách theo dõi độ mới của giá mặc định")
    parser.add_argument("--apply", action="store_true", help="ghi vào DB (mặc định chỉ dry-run)")
    parser.add_argument("--min-days", type=int, default=DEFAULT_MIN_DAYS)
    parser.add_argument("--window-days", type=int, default=DEFAULT_WINDOW_DAYS)
    parser.add_argument("--csv", type=Path, default=None, help="xuất đề xuất ra file CSV")
    args = parser.parse_args(argv)
    if args.min_days < 2 or args.window_days < 1:
        parser.error("--min-days phải từ 2 và --window-days từ 1.")
    return await run(
        get_sessionmaker(),
        apply=args.apply,
        min_days=args.min_days,
        window_days=args.window_days,
        today=datetime.now(BUSINESS_TIMEZONE).date(),
        csv_path=args.csv,
        out=sys.stdout,
    )


def main() -> None:
    sys.exit(asyncio.run(amain(sys.argv[1:])))


if __name__ == "__main__":
    main()
