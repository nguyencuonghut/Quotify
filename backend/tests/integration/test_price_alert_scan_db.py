"""Lần quét `run_once` trên PostgreSQL thật: từ version được chốt đến dòng sự kiện (Slice 5)."""

from __future__ import annotations

import itertools
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from db_helpers import (
    create_material,
    create_priced_line,
    create_quote_shell,
    create_user,
    create_version_with_lines,
)
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.services.price_alert_scan as scan_module
from app.models import (
    PriceAlertEvent,
    PriceAlertMaterialThreshold,
    PriceAlertScannedVersion,
    PriceAlertScanRun,
    PriceAlertScanState,
    PriceAlertSetting,
)
from app.services.daily_min_series import get_daily_min_series
from app.services.price_alert_candidates import record_scanned_version, resolve_candidate_lines
from app.services.price_alert_scan import (
    SCAN_ADVISORY_LOCK_KEY,
    PriceAlertScanService,
    ScanOutcome,
)
from app.services.price_alert_settings_service import (
    PriceAlertSettingsService,
    PriceAlertSettingsValues,
)

pytestmark = pytest.mark.integration

DEC = date(2045, 12, 1)
_days = itertools.count(0, 30)


class Day:
    """Một ngày thử riêng cho mỗi test (DB dùng chung cả phiên) và các mốc xoay quanh nó."""

    def __init__(self) -> None:
        self.date = date(2045, 1, 1) + timedelta(days=next(_days))
        self.midnight = datetime(self.date.year, self.date.month, self.date.day, tzinfo=UTC)

    def at(self, offset_days: int = 0, hour: int = 3) -> datetime:
        return self.midnight + timedelta(days=offset_days, hours=hour)

    def day(self, offset_days: int) -> date:
        return self.date + timedelta(days=offset_days)


@pytest.fixture
def day() -> Day:
    return Day()


