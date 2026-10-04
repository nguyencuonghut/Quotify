from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    PriceAlertEvent,
    PriceAlertMaterialThreshold,
    PriceAlertScanRun,
    PriceAlertSetting,
    QuoteLine,
    User,
)
from app.services.daily_min_series import get_daily_min_series
from app.services.price_alert_candidates import (
    BUSINESS_TIMEZONE,
    VersionToScan,
    is_trigger_source,
    record_scanned_version,
    resolve_candidate_lines,
    select_versions_to_scan,
    trigger_delay_working_days,
)
from app.services.price_alert_messages import PriceAlertMessageService
from app.services.price_alert_rules import (
    ChangeEvaluation,
    PricePoint,
    Thresholds,
    evaluate_change,
)
from app.services.price_alert_settings_service import PriceAlertSettingsService
from app.services.working_days import reference_window

logger = logging.getLogger(__name__)

# Khóa advisory của lần quét. `cron(unique=True)` của arq không chặn chạy chồng (L8e).
SCAN_ADVISORY_LOCK_KEY = 7_620_261_004
DEFAULT_BATCH_LIMIT = 500
_CENT = Decimal("0.01")
_MAX_ERROR_LENGTH = 255

ScanStatus = Literal["disabled", "locked", "idle", "scanned"]


@dataclass(frozen=True, slots=True)
class ScanOutcome:
    status: ScanStatus
    versions_scanned: int = 0
    events_created: int = 0
    error_count: int = 0
    scan_run_id: UUID | None = None


@dataclass(slots=True)
class _Counters:
    versions: int = 0
    events: int = 0
    errors: int = 0
    last_error: str | None = None


