"""Cấu hình theo dõi độ mới của giá theo vật tư trên PostgreSQL thật (Telegram 1D, Slice 3)."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from db_helpers import create_material, create_user
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Material, PriceFreshnessMaterial
from app.services.price_alert_material_threshold_service import (
    MaterialNotFoundError,
    MaterialThresholdView,
    PriceAlertMaterialThresholdService,
)

pytestmark = pytest.mark.integration


async def _set(
    session_factory: async_sessionmaker[AsyncSession],
    material_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    watched: bool = True,
    interval: int = 14,
) -> list[dict[str, str]]:
    async with session_factory() as session:
        result = await PriceAlertMaterialThresholdService(session).set_freshness(
            material_id=material_id,
            is_watched=watched,
            expected_interval_days=interval,
            updated_by_id=user_id,
        )
        await session.commit()
        return result.changes


async def _clear(
    session_factory: async_sessionmaker[AsyncSession],
    material_id: uuid.UUID,
) -> list[dict[str, str]]:
    async with session_factory() as session:
        changes = await PriceAlertMaterialThresholdService(session).clear_freshness(
            material_id=material_id,
        )
        await session.commit()
        return changes


async def _row(
    session_factory: async_sessionmaker[AsyncSession],
    material_id: uuid.UUID,
) -> PriceFreshnessMaterial | None:
    async with session_factory() as session:
        return (
            await session.execute(
                select(PriceFreshnessMaterial).where(
                    PriceFreshnessMaterial.material_id == material_id,
                ),
            )
        ).scalar_one_or_none()


async def _item(
    session_factory: async_sessionmaker[AsyncSession],
    material_id: uuid.UUID,
) -> MaterialThresholdView:
    async with session_factory() as session:
        code = (
            await session.execute(select(Material.code).where(Material.id == material_id))
        ).scalar_one()
        page = await PriceAlertMaterialThresholdService(session).list_materials(
            limit=100,
            offset=0,
            search=code,
        )
    return next(item for item in page.items if item.material_id == material_id)


@pytest.mark.asyncio
async def test_set_freshness_saves_the_watch_config_and_lists_it_with_the_material(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material_id = await create_material(session_factory)
    user_id = await create_user(session_factory)

    changes = await _set(session_factory, material_id, user_id)

    assert changes == [
        {
            "field": "is_watched",
            "label": "Theo dõi độ mới của giá",
            "old_value": "chưa cấu hình",
            "new_value": "có",
        },
        {
            "field": "expected_interval_days",
            "label": "Chu kỳ kỳ vọng (ngày)",
            "old_value": "chưa cấu hình",
            "new_value": "14",
        },
    ]
    row = await _row(session_factory, material_id)
    assert row is not None
    assert row.is_watched is True
    assert row.expected_interval_days == 14
    assert row.updated_by_id == user_id
    item = await _item(session_factory, material_id)
    assert item.freshness is not None
    assert (item.freshness.is_watched, item.freshness.expected_interval_days) == (True, 14)


@pytest.mark.asyncio
async def test_material_without_config_lists_no_freshness(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material_id = await create_material(session_factory)

    assert (await _item(session_factory, material_id)).freshness is None


@pytest.mark.asyncio
async def test_set_freshness_twice_updates_the_same_row_and_reports_only_what_changed(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material_id = await create_material(session_factory)
    user_id = await create_user(session_factory)
    await _set(session_factory, material_id, user_id, interval=14)

    changes = await _set(session_factory, material_id, user_id, watched=False, interval=14)

    assert [(c["field"], c["old_value"], c["new_value"]) for c in changes] == [
        ("is_watched", "có", "không"),
    ]
    row = await _row(session_factory, material_id)
    assert row is not None and row.is_watched is False
    assert await _set(session_factory, material_id, user_id, watched=False, interval=14) == []


@pytest.mark.asyncio
async def test_set_freshness_rejects_an_unknown_material_and_a_bad_interval(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await create_user(session_factory)
    material_id = await create_material(session_factory)

    with pytest.raises(MaterialNotFoundError):
        await _set(session_factory, uuid.uuid4(), user_id)
    for bad in (0, 366):
        with pytest.raises(ValueError, match="1 đến 365"):
            await _set(session_factory, material_id, user_id, interval=bad)
    assert await _row(session_factory, material_id) is None


@pytest.mark.asyncio
async def test_clear_freshness_deletes_only_that_materials_row_and_is_idempotent(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await create_user(session_factory)
    target = await create_material(session_factory)
    bystander = await create_material(session_factory)
    await _set(session_factory, target, user_id, interval=7)
    await _set(session_factory, bystander, user_id, interval=30)

    changes = await _clear(session_factory, target)

    assert [c["field"] for c in changes] == ["is_watched", "expected_interval_days"]
    assert changes[0]["new_value"] == "chưa cấu hình"
    assert await _row(session_factory, target) is None
    survivor = await _row(session_factory, bystander)
    assert survivor is not None and survivor.expected_interval_days == 30
    assert await _clear(session_factory, target) == []


@pytest.mark.asyncio
async def test_threshold_and_freshness_settings_do_not_affect_each_other(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await create_user(session_factory)
    material_id = await create_material(session_factory)
    async with session_factory() as session:
        await PriceAlertMaterialThresholdService(session).set_override(
            material_id=material_id,
            light=Decimal("1.00"),
            medium=Decimal("3.00"),
            large=Decimal("6.00"),
            anomaly=None,
            updated_by_id=user_id,
        )
        await session.commit()
    await _set(session_factory, material_id, user_id)

    async with session_factory() as session:
        await PriceAlertMaterialThresholdService(session).clear_override(material_id=material_id)
        await session.commit()
    item = await _item(session_factory, material_id)
    assert item.override is None
    assert item.freshness is not None

    await _clear(session_factory, material_id)
    async with session_factory() as session:
        await PriceAlertMaterialThresholdService(session).set_override(
            material_id=material_id,
            light=Decimal("1.00"),
            medium=Decimal("3.00"),
            large=Decimal("6.00"),
            anomaly=None,
            updated_by_id=user_id,
        )
        await session.commit()
    assert (await _item(session_factory, material_id)).freshness is None


@pytest.mark.asyncio
async def test_search_and_paging_do_not_duplicate_rows_when_both_configs_exist(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await create_user(session_factory)
    material_id = await create_material(session_factory)
    await _set(session_factory, material_id, user_id)
    async with session_factory() as session:
        code = (
            await session.execute(select(Material.code).where(Material.id == material_id))
        ).scalar_one()
        page = await PriceAlertMaterialThresholdService(session).list_materials(
            limit=100,
            offset=0,
            search=code,
        )
    assert page.total == 1
    assert len(page.items) == 1
