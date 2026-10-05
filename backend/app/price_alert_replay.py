"""Dry-run replay của engine thông báo biến động giá (L26).

Chạy engine thật trên dữ liệu hiện có trong MỘT giao dịch luôn bị hủy: không ghi gì, không gửi
Telegram. Dùng để đo tải tin trước khi bật tính năng.

    python -m app.price_alert_replay --weeks 8 [--ignore-trigger-source]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.db.session import get_sessionmaker
from app.models import (
    PriceAlertEvent,
    PriceAlertMessage,
    PriceAlertScannedVersion,
    PriceAlertScanRun,
)
from app.services.price_alert_candidates import (
    BUSINESS_TIMEZONE,
    VersionToScan,
    select_versions_to_scan,
)
from app.services.price_alert_messages import PriceAlertMessageService
from app.services.price_alert_scan import (
    SCAN_ADVISORY_LOCK_KEY,
    PriceAlertScanService,
    get_seed_user_id,
)
from app.services.price_alert_settings_service import PriceAlertSettingsService

_HISTORY_FOR_REPEAT_RULE = timedelta(days=14)
_EPOCH = datetime(2000, 1, 1, tzinfo=UTC)
SLOT_SECONDS = 30


@dataclass(slots=True)
class WeekRow:
    iso_week: tuple[int, int]
    events: int = 0
    medium_or_large: int = 0
    material_days: set[tuple[UUID, date]] = field(default_factory=set)


@dataclass(slots=True)
class ReplayReport:
    versions_scanned: int
    trigger_versions: int
    events: int
    errors: int
    by_level: dict[str, int]
    weeks: list[WeekRow]
    period_days: int
    material_days: int
    medium_or_large_material_days: int
    tables_unchanged: bool
    messages_by_status: dict[str, int] = field(default_factory=dict)
    immediate_messages_per_week: list[tuple[tuple[int, int], int]] = field(default_factory=list)

    @property
    def weeks_in_period(self) -> float:
        return max(self.period_days, 1) / 7


async def run_replay(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    weeks: int,
    ignore_trigger_source: bool,
    seed_email: str,
    now: datetime | None = None,
    pilot_emails: frozenset[str] = frozenset(),
    dump_events_to: str | None = None,
) -> ReplayReport | None:
    """Chạy replay rồi LUÔN hủy giao dịch. Trả `None` nếu cron đang giữ khóa quét."""
    moment = now or datetime.now(UTC)
    since = moment - timedelta(weeks=weeks)
    async with session_factory() as session:
        try:
            locked = (
                await session.execute(
                    select(func.pg_try_advisory_xact_lock(SCAN_ADVISORY_LOCK_KEY))
                )
            ).scalar_one()
            if not locked:
                return None
            # Replay không được giữ khóa hay chạy quá lâu trên hệ thống đang chạy.
            await session.execute(text("SET LOCAL lock_timeout = '5s'"))
            await session.execute(text("SET LOCAL statement_timeout = '120s'"))
            before = await _table_counts(session)

            # Trong giao dịch này coi như chưa từng quét; rollback sẽ trả lại nguyên trạng.
            await session.execute(delete(PriceAlertMessage))
            await session.execute(delete(PriceAlertEvent))
            await session.execute(delete(PriceAlertScannedVersion))
            settings = await PriceAlertSettingsService(session).get_or_create_settings()
            seed_user_id = await get_seed_user_id(session, seed_email)
            versions = [
                version
                for version in await select_versions_to_scan(session, watermark=_EPOCH)
                if version.confirmed_at >= since - _HISTORY_FOR_REPEAT_RULE
            ]
            service = PriceAlertScanService(session, seed_user_id=seed_user_id)
            messages = PriceAlertMessageService(
                session,
                seed_user_id=seed_user_id,
                pilot_emails=pilot_emails,
            )
            errors = 0
            # Mỗi ô 30 giây là một lần quét (một `scan_run`), như cron thật.
            slots: dict[int, list[VersionToScan]] = defaultdict(list)
            for version in versions:
                slots[int(version.confirmed_at.timestamp() // SLOT_SECONDS)].append(version)
            for slot in sorted(slots):
                slot_versions = slots[slot]
                slot_time = datetime.fromtimestamp((slot + 1) * SLOT_SECONDS, tz=UTC)
                run = PriceAlertScanRun(started_at=slot_time)
                session.add(run)
                await session.flush()
                counters = await service.scan_versions(
                    slot_versions,
                    settings=settings,
                    scan_run_id=run.id,
                    now_for=lambda version: version.confirmed_at,
                    ignore_trigger_source=ignore_trigger_source,
                )
                errors += counters.errors
                await messages.build_for_run(scan_run_id=run.id, now=slot_time, settings=settings)
            report = await _build_report(session, versions, errors, since)
            if dump_events_to:
                await _dump_events(session, dump_events_to, since)
        finally:
            await session.rollback()

    async with session_factory() as check:
        report.tables_unchanged = await _table_counts(check) == before
    return report


async def _table_counts(session: AsyncSession) -> dict[str, int]:
    counts = {}
    for model in (
        PriceAlertEvent,
        PriceAlertMessage,
        PriceAlertScannedVersion,
        PriceAlertScanRun,
    ):
        counts[model.__tablename__] = (
            await session.execute(select(func.count()).select_from(model))
        ).scalar_one()
    return counts


async def _build_report(
    session: AsyncSession,
    versions: list[VersionToScan],
    errors: int,
    since: datetime,
) -> ReplayReport:
    events = (
        await session.execute(
            select(
                PriceAlertEvent.material_id,
                PriceAlertEvent.level,
                PriceAlertEvent.created_at,
            ).where(PriceAlertEvent.created_at >= since),
        )
    ).all()
    weeks: dict[tuple[int, int], WeekRow] = {}
    by_level: dict[str, int] = defaultdict(int)
    material_days: dict[tuple[UUID, date], bool] = {}
    local_dates: list[date] = []
    for material_id, level, created_at in events:
        local = created_at.astimezone(BUSINESS_TIMEZONE).date()
        local_dates.append(local)
        iso = local.isocalendar()
        row = weeks.setdefault((iso[0], iso[1]), WeekRow((iso[0], iso[1])))
        row.events += 1
        by_level[level] += 1
        strong = level in ("medium", "large")
        row.medium_or_large += int(strong)
        row.material_days.add((material_id, local))
        key = (material_id, local)
        material_days[key] = material_days.get(key, False) or strong
    trigger_versions = (
        await session.execute(
            select(func.count())
            .select_from(PriceAlertScannedVersion)
            .where(
                PriceAlertScannedVersion.is_trigger_source.is_(True),
                PriceAlertScannedVersion.scanned_at >= since,
            ),
        )
    ).scalar_one()
    period_days = (max(local_dates) - min(local_dates)).days + 1 if local_dates else 0
    message_status: dict[str, int] = defaultdict(int)
    immediate_by_week: dict[tuple[int, int], int] = defaultdict(int)
    message_rows = (
        await session.execute(
            select(PriceAlertMessage.status, PriceAlertMessage.created_at).where(
                PriceAlertMessage.kind == "change",
                PriceAlertMessage.created_at >= since,
            ),
        )
    ).all()
    for status, created_at in message_rows:
        message_status[status] += 1
        if status == "pending":
            iso = created_at.astimezone(BUSINESS_TIMEZONE).date().isocalendar()
            immediate_by_week[(iso[0], iso[1])] += 1
    return ReplayReport(
        versions_scanned=sum(1 for v in versions if v.confirmed_at >= since),
        trigger_versions=trigger_versions,
        events=len(events),
        errors=errors,
        by_level=dict(by_level),
        weeks=[weeks[key] for key in sorted(weeks)],
        period_days=period_days,
        material_days=len(material_days),
        medium_or_large_material_days=sum(material_days.values()),
        tables_unchanged=False,
        messages_by_status=dict(message_status),
        immediate_messages_per_week=sorted(immediate_by_week.items()),
    )


async def _dump_events(session: AsyncSession, path: str, since: datetime) -> None:
    """Ghi sự kiện của lần replay ra tệp JSON để đối chiếu thủ công (trước khi hủy giao dịch)."""
    rows = (
        await session.execute(
            select(PriceAlertEvent)
            .where(PriceAlertEvent.created_at >= since)
            .order_by(
                PriceAlertEvent.sequence_number,
            ),
        )
    ).scalars()
    dump = [
        {
            column.name: (
                value.isoformat()
                if hasattr(value, "isoformat")
                else str(value)
                if value is not None and not isinstance(value, int | float | bool)
                else value
            )
            for column in PriceAlertEvent.__table__.columns
            for value in [getattr(row, column.name)]
        }
        for row in rows
    ]
    # Tệp nhỏ, ghi một lần trong lệnh CLI: không cần I/O bất đồng bộ.
    Path(path).write_text(  # noqa: ASYNC240
        json.dumps(dump, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )


def format_report(report: ReplayReport) -> str:
    per_week = report.weeks_in_period
    lines = [
        f"Đã quét {report.versions_scanned} version, {report.trigger_versions} là nguồn kích hoạt, "
        f"{report.errors} lỗi.",
        f"Sự kiện (theo chuỗi): {report.events} = {report.events / per_week:.1f} mỗi tuần "
        f"(kỳ {report.period_days} ngày = {per_week:.2f} tuần).",
        f"Theo mức: {report.by_level}",
        f"Gộp theo (vật tư, ngày): {report.material_days} = {report.material_days / per_week:.1f} "
        f"mỗi tuần; Trung bình và Lớn: {report.medium_or_large_material_days} = "
        f"{report.medium_or_large_material_days / per_week:.1f} mỗi tuần.",
        f"Tin theo đơn vị D5(b) (một tin cho mỗi người nhận, mỗi vật tư, mỗi lần quét): "
        f"{report.messages_by_status}",
        "",
        "Tuần ISO   Sự kiện   Trung bình+Lớn   Vật tư-ngày",
    ]
    for row in report.weeks:
        lines.append(
            f"{row.iso_week[0]}-W{row.iso_week[1]:02d}   {row.events:7d}   "
            f"{row.medium_or_large:14d}   {len(row.material_days):11d}",
        )
    lines.append("")
    lines.append(
        "Giao dịch đã hủy: các bảng price_alert_* không đổi."
        if report.tables_unchanged
        else "CẢNH BÁO: số dòng các bảng price_alert_* đã đổi sau replay."
    )
    return "\n".join(lines)


async def amain(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Dry-run replay thông báo biến động giá")
    parser.add_argument("--weeks", type=int, default=8)
    parser.add_argument(
        "--dump-events", help="Ghi các sự kiện của replay ra tệp JSON để đối chiếu."
    )
    parser.add_argument(
        "--ignore-trigger-source",
        action="store_true",
        help="Bỏ điều kiện D6 (tài khoản seed, độ trễ) để thấy nhiều dữ liệu hơn.",
    )
    args = parser.parse_args(argv)
    settings = get_settings()
    report = await run_replay(
        get_sessionmaker(),
        weeks=args.weeks,
        ignore_trigger_source=args.ignore_trigger_source,
        seed_email=settings.auth_seed_admin_email,
        dump_events_to=args.dump_events,
    )
    if report is None:
        print("Cron đang giữ khóa quét; thử lại sau ít giây.", file=sys.stderr)
        return 1
    print(format_report(report))
    return 0


def main() -> None:
    sys.exit(asyncio.run(amain(sys.argv[1:])))


if __name__ == "__main__":
    main()