class PriceAlertScanService:
    """Quét version vừa chốt và ghi sự kiện biến động giá (L3, L8, L27).

    Service chỉ `flush`. Người gọi quyết định `commit` (cron) hay `rollback` (dry-run replay);
    khóa advisory kiểu transaction nên được nhả cùng giao dịch đó.
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        seed_user_id: UUID | None,
        batch_limit: int = DEFAULT_BATCH_LIMIT,
        pilot_emails: frozenset[str] = frozenset(),
    ) -> None:
        self.session = session
        self.seed_user_id = seed_user_id
        self.pilot_emails = pilot_emails
        self.batch_limit = batch_limit

    async def run_once(self, now: datetime) -> ScanOutcome:
        settings_service = PriceAlertSettingsService(self.session)
        settings = await settings_service.get_or_create_settings()
        if not settings.is_enabled:
            return ScanOutcome("disabled")

        locked = (
            await self.session.execute(
                select(func.pg_try_advisory_xact_lock(SCAN_ADVISORY_LOCK_KEY))
            )
        ).scalar_one()
        if not locked:
            return ScanOutcome("locked")

        scan_state = await settings_service.get_or_create_scan_state(for_update=True)
        watermark = scan_state.watermark_confirmed_at or now
        scan_state.last_run_at = now

        versions = await select_versions_to_scan(
            self.session,
            watermark=watermark,
            limit=self.batch_limit,
        )
        if not versions:
            await self.session.flush()
            return ScanOutcome("idle")

        run = PriceAlertScanRun(started_at=now)
        self.session.add(run)
        await self.session.flush()

        counters = await self.scan_versions(
            versions,
            settings=settings,
            scan_run_id=run.id,
            now_for=lambda _version: now,
        )
        # Không để một `confirmed_at` ở tương lai (đồng hồ lệch) kéo watermark vượt `now`.
        scan_state.watermark_confirmed_at = max(
            watermark,
            min(max(version.confirmed_at for version in versions), now),
        )
        try:
            async with self.session.begin_nested():
                messages = await PriceAlertMessageService(
                    self.session,
                    seed_user_id=self.seed_user_id,
                    pilot_emails=self.pilot_emails,
                ).build_for_run(scan_run_id=run.id, now=now, settings=settings)
            run.messages_created = messages.created
        except Exception as exc:
            # Lỗi ở bước tin không được làm hỏng lần quét: sự kiện đã ghi và watermark vẫn tiến.
            logger.warning("price_alert.messages_failed error=%s", type(exc).__name__)
            counters.errors += 1
            counters.last_error = f"messages {type(exc).__name__}: {exc}"[:_MAX_ERROR_LENGTH]
        run.finished_at = now
        run.versions_scanned = counters.versions
        run.events_created = counters.events
        run.error_count = counters.errors
        run.last_error = counters.last_error
        await self.session.flush()
        return ScanOutcome(
            "scanned",
            versions_scanned=counters.versions,
            events_created=counters.events,
            error_count=counters.errors,
            scan_run_id=run.id,
        )

    async def scan_versions(
        self,
        versions: Sequence[VersionToScan],
        *,
        settings: PriceAlertSetting,
        scan_run_id: UUID | None,
        now_for: Callable[[VersionToScan], datetime],
        ignore_trigger_source: bool = False,
    ) -> _Counters:
        counters = _Counters()
        for version in versions:
            try:
                async with self.session.begin_nested():
                    created = await self._scan_one(
                        version,
                        settings=settings,
                        scan_run_id=scan_run_id,
                        now=now_for(version),
                        ignore_trigger_source=ignore_trigger_source,
                    )
                counters.events += created
            except Exception as exc:
                # Một version lỗi không chặn các version khác. Vẫn đánh dấu đã quét để không thử
                # lại mỗi 30 giây trong cửa sổ chồng lấp; lỗi nằm ở `scan_runs`.
                logger.warning(
                    "price_alert.version_failed version_id=%s error=%s",
                    version.version_id,
                    type(exc).__name__,
                )
                counters.errors += 1
                counters.last_error = f"{type(exc).__name__}: {exc}"[:_MAX_ERROR_LENGTH]
                try:
                    async with self.session.begin_nested():
                        await record_scanned_version(
                            self.session,
                            version_id=version.version_id,
                            is_trigger_source=False,
                            trigger_delay_working_days=None,
                            scan_run_id=scan_run_id,
                        )
                except Exception:
                    # Không để lỗi ghi dấu làm hỏng cả lần quét (vòng lặp lỗi lặp lại mãi).
                    logger.exception("price_alert.mark_scanned_failed")
            counters.versions += 1
        return counters

    async def _scan_one(
        self,
        version: VersionToScan,
        *,
        settings: PriceAlertSetting,
        scan_run_id: UUID | None,
        now: datetime,
        ignore_trigger_source: bool,
    ) -> int:
        trigger = ignore_trigger_source or is_trigger_source(
            quote_created_by_id=version.quote_created_by_id,
            seed_user_id=self.seed_user_id,
            received_date=version.received_date,
            confirmed_at=version.confirmed_at,
            max_delay_working_days=settings.max_trigger_delay_working_days,
        )
        created = 0
        if trigger:
            candidates = await resolve_candidate_lines(self.session, version)
            chains = sorted(
                {(line.material_id, line.delivery_month.replace(day=1)) for line in candidates},
            )
            for material_id, month in chains:
                created += await self._evaluate_chain(
                    version,
                    material_id=material_id,
                    delivery_month=month,
                    settings=settings,
                    scan_run_id=scan_run_id,
                    now=now,
                )
        await record_scanned_version(
            self.session,
            version_id=version.version_id,
            is_trigger_source=trigger,
            trigger_delay_working_days=trigger_delay_working_days(
                version.received_date,
                version.confirmed_at,
            ),
            scan_run_id=scan_run_id,
        )
        return created

    async def _evaluate_chain(
        self,
        version: VersionToScan,
        *,
        material_id: UUID,
        delivery_month: date,
        settings: PriceAlertSetting,
        scan_run_id: UUID | None,
        now: datetime,
    ) -> int:
        start, _ = reference_window(version.received_date, settings.reference_working_days)
        series = await get_daily_min_series(
            self.session,
            material_id=material_id,
            delivery_month=delivery_month,
            start=start,
            end=version.received_date,
        )
        new_point = next((p for p in series if p.received_date == version.received_date), None)
        # Điểm của ngày chỉ đổi khi chính version này giữ giá thấp nhất của ngày (D2).
        if new_point is None or new_point.version_id != version.version_id:
            return 0
        prior = [
            PricePoint(point.received_date, point.price)
            for point in series
            if point.received_date < version.received_date
        ]
        thresholds = await load_thresholds(self.session, material_id, settings)
        evaluation = evaluate_change(
            PricePoint(new_point.received_date, new_point.price),
            prior,
            thresholds,
        )
        if evaluation is None:
            return 0
        if await self._is_repeat(material_id, delivery_month, evaluation, settings, now):
            return 0
        ref_line_id = next(
            (p.line_id for p in series if p.received_date == evaluation.received_date_ref),
            None,
        )
        cnf = await self._cnf(new_point.line_id, ref_line_id, evaluation.received_date_ref)

        result = await self.session.execute(
            pg_insert(PriceAlertEvent)
            .values(
                scan_run_id=scan_run_id,
                quote_version_id=version.version_id,
                material_id=material_id,
                delivery_month=delivery_month,
                kind="change",
                direction=evaluation.direction,
                level=evaluation.level,
                rule=evaluation.rule,
                percent_change=_cents(evaluation.percent_change),
                price_new=evaluation.price_new,
                price_ref=evaluation.price_ref,
                received_date_new=evaluation.received_date_new,
                received_date_ref=evaluation.received_date_ref,
                window_min=evaluation.window_min,
                window_max=evaluation.window_max,
                window_min_date=evaluation.window_min_date,
                window_max_date=evaluation.window_max_date,
                reference_point_count=evaluation.reference_point_count,
                secondary_rule=evaluation.secondary_rule,
                secondary_percent=(
                    None
                    if evaluation.secondary_percent is None
                    else _cents(evaluation.secondary_percent)
                ),
                secondary_price_ref=evaluation.secondary_price_ref,
                secondary_date_ref=evaluation.secondary_date_ref,
                cnf_price_new=cnf[0],
                cnf_price_ref=cnf[1],
                cnf_date_ref=cnf[2],
                created_at=now,
            )
            .on_conflict_do_nothing(
                index_elements=["quote_version_id", "material_id", "delivery_month"],
                index_where=text("kind = 'change'"),
            ),
        )
        return int(result.rowcount or 0)  # type: ignore[attr-defined]

    async def _cnf(
        self,
        new_line_id: UUID,
        ref_line_id: UUID | None,
        ref_date: date,
    ) -> tuple[Decimal | None, Decimal | None, date | None]:
        """QĐ-8: CNF (USD/MT) chỉ có khi dòng là USD/MT; mốc so sánh chỉ khi cả hai bên đều vậy."""
        ids = [new_line_id, *([ref_line_id] if ref_line_id is not None else [])]
        rows = (
            await self.session.execute(
                select(
                    QuoteLine.id,
                    QuoteLine.currency,
                    QuoteLine.unit,
                    QuoteLine.price_original,
                ).where(QuoteLine.id.in_(ids)),
            )
        ).all()
        usd = {row[0]: row[3] for row in rows if (row[1], row[2]) == ("USD", "MT")}
        new_cnf = usd.get(new_line_id)
        if new_cnf is None:
            return None, None, None
        ref_cnf = usd.get(ref_line_id) if ref_line_id is not None else None
        return new_cnf, ref_cnf, ref_date if ref_cnf is not None else None

    async def _is_repeat(
        self,
        material_id: UUID,
        delivery_month: date,
        evaluation: ChangeEvaluation,
        settings: PriceAlertSetting,
        now: datetime,
    ) -> bool:
        """D5(a): cùng chiều và cùng mức với sự kiện gần nhất của chuỗi trong cửa sổ chống lặp."""
        last = (
            await self.session.execute(
                select(PriceAlertEvent.direction, PriceAlertEvent.level, PriceAlertEvent.created_at)
                .where(
                    PriceAlertEvent.kind == "change",
                    PriceAlertEvent.material_id == material_id,
                    PriceAlertEvent.delivery_month == delivery_month,
                )
                .order_by(PriceAlertEvent.sequence_number.desc())
                .limit(1),
            )
        ).first()
        if last is None:
            return False
        last_direction, last_level, last_created_at = last
        age_days = (_local_date(now) - _local_date(last_created_at)).days
        return (
            age_days <= settings.dedupe_window_days
            and last_direction == evaluation.direction
            and last_level == evaluation.level
        )


async def load_thresholds(
    session: AsyncSession,
    material_id: UUID,
    settings: PriceAlertSetting,
) -> Thresholds:
    """Ngưỡng hiệu lực: ghi đè theo vật tư nếu có, không thì mặc định chung (D4)."""
    override = (
        await session.execute(
            select(
                PriceAlertMaterialThreshold.light_from_percent,
                PriceAlertMaterialThreshold.medium_from_percent,
                PriceAlertMaterialThreshold.large_over_percent,
            ).where(PriceAlertMaterialThreshold.material_id == material_id),
        )
    ).first()
    if override is not None and override[0] is not None:
        return Thresholds(light=override[0], medium=override[1], large=override[2])
    return Thresholds(
        light=settings.light_from_percent,
        medium=settings.medium_from_percent,
        large=settings.large_over_percent,
    )


def _local_date(moment: datetime) -> date:
    return moment.astimezone(BUSINESS_TIMEZONE).date()


def _cents(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


async def get_seed_user_id(session: AsyncSession, seed_email: str) -> UUID | None:
    """Id tài khoản seed admin (tài khoản import, D6). Không có thì không ai bị loại."""
    return (
        await session.execute(select(User.id).where(User.email == seed_email.strip()))
    ).scalar_one_or_none()
