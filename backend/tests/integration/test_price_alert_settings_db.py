"""Cấu hình thông báo biến động giá trên PostgreSQL thật: watermark, ràng buộc, khóa ngoại."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from db_helpers import create_confirmed_quote_version, create_material, create_user
from sqlalchemy import delete, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
    PriceAlertMaterialThreshold,
    PriceAlertScannedVersion,
    PriceAlertScanRun,
    PriceAlertScanState,
    PriceAlertSetting,
    User,
    UserAlertPreference,
)
from app.services.price_alert_settings_service import (
    PriceAlertSettingsService,
    PriceAlertSettingsValues,
)

pytestmark = pytest.mark.integration

T0 = datetime(2026, 10, 5, 8, 0, tzinfo=UTC)

DEFAULTS: dict[str, Any] = {
    "is_enabled": False,
    "anomaly_enabled": False,
    "reference_working_days": 7,
    "light_from_percent": Decimal("2.50"),
    "medium_from_percent": Decimal("5.00"),
    "large_over_percent": Decimal("10.00"),
    "anomaly_percent": Decimal("30.00"),
    "anomaly_lookback_days": 30,
    "max_trigger_delay_working_days": 3,
    "staff_lookback_days": 90,
    "dedupe_window_days": 14,
    "immediate_cap_per_scan": 30,
    "digest_hour_local": 8,
    "reference_fallback_days": 30,
}


def _values(**overrides: Any) -> PriceAlertSettingsValues:
    return PriceAlertSettingsValues(**{**DEFAULTS, **overrides})


@pytest.fixture(autouse=True)
async def reset_price_alert_state(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[None]:
    """Hai hàng singleton dùng chung cả phiên test nên đưa về mặc định trước mỗi test."""

    async def reset() -> None:
        async with session_factory() as session:
            await session.execute(
                update(PriceAlertSetting).values(**DEFAULTS, updated_by_id=None),
            )
            await session.execute(
                update(PriceAlertScanState).values(
                    watermark_confirmed_at=None,
                    enabled_since=None,
                    last_digest_local_date=None,
                    last_run_at=None,
                ),
            )
            await session.commit()

    await reset()
    yield
    await reset()


async def _update(
    session_factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
    now: datetime,
    **overrides: Any,
) -> Any:
    async with session_factory() as session:
        result = await PriceAlertSettingsService(session).update_settings(
            values=_values(**overrides),
            updated_by_id=user_id,
            now=now,
        )
        await session.commit()
        return result


async def _scan_state(
    session_factory: async_sessionmaker[AsyncSession],
) -> PriceAlertScanState:
    async with session_factory() as session:
        return (await session.execute(select(PriceAlertScanState))).scalar_one()


async def test_migration_inserts_the_default_rows(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        setting = (await session.execute(select(PriceAlertSetting))).scalar_one()
        scan_state = (await session.execute(select(PriceAlertScanState))).scalar_one()

    assert setting.singleton_key == "default"
    assert setting.is_enabled is False
    assert setting.light_from_percent == Decimal("2.50")
    assert setting.medium_from_percent == Decimal("5.00")
    assert setting.large_over_percent == Decimal("10.00")
    assert setting.anomaly_percent == Decimal("30.00")
    assert (setting.reference_working_days, setting.anomaly_lookback_days) == (7, 30)
    assert (setting.max_trigger_delay_working_days, setting.staff_lookback_days) == (3, 90)
    assert (setting.dedupe_window_days, setting.immediate_cap_per_scan) == (14, 30)
    assert setting.digest_hour_local == 8
    assert scan_state.watermark_confirmed_at is None
    assert scan_state.enabled_since is None
    assert scan_state.last_run_at is None


async def test_enabling_sets_watermark_and_enabled_since_to_the_enable_moment(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await create_user(session_factory)

    result = await _update(session_factory, user_id, T0, is_enabled=True)

    assert [change["field"] for change in result.changes] == ["is_enabled"]
    scan_state = await _scan_state(session_factory)
    assert scan_state.watermark_confirmed_at == T0
    assert scan_state.enabled_since == T0
    async with session_factory() as session:
        setting = (await session.execute(select(PriceAlertSetting))).scalar_one()
    assert setting.is_enabled is True
    assert setting.updated_by_id == user_id


async def test_staying_enabled_keeps_the_original_watermark(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await create_user(session_factory)
    await _update(session_factory, user_id, T0, is_enabled=True)

    result = await _update(
        session_factory,
        user_id,
        T0 + timedelta(hours=1),
        is_enabled=True,
        medium_from_percent=Decimal("6.00"),
    )

    assert [change["field"] for change in result.changes] == ["medium_from_percent"]
    scan_state = await _scan_state(session_factory)
    assert scan_state.watermark_confirmed_at == T0
    assert scan_state.enabled_since == T0


async def test_disabling_then_enabling_again_resets_the_watermark(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await create_user(session_factory)
    await _update(session_factory, user_id, T0, is_enabled=True)
    await _update(session_factory, user_id, T0 + timedelta(days=1), is_enabled=False)
    after_disable = await _scan_state(session_factory)
    assert after_disable.watermark_confirmed_at == T0

    later = T0 + timedelta(days=30)
    await _update(session_factory, user_id, later, is_enabled=True)

    scan_state = await _scan_state(session_factory)
    assert scan_state.watermark_confirmed_at == later
    assert scan_state.enabled_since == later


async def test_update_without_changes_reports_none_and_keeps_the_last_editor(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await create_user(session_factory)

    result = await _update(session_factory, user_id, T0)

    assert result.changes == []
    async with session_factory() as session:
        setting = (await session.execute(select(PriceAlertSetting))).scalar_one()
    assert setting.updated_by_id is None


async def test_changes_use_string_values_for_every_type(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await create_user(session_factory)

    result = await _update(
        session_factory,
        user_id,
        T0,
        is_enabled=True,
        light_from_percent=Decimal("3"),
        digest_hour_local=9,
    )

    changes = {change["field"]: change for change in result.changes}
    assert changes["is_enabled"]["old_value"] == "false"
    assert changes["is_enabled"]["new_value"] == "true"
    assert changes["light_from_percent"]["old_value"] == "2.50"
    assert changes["light_from_percent"]["new_value"] == "3.00"
    assert changes["digest_hour_local"]["old_value"] == "8"
    assert changes["digest_hour_local"]["new_value"] == "9"
    assert all(isinstance(value, str) for change in result.changes for value in change.values())


async def test_unordered_thresholds_raise_before_anything_is_written(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await create_user(session_factory)

    with pytest.raises(ValueError, match="tăng dần"):
        await _update(
            session_factory,
            user_id,
            T0,
            is_enabled=True,
            light_from_percent=Decimal("6.00"),
        )

    scan_state = await _scan_state(session_factory)
    assert scan_state.watermark_confirmed_at is None
    async with session_factory() as session:
        setting = (await session.execute(select(PriceAlertSetting))).scalar_one()
    assert setting.is_enabled is False


async def test_two_concurrent_enables_set_the_watermark_only_once(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Dòng cấu hình bị khóa (FOR UPDATE): lần bật thứ hai thấy cờ đã bật nên không đặt lại mốc."""
    user_id = await create_user(session_factory)
    first_has_written = asyncio.Event()
    first_may_commit = asyncio.Event()

    async def first() -> None:
        async with session_factory() as session:
            await PriceAlertSettingsService(session).update_settings(
                values=_values(is_enabled=True),
                updated_by_id=user_id,
                now=T0,
            )
            first_has_written.set()
            await first_may_commit.wait()
            await session.commit()

    async def second() -> None:
        await first_has_written.wait()
        async with session_factory() as session:
            await PriceAlertSettingsService(session).update_settings(
                values=_values(is_enabled=True),
                updated_by_id=user_id,
                now=T0 + timedelta(minutes=5),
            )
            await session.commit()

    first_task = asyncio.create_task(first())
    second_task = asyncio.create_task(second())
    await first_has_written.wait()
    await asyncio.sleep(0.5)
    assert not second_task.done(), "lần bật thứ hai phải chờ khóa dòng của lần đầu"
    first_may_commit.set()
    await asyncio.wait_for(asyncio.gather(first_task, second_task), timeout=10)

    scan_state = await _scan_state(session_factory)
    assert scan_state.watermark_confirmed_at == T0
    assert scan_state.enabled_since == T0