@pytest.fixture(autouse=True)
async def reset_state(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[None]:
    async def reset() -> None:
        async with session_factory() as session:
            await session.execute(
                update(PriceAlertSetting).values(is_enabled=False, dedupe_window_days=14)
            )
            await session.execute(
                update(PriceAlertScanState).values(
                    watermark_confirmed_at=None, enabled_since=None, last_run_at=None
                )
            )
            await session.commit()

    await reset()
    yield
    await reset()


async def enable(
    session_factory: async_sessionmaker[AsyncSession],
    day: Day,
    **overrides: object,
) -> None:
    """Bật tính năng; watermark là nửa đêm của ngày thử nên chỉ version sau đó được quét."""
    async with session_factory() as session:
        setting = await PriceAlertSettingsService(session).get_or_create_settings()
        values = {
            "is_enabled": True,
            "reference_working_days": setting.reference_working_days,
            "light_from_percent": setting.light_from_percent,
            "medium_from_percent": setting.medium_from_percent,
            "large_over_percent": setting.large_over_percent,
            "anomaly_percent": setting.anomaly_percent,
            "anomaly_lookback_days": setting.anomaly_lookback_days,
            "max_trigger_delay_working_days": setting.max_trigger_delay_working_days,
            "staff_lookback_days": setting.staff_lookback_days,
            "dedupe_window_days": setting.dedupe_window_days,
            "immediate_cap_per_scan": setting.immediate_cap_per_scan,
            "digest_hour_local": setting.digest_hour_local,
            **overrides,
        }
        await PriceAlertSettingsService(session).update_settings(
            values=PriceAlertSettingsValues(**values),  # type: ignore[arg-type]
            updated_by_id=await _any_user(session_factory),
            now=day.midnight,
        )
        await session.commit()


async def _any_user(session_factory: async_sessionmaker[AsyncSession]) -> uuid.UUID:
    return await create_user(session_factory)


async def run_once(
    session_factory: async_sessionmaker[AsyncSession],
    now: datetime,
    *,
    seed_user_id: uuid.UUID | None = None,
) -> ScanOutcome:
    async with session_factory() as session:
        outcome = await PriceAlertScanService(session, seed_user_id=seed_user_id).run_once(now)
        await session.commit()
    return outcome


async def prior_points(
    session_factory: async_sessionmaker[AsyncSession],
    material: uuid.UUID,
    day: Day,
    prices: dict[int, int],
) -> None:
    """Các điểm trước (đã quét xong, không phải việc của lần quét), khóa theo số ngày lùi."""
    for offset, price in prices.items():
        version, _ = await create_priced_line(
            session_factory,
            material_id=material,
            price=price,
            received_date=day.day(offset),
            delivery_month=DEC,
            confirmed_at=day.at(offset),
        )
        async with session_factory() as session:
            await record_scanned_version(
                session, version_id=version, is_trigger_source=True, trigger_delay_working_days=0
            )
            await session.commit()


async def new_quote(
    session_factory: async_sessionmaker[AsyncSession],
    material: uuid.UUID,
    day: Day,
    price: int,
    *,
    offset: int = 0,
    created_by: uuid.UUID | None = None,
) -> uuid.UUID:
    quote = await create_quote_shell(session_factory, created_by_id=created_by)
    version, _ = await create_version_with_lines(
        session_factory,
        quote_id=quote,
        version_number=1,
        received_date=day.day(offset),
        lines=[(material, price, DEC)],
        confirmed_at=day.at(offset, hour=4),
    )
    return version


async def events(
    session_factory: async_sessionmaker[AsyncSession], material: uuid.UUID
) -> list[PriceAlertEvent]:
    async with session_factory() as session:
        return list(
            (
                await session.execute(
                    select(PriceAlertEvent)
                    .where(PriceAlertEvent.material_id == material)
                    .order_by(PriceAlertEvent.created_at, PriceAlertEvent.id)
                )
            ).scalars()
        )


async def count(session_factory: async_sessionmaker[AsyncSession], model: type) -> int:
    async with session_factory() as session:
        return (await session.execute(select(func.count()).select_from(model))).scalar_one()


async def test_confirming_a_version_creates_exactly_one_event_with_every_field(
    session_factory: async_sessionmaker[AsyncSession], day: Day
) -> None:
    material = await create_material(session_factory)
    person = await create_user(session_factory)
    await enable(session_factory, day)
    await prior_points(session_factory, material, day, {-3: 7900, -2: 7720, -1: 7800})
    version = await new_quote(session_factory, material, day, 8150, created_by=person)
    runs_before = await count(session_factory, PriceAlertScanRun)

    outcome = await run_once(session_factory, day.at(0, 4))

    assert (outcome.status, outcome.versions_scanned, outcome.events_created) == ("scanned", 1, 1)
    [event] = await events(session_factory, material)
    assert (event.kind, event.direction, event.level, event.rule) == (
        "change",
        "up",
        "medium",
        "R2",
    )
    assert event.quote_version_id == version
    assert event.percent_change == Decimal("5.57")
    assert (event.price_new, event.price_ref) == (Decimal("8150.00"), Decimal("7720.00"))
    assert event.received_date_ref == day.day(-2)
    assert event.secondary_rule == "R1"
    assert event.secondary_percent == Decimal("4.49")
    assert (event.window_min, event.window_max) == (Decimal("7720.00"), Decimal("7900.00"))
    assert event.reference_point_count == 3
    assert event.delivery_month == DEC
    assert event.scan_run_id == outcome.scan_run_id
    async with session_factory() as session:
        scanned = await session.get(PriceAlertScannedVersion, version)
        state = (await session.execute(select(PriceAlertScanState))).scalar_one()
    assert scanned is not None and scanned.is_trigger_source is True
    assert scanned.trigger_delay_working_days == 0
    assert state.watermark_confirmed_at == day.at(0, 4)
    assert state.last_run_at == day.at(0, 4)
    assert await count(session_factory, PriceAlertScanRun) == runs_before + 1


async def test_running_again_is_idle_updates_the_heartbeat_and_writes_no_run_row(
    session_factory: async_sessionmaker[AsyncSession], day: Day
) -> None:
    material = await create_material(session_factory)
    await enable(session_factory, day)
    await prior_points(session_factory, material, day, {-1: 100})
    await new_quote(session_factory, material, day, 110)
    await run_once(session_factory, day.at(0, 4))
    runs, evts = (
        await count(session_factory, PriceAlertScanRun),
        await count(session_factory, PriceAlertEvent),
    )

    outcome = await run_once(session_factory, day.at(0, 5))

    assert outcome.status == "idle"
    assert await count(session_factory, PriceAlertScanRun) == runs
    assert await count(session_factory, PriceAlertEvent) == evts
    async with session_factory() as session:
        state = (await session.execute(select(PriceAlertScanState))).scalar_one()
    assert state.last_run_at == day.at(0, 5)


async def test_a_disabled_flag_does_nothing_and_leaves_the_heartbeat_alone(
    session_factory: async_sessionmaker[AsyncSession], day: Day
) -> None:
    material = await create_material(session_factory)
    await enable(session_factory, day)
    await prior_points(session_factory, material, day, {-1: 100})
    await new_quote(session_factory, material, day, 110)
    async with session_factory() as session:
        await session.execute(update(PriceAlertSetting).values(is_enabled=False))
        await session.commit()

    outcome = await run_once(session_factory, day.at(0, 4))

    assert outcome.status == "disabled"
    assert await events(session_factory, material) == []
    async with session_factory() as session:
        state = (await session.execute(select(PriceAlertScanState))).scalar_one()
    assert state.last_run_at is None


async def test_only_one_connection_scans_at_a_time(
    session_factory: async_sessionmaker[AsyncSession], day: Day
) -> None:
    material = await create_material(session_factory)
    await enable(session_factory, day)
    await prior_points(session_factory, material, day, {-1: 100})
    await new_quote(session_factory, material, day, 110)

    async with session_factory() as holder:
        await holder.execute(select(func.pg_advisory_xact_lock(SCAN_ADVISORY_LOCK_KEY)))
        blocked = await run_once(session_factory, day.at(0, 4))
    free = await run_once(session_factory, day.at(0, 4))

    assert blocked.status == "locked"
    assert free.status == "scanned"
    assert len(await events(session_factory, material)) == 1


async def test_a_version_committed_late_inside_the_overlap_is_still_scanned(
    session_factory: async_sessionmaker[AsyncSession], day: Day
) -> None:
    material, other = await create_material(session_factory), await create_material(session_factory)
    await enable(session_factory, day)
    await prior_points(session_factory, material, day, {-1: 100})
    await prior_points(session_factory, other, day, {-1: 100})
    await new_quote(session_factory, material, day, 110)
    await run_once(session_factory, day.at(0, 4))  # watermark tiến tới 04:00
    # version có confirmed_at 03:58 (trước watermark 2 phút) nhưng commit sau lần quét đầu
    late_quote = await create_quote_shell(session_factory)
    await create_version_with_lines(
        session_factory,
        quote_id=late_quote,
        version_number=1,
        received_date=day.day(0),
        lines=[(other, 110, DEC)],
        confirmed_at=day.at(0, 4) - timedelta(minutes=2),
    )

    await run_once(session_factory, day.at(0, 5))

    assert len(await events(session_factory, other)) == 1


async def test_a_failing_version_is_isolated_recorded_and_the_watermark_still_advances(
    session_factory: async_sessionmaker[AsyncSession], day: Day, monkeypatch: pytest.MonkeyPatch
) -> None:
    good, bad = await create_material(session_factory), await create_material(session_factory)
    await enable(session_factory, day)
    await prior_points(session_factory, good, day, {-1: 100})
    await prior_points(session_factory, bad, day, {-1: 100})
    bad_version = await new_quote(session_factory, bad, day, 110)
    good_version = await new_quote(session_factory, good, day, 110)
    original_resolve = resolve_candidate_lines

    async def explode(session, version):  # type: ignore[no-untyped-def]
        if version.version_id == bad_version:
            raise RuntimeError("giá lỗi")
        return await original_resolve(session, version)

    monkeypatch.setattr(scan_module, "resolve_candidate_lines", explode)

    outcome = await run_once(session_factory, day.at(0, 6))

    assert (outcome.versions_scanned, outcome.events_created, outcome.error_count) == (2, 1, 1)
    assert len(await events(session_factory, good)) == 1
    assert await events(session_factory, bad) == []
    async with session_factory() as session:
        run = await session.get(PriceAlertScanRun, outcome.scan_run_id)
        state = (await session.execute(select(PriceAlertScanState))).scalar_one()
        assert await session.get(PriceAlertScannedVersion, bad_version) is not None
        assert await session.get(PriceAlertScannedVersion, good_version) is not None
    assert run is not None and run.error_count == 1 and "giá lỗi" in (run.last_error or "")
    assert state.watermark_confirmed_at == day.at(0, 4)


async def test_data_older_than_the_enable_moment_produces_no_events(
    session_factory: async_sessionmaker[AsyncSession], day: Day
) -> None:
    material = await create_material(session_factory)
    await enable(session_factory, day)
    await prior_points(session_factory, material, day, {-3: 100})
    old_quote = await create_quote_shell(session_factory)
    await create_version_with_lines(
        session_factory,
        quote_id=old_quote,
        version_number=1,
        received_date=day.day(-1),
        lines=[(material, 150, DEC)],
        confirmed_at=day.at(-1, 4),
    )

    outcome = await run_once(session_factory, day.at(0, 5))

    assert outcome.status == "idle"
    assert await events(session_factory, material) == []


async def test_the_seed_account_is_scanned_but_never_triggers(
    session_factory: async_sessionmaker[AsyncSession], day: Day
) -> None:
    material = await create_material(session_factory)
    seed = await create_user(session_factory)
    await enable(session_factory, day)
    await prior_points(session_factory, material, day, {-1: 100})
    version = await new_quote(session_factory, material, day, 130, created_by=seed)

    await run_once(session_factory, day.at(0, 5), seed_user_id=seed)

    assert await events(session_factory, material) == []
    async with session_factory() as session:
        scanned = await session.get(PriceAlertScannedVersion, version)
    assert scanned is not None and scanned.is_trigger_source is False


async def test_a_second_quote_that_does_not_lower_the_day_minimum_makes_no_event(
    session_factory: async_sessionmaker[AsyncSession], day: Day
) -> None:
    material = await create_material(session_factory)
    # Cửa sổ chống lặp 0 ngày để chỉ quy tắc "điểm của ngày không đổi" chặn được sự kiện thứ hai.
    await enable(session_factory, day, dedupe_window_days=0)
    await prior_points(session_factory, material, day, {-1: 100})
    await new_quote(session_factory, material, day, 110)
    await run_once(session_factory, day.at(0, 4))
    await new_quote(session_factory, material, day, 125)

    await run_once(session_factory, day.at(1, 5))

    assert len(await events(session_factory, material)) == 1


async def _chain_with_history(
    session_factory: async_sessionmaker[AsyncSession], day: Day
) -> uuid.UUID:
    material = await create_material(session_factory)
    await enable(session_factory, day)
    await prior_points(session_factory, material, day, {-1: 1000})
    return material


async def test_repeating_the_same_direction_and_level_inside_the_window_is_dropped(
    session_factory: async_sessionmaker[AsyncSession], day: Day
) -> None:
    material = await _chain_with_history(session_factory, day)
    await new_quote(session_factory, material, day, 1060)  # +6% Trung bình, tăng
    await run_once(session_factory, day.at(0, 4))
    await new_quote(session_factory, material, day, 1070, offset=1)  # so đáy 1000: +7% cùng mức
    await run_once(session_factory, day.at(1, 5))

    assert [(e.direction, e.level) for e in await events(session_factory, material)] == [
        ("up", "medium")
    ]


async def test_escalation_or_a_change_of_direction_creates_a_new_event(
    session_factory: async_sessionmaker[AsyncSession], day: Day
) -> None:
    material = await _chain_with_history(session_factory, day)
    await new_quote(session_factory, material, day, 1060)  # +6% tăng Trung bình
    await run_once(session_factory, day.at(0, 4))
    await new_quote(session_factory, material, day, 1200, offset=1)  # tăng Lớn
    await run_once(session_factory, day.at(1, 5))
    await new_quote(session_factory, material, day, 1000, offset=2)  # giảm
    await run_once(session_factory, day.at(2, 5))

    kinds = [(e.direction, e.level) for e in await events(session_factory, material)]

    assert kinds == [("up", "medium"), ("up", "large"), ("down", "large")]


async def test_the_repeat_window_expires_after_the_configured_days(
    session_factory: async_sessionmaker[AsyncSession], day: Day
) -> None:
    material = await create_material(session_factory)
    await enable(session_factory, day, dedupe_window_days=2)
    await prior_points(session_factory, material, day, {-1: 1000})
    await new_quote(session_factory, material, day, 1060)
    await run_once(session_factory, day.at(0, 4))
    await new_quote(session_factory, material, day, 1070, offset=2)  # tuổi 2 ngày: còn trong cửa sổ
    await run_once(session_factory, day.at(2, 5))
    await new_quote(session_factory, material, day, 1075, offset=3)  # tuổi 3 ngày: hết cửa sổ
    await run_once(session_factory, day.at(3, 5))

    assert [e.received_date_new for e in await events(session_factory, material)] == [
        day.day(0),
        day.day(3),
    ]


async def test_a_light_event_counts_as_already_sent_for_the_repeat_rule(
    session_factory: async_sessionmaker[AsyncSession], day: Day
) -> None:
    material = await _chain_with_history(session_factory, day)
    await new_quote(session_factory, material, day, 1030)  # +3% Nhẹ
    await run_once(session_factory, day.at(0, 4))
    await new_quote(session_factory, material, day, 1032, offset=1)  # so đáy 1000: +3,2% Nhẹ tăng
    await run_once(session_factory, day.at(1, 5))

    assert [e.level for e in await events(session_factory, material)] == ["light"]


async def test_an_adjusted_version_with_an_unscanned_source_evaluates_every_line(
    session_factory: async_sessionmaker[AsyncSession], day: Day
) -> None:
    material = await create_material(session_factory)
    await enable(session_factory, day)
    await prior_points(session_factory, material, day, {-1: 100})
    quote = await create_quote_shell(session_factory)
    first, _ = await create_version_with_lines(
        session_factory,
        quote_id=quote,
        version_number=1,
        received_date=day.day(0),
        lines=[(material, 100, DEC)],
        confirmed_at=day.at(0, 3),
    )
    second, _ = await create_version_with_lines(
        session_factory,
        quote_id=quote,
        version_number=2,
        received_date=day.day(0),
        lines=[(material, 110, DEC)],
        confirmed_at=day.at(0, 4),
        supersedes_version_id=first,
    )

    await run_once(session_factory, day.at(0, 5))

    [event] = await events(session_factory, material)
    assert event.quote_version_id == second


async def test_deleting_a_line_creates_no_event_for_the_unchanged_ones(
    session_factory: async_sessionmaker[AsyncSession], day: Day
) -> None:
    kept, dropped = await create_material(session_factory), await create_material(session_factory)
    await enable(session_factory, day)
    await prior_points(session_factory, kept, day, {-1: 100})
    quote = await create_quote_shell(session_factory)
    first, _ = await create_version_with_lines(
        session_factory,
        quote_id=quote,
        version_number=1,
        received_date=day.day(0),
        lines=[(kept, 100, DEC), (dropped, 100, DEC)],
        confirmed_at=day.at(0, 3),
    )
    await create_version_with_lines(
        session_factory,
        quote_id=quote,
        version_number=2,
        received_date=day.day(0),
        lines=[(kept, 100, DEC)],
        confirmed_at=day.at(0, 4),
        supersedes_version_id=first,
    )

    await run_once(session_factory, day.at(0, 5))

    assert await events(session_factory, kept) == []
    assert await events(session_factory, dropped) == []


async def test_a_per_material_override_changes_the_level(
    session_factory: async_sessionmaker[AsyncSession], day: Day
) -> None:
    material = await create_material(session_factory)
    await enable(session_factory, day)
    async with session_factory() as session:
        session.add(
            PriceAlertMaterialThreshold(
                material_id=material,
                light_from_percent=Decimal("1"),
                medium_from_percent=Decimal("2"),
                large_over_percent=Decimal("3"),
            )
        )
        await session.commit()
    await prior_points(session_factory, material, day, {-1: 100})
    await new_quote(session_factory, material, day, 104)  # +4% > 3 → Lớn theo ghi đè

    await run_once(session_factory, day.at(0, 4))

    [event] = await events(session_factory, material)
    assert event.level == "large"


async def test_a_late_confirmation_is_scanned_but_is_not_a_trigger_source(
    session_factory: async_sessionmaker[AsyncSession], day: Day
) -> None:
    material = await create_material(session_factory)
    await enable(session_factory, day)
    await prior_points(session_factory, material, day, {-30: 100})
    quote = await create_quote_shell(session_factory)
    version, _ = await create_version_with_lines(
        session_factory,
        quote_id=quote,
        version_number=1,
        received_date=day.day(-20),
        lines=[(material, 150, DEC)],
        confirmed_at=day.at(0, 4),
    )

    await run_once(session_factory, day.at(0, 5))

    assert await events(session_factory, material) == []
    async with session_factory() as session:
        scanned = await session.get(PriceAlertScannedVersion, version)
    assert scanned is not None and scanned.is_trigger_source is False
    assert (scanned.trigger_delay_working_days or 0) > 3


async def test_the_unique_index_makes_inserting_the_same_event_twice_a_no_op(
    session_factory: async_sessionmaker[AsyncSession], day: Day
) -> None:
    material = await create_material(session_factory)
    # Cửa sổ chống lặp 0 ngày và quét lại sau một ngày: chỉ chỉ mục UNIQUE còn chặn được.
    await enable(session_factory, day, dedupe_window_days=0)
    await prior_points(session_factory, material, day, {-1: 100})
    version = await new_quote(session_factory, material, day, 110)
    await run_once(session_factory, day.at(0, 5))
    async with session_factory() as session:
        await session.execute(
            text("DELETE FROM price_alert_scanned_versions WHERE version_id = :v"), {"v": version}
        )
        await session.commit()

    await run_once(session_factory, day.at(1, 5))

    assert len(await events(session_factory, material)) == 1


async def test_a_database_error_in_one_version_does_not_break_the_rest_of_the_batch(
    session_factory: async_sessionmaker[AsyncSession], day: Day, monkeypatch: pytest.MonkeyPatch
) -> None:
    good, bad = await create_material(session_factory), await create_material(session_factory)
    await enable(session_factory, day)
    await prior_points(session_factory, good, day, {-1: 100})
    await prior_points(session_factory, bad, day, {-1: 100})
    await new_quote(session_factory, bad, day, 110)
    await new_quote(session_factory, good, day, 110)
    real = get_daily_min_series

    async def broken(session: AsyncSession, **kwargs: Any) -> Any:
        if kwargs["material_id"] == bad:
            await session.execute(text("SELECT 1 / 0"))
        return await real(session, **kwargs)

    monkeypatch.setattr(scan_module, "get_daily_min_series", broken)

    outcome = await run_once(session_factory, day.at(0, 6))

    assert (outcome.versions_scanned, outcome.events_created, outcome.error_count) == (2, 1, 1)
    assert len(await events(session_factory, good)) == 1


async def test_a_small_batch_limit_takes_the_backlog_in_order_over_several_runs(
    session_factory: async_sessionmaker[AsyncSession], day: Day
) -> None:
    materials = [await create_material(session_factory) for _ in range(3)]
    await enable(session_factory, day)
    for index, material in enumerate(materials):
        await prior_points(session_factory, material, day, {-1: 100})
        quote = await create_quote_shell(session_factory)
        await create_version_with_lines(
            session_factory,
            quote_id=quote,
            version_number=1,
            received_date=day.day(0),
            lines=[(material, 110, DEC)],
            confirmed_at=day.at(0, 3) + timedelta(minutes=index),
        )

    async def run(now: datetime) -> ScanOutcome:
        async with session_factory() as session:
            outcome = await PriceAlertScanService(
                session, seed_user_id=None, batch_limit=2
            ).run_once(now)
            await session.commit()
        return outcome

    first, second, third = await run(day.at(0, 6)), await run(day.at(0, 6)), await run(day.at(0, 6))

    assert (first.versions_scanned, second.versions_scanned, third.status) == (2, 1, "idle")
    for material in materials:
        assert len(await events(session_factory, material)) == 1


async def test_a_confirmation_time_in_the_future_cannot_drag_the_watermark_past_now(
    session_factory: async_sessionmaker[AsyncSession], day: Day
) -> None:
    material = await create_material(session_factory)
    await enable(session_factory, day)
    await prior_points(session_factory, material, day, {-1: 100})
    quote = await create_quote_shell(session_factory)
    await create_version_with_lines(
        session_factory,
        quote_id=quote,
        version_number=1,
        received_date=day.day(0),
        lines=[(material, 110, DEC)],
        confirmed_at=day.at(0, 3) + timedelta(days=5),
    )

    await run_once(session_factory, day.at(0, 6))

    async with session_factory() as session:
        state = (await session.execute(select(PriceAlertScanState))).scalar_one()
    assert state.watermark_confirmed_at == day.at(0, 6)


async def test_dry_run_replay_reports_the_events_and_leaves_every_table_unchanged(
    session_factory: async_sessionmaker[AsyncSession], day: Day
) -> None:
    from app.price_alert_replay import format_report, run_replay

    material, other = await create_material(session_factory), await create_material(session_factory)
    person = await create_user(session_factory)
    # Hai chuỗi, mỗi chuỗi một biến động Trung bình do người thật nhập. Replay bỏ qua cờ bật.
    await prior_points(session_factory, material, day, {-1: 1000})
    await prior_points(session_factory, other, day, {-1: 1000})
    await new_quote(session_factory, material, day, 1060, created_by=person)
    await new_quote(session_factory, other, day, 1120, created_by=person)
    async with session_factory() as session:
        await session.execute(update(PriceAlertSetting).values(is_enabled=False))
        await session.commit()
    before = {
        model: await count(session_factory, model)
        for model in (PriceAlertEvent, PriceAlertScannedVersion, PriceAlertScanRun)
    }

    report = await run_replay(
        session_factory,
        weeks=1,
        ignore_trigger_source=False,
        seed_email="khong-ton-tai@example.com",
        now=day.at(1),
    )

    assert report is not None
    assert report.tables_unchanged is True
    assert report.events == 2
    assert report.errors == 0
    assert report.by_level == {"medium": 1, "large": 1}
    assert report.material_days == 2
    assert report.medium_or_large_material_days == 2
    assert sum(row.events for row in report.weeks) == 2
    assert "2 " in format_report(report)
    after = {
        model: await count(session_factory, model)
        for model in (PriceAlertEvent, PriceAlertScannedVersion, PriceAlertScanRun)
    }
    assert after == before
    assert await events(session_factory, material) == []


async def test_dry_run_replay_gives_way_to_a_running_scan(
    session_factory: async_sessionmaker[AsyncSession], day: Day
) -> None:
    from app.price_alert_replay import run_replay

    async with session_factory() as holder:
        await holder.execute(select(func.pg_advisory_xact_lock(SCAN_ADVISORY_LOCK_KEY)))
        report = await run_replay(
            session_factory,
            weeks=1,
            ignore_trigger_source=False,
            seed_email="khong-ton-tai@example.com",
            now=day.at(1),
        )

    assert report is None


async def test_a_failure_while_building_messages_keeps_the_events_and_the_watermark(
    session_factory: async_sessionmaker[AsyncSession], day: Day, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.price_alert_messages import PriceAlertMessageService

    material = await create_material(session_factory)
    await enable(session_factory, day)
    await prior_points(session_factory, material, day, {-1: 100})
    await new_quote(session_factory, material, day, 110)

    async def broken(self: object, **kwargs: object) -> None:
        raise RuntimeError("lỗi dựng tin")

    monkeypatch.setattr(PriceAlertMessageService, "build_for_run", broken)

    outcome = await run_once(session_factory, day.at(0, 6))

    assert (outcome.status, outcome.events_created, outcome.error_count) == ("scanned", 1, 1)
    assert len(await events(session_factory, material)) == 1
    async with session_factory() as session:
        run = await session.get(PriceAlertScanRun, outcome.scan_run_id)
        state = (await session.execute(select(PriceAlertScanState))).scalar_one()
    assert run is not None and "lỗi dựng tin" in (run.last_error or "")
    assert state.watermark_confirmed_at == day.at(0, 4)