@pytest.mark.parametrize(
    "overrides",
    [
        {"light_from_percent": Decimal("6.00")},
        {"medium_from_percent": Decimal("10.00")},
        {"large_over_percent": Decimal("30.00")},
        {"anomaly_percent": Decimal("10.00")},
        {"light_from_percent": Decimal("0")},
        {"reference_working_days": 0},
        {"reference_working_days": 31},
        {"anomaly_lookback_days": 366},
        {"max_trigger_delay_working_days": 31},
        {"staff_lookback_days": 0},
        {"dedupe_window_days": 91},
        {"immediate_cap_per_scan": 501},
        {"digest_hour_local": 24},
        {"reference_fallback_days": 366},
        {"reference_fallback_days": -1},
    ],
)
async def test_settings_check_constraints_reject_invalid_rows(
    session_factory: async_sessionmaker[AsyncSession],
    overrides: dict[str, Any],
) -> None:
    async with session_factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(update(PriceAlertSetting).values(**overrides))
        await session.rollback()


async def test_second_singleton_row_is_rejected(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        session.add(PriceAlertSetting(singleton_key="default"))
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()
    async with session_factory() as session:
        session.add(PriceAlertSetting(singleton_key="other"))
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()
    async with session_factory() as session:
        session.add(PriceAlertScanState(singleton_key="default"))
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()


@pytest.mark.parametrize(
    "columns",
    [
        {"light_from_percent": Decimal("2.5")},
        {
            "light_from_percent": Decimal("2.5"),
            "medium_from_percent": Decimal("5"),
            "large_over_percent": None,
        },
        {
            "light_from_percent": Decimal("5"),
            "medium_from_percent": Decimal("2.5"),
            "large_over_percent": Decimal("10"),
        },
        {
            "light_from_percent": Decimal("2.5"),
            "medium_from_percent": Decimal("5"),
            "large_over_percent": Decimal("10"),
            "anomaly_percent": Decimal("10"),
        },
        {
            "light_from_percent": Decimal("0"),
            "medium_from_percent": Decimal("5"),
            "large_over_percent": Decimal("10"),
        },
    ],
)
async def test_material_threshold_check_constraints_reject_invalid_rows(
    session_factory: async_sessionmaker[AsyncSession],
    columns: dict[str, Decimal | None],
) -> None:
    material_id = await create_material(session_factory)
    async with session_factory() as session:
        session.add(PriceAlertMaterialThreshold(material_id=material_id, **columns))
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()


async def test_material_threshold_accepts_a_full_override_or_only_an_anomaly_override(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    full_material = await create_material(session_factory)
    anomaly_only_material = await create_material(session_factory)
    async with session_factory() as session:
        session.add_all(
            [
                PriceAlertMaterialThreshold(
                    material_id=full_material,
                    light_from_percent=Decimal("1"),
                    medium_from_percent=Decimal("3"),
                    large_over_percent=Decimal("6"),
                    anomaly_percent=Decimal("20"),
                ),
                PriceAlertMaterialThreshold(
                    material_id=anomaly_only_material,
                    anomaly_percent=Decimal("45"),
                ),
            ],
        )
        await session.commit()


async def test_user_alert_preference_rejects_an_unknown_level(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await create_user(session_factory)
    async with session_factory() as session:
        session.add(UserAlertPreference(user_id=user_id, min_level="critical"))
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()


async def test_user_alert_preference_defaults(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await create_user(session_factory)
    async with session_factory() as session:
        session.add(UserAlertPreference(user_id=user_id))
        await session.commit()
    async with session_factory() as session:
        preference = await session.get(UserAlertPreference, user_id)
    assert preference is not None
    assert preference.is_enabled is True
    assert preference.min_level is None
    assert preference.admin_receive_all is False


async def test_deleting_a_material_removes_its_threshold_override(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material_id = await create_material(session_factory)
    async with session_factory() as session:
        session.add(
            PriceAlertMaterialThreshold(
                material_id=material_id,
                light_from_percent=Decimal("1"),
                medium_from_percent=Decimal("3"),
                large_over_percent=Decimal("6"),
            ),
        )
        await session.commit()

    async with session_factory() as session:
        await session.execute(text("DELETE FROM materials WHERE id = :id"), {"id": material_id})
        await session.commit()

    async with session_factory() as session:
        assert await session.get(PriceAlertMaterialThreshold, material_id) is None


async def test_deleting_a_user_clears_the_editor_and_removes_preferences(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await create_user(session_factory)
    await _update(session_factory, user_id, T0, is_enabled=True)
    async with session_factory() as session:
        session.add(UserAlertPreference(user_id=user_id))
        await session.commit()

    async with session_factory() as session:
        await session.execute(delete(User).where(User.id == user_id))
        await session.commit()

    async with session_factory() as session:
        setting = (await session.execute(select(PriceAlertSetting))).scalar_one()
        assert setting.updated_by_id is None
        assert await session.get(UserAlertPreference, user_id) is None


async def test_scanned_versions_cascade_with_the_version_and_detach_from_the_run(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    version_to_delete = await create_confirmed_quote_version(session_factory)
    version_to_keep = await create_confirmed_quote_version(session_factory)
    async with session_factory() as session:
        run = PriceAlertScanRun()
        session.add(run)
        await session.flush()
        session.add_all(
            [
                PriceAlertScannedVersion(
                    version_id=version_to_delete,
                    is_trigger_source=True,
                    trigger_delay_working_days=0,
                    scan_run_id=run.id,
                ),
                PriceAlertScannedVersion(
                    version_id=version_to_keep,
                    is_trigger_source=False,
                    scan_run_id=run.id,
                ),
            ],
        )
        await session.commit()
        run_id = run.id

    async with session_factory() as session:
        await session.execute(
            text("DELETE FROM quote_versions WHERE id = :id"),
            {"id": version_to_delete},
        )
        await session.commit()
    async with session_factory() as session:
        assert await session.get(PriceAlertScannedVersion, version_to_delete) is None
        assert await session.get(PriceAlertScannedVersion, version_to_keep) is not None

    async with session_factory() as session:
        await session.execute(
            delete(PriceAlertScanRun).where(PriceAlertScanRun.id == run_id),
        )
        await session.commit()
    async with session_factory() as session:
        kept = await session.get(PriceAlertScannedVersion, version_to_keep)
        assert kept is not None
        assert kept.scan_run_id is None
        assert kept.is_trigger_source is False
        assert kept.trigger_delay_working_days is None


async def test_scan_run_counters_default_to_zero(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        run = PriceAlertScanRun()
        session.add(run)
        await session.commit()
        run_id = run.id

    async with session_factory() as session:
        stored = await session.get(PriceAlertScanRun, run_id)
    assert stored is not None
    assert stored.started_at is not None
    assert stored.finished_at is None
    assert (stored.versions_scanned, stored.events_created, stored.error_count) == (0, 0, 0)
    assert (stored.messages_created, stored.messages_sent) == (0, 0)
    assert stored.last_error is None
