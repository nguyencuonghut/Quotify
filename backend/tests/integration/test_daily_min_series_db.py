"""Điểm giá daily-min của một chuỗi trên PostgreSQL thật."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest
from db_helpers import create_material, create_priced_line
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.daily_min_series import DailyMinPoint, get_daily_min_series

pytestmark = pytest.mark.integration

DEC = date(2026, 12, 1)
START = date(2026, 9, 1)
END = date(2026, 9, 30)


async def _series(
    session_factory: async_sessionmaker[AsyncSession],
    material_id: UUID,
    *,
    delivery_month: date = DEC,
    exclude: tuple[UUID, ...] | list[UUID] = (),
) -> list[DailyMinPoint]:
    async with session_factory() as session:
        return await get_daily_min_series(
            session,
            material_id=material_id,
            delivery_month=delivery_month,
            start=START,
            end=END,
            exclude_line_ids=exclude,
        )


async def test_several_lines_and_suppliers_on_one_day_give_one_lowest_point(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material = await create_material(session_factory)
    day = date(2026, 9, 15)
    await create_priced_line(session_factory, material_id=material, price=27000, received_date=day)
    low_version, low_line = await create_priced_line(
        session_factory, material_id=material, price=26000, received_date=day
    )
    await create_priced_line(session_factory, material_id=material, price=26500, received_date=day)

    points = await _series(session_factory, material)

    assert len(points) == 1
    assert points[0].received_date == day
    assert points[0].price == Decimal("26000.00")
    assert points[0].line_id == low_line
    assert points[0].version_id == low_version


async def test_points_are_ordered_by_date_and_limited_to_the_range(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material = await create_material(session_factory)
    for day, price in [
        (date(2026, 9, 20), 3),
        (date(2026, 9, 10), 1),
        (date(2026, 8, 31), 9),
        (date(2026, 10, 1), 9),
        (date(2026, 9, 1), 2),
        (date(2026, 9, 30), 4),
    ]:
        await create_priced_line(
            session_factory, material_id=material, price=price, received_date=day
        )

    points = await _series(session_factory, material)

    assert [(p.received_date.day, int(p.price)) for p in points] == [
        (1, 2),
        (10, 1),
        (20, 3),
        (30, 4),
    ]


async def test_draft_superseded_and_cancelled_quotes_are_ignored(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material = await create_material(session_factory)
    day = date(2026, 9, 15)
    await create_priced_line(
        session_factory, material_id=material, price=1, received_date=day, status="draft"
    )
    await create_priced_line(
        session_factory, material_id=material, price=2, received_date=day, status="superseded"
    )
    await create_priced_line(
        session_factory, material_id=material, price=3, received_date=day, cancelled=True
    )
    await create_priced_line(session_factory, material_id=material, price=50, received_date=day)

    points = await _series(session_factory, material)

    assert [int(p.price) for p in points] == [50]


async def test_excluding_a_line_recomputes_the_day_and_drops_empty_days(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material = await create_material(session_factory)
    day = date(2026, 9, 15)
    _, bad_line = await create_priced_line(
        session_factory, material_id=material, price=15000, received_date=day
    )
    await create_priced_line(session_factory, material_id=material, price=26000, received_date=day)
    _, only_line = await create_priced_line(
        session_factory, material_id=material, price=100, received_date=date(2026, 9, 16)
    )

    points = await _series(session_factory, material, exclude=[bad_line, only_line])

    assert [(p.received_date, int(p.price)) for p in points] == [(day, 26000)]


async def test_other_materials_and_delivery_months_are_not_mixed_in(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material = await create_material(session_factory)
    other = await create_material(session_factory)
    day = date(2026, 9, 15)
    await create_priced_line(session_factory, material_id=other, price=1, received_date=day)
    await create_priced_line(
        session_factory,
        material_id=material,
        price=2,
        received_date=day,
        delivery_month=date(2027, 1, 1),
    )
    await create_priced_line(session_factory, material_id=material, price=9, received_date=day)

    points = await _series(session_factory, material)

    assert [int(p.price) for p in points] == [9]


async def test_delivery_month_not_on_the_first_still_groups_into_the_month(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material = await create_material(session_factory)
    day = date(2026, 9, 15)
    await create_priced_line(
        session_factory,
        material_id=material,
        price=8,
        received_date=day,
        delivery_month=date(2026, 12, 15),
    )
    await create_priced_line(
        session_factory,
        material_id=material,
        price=7,
        received_date=day,
        delivery_month=date(2026, 12, 1),
    )

    points = await _series(session_factory, material, delivery_month=date(2026, 12, 20))

    assert [int(p.price) for p in points] == [7]


async def test_weekend_received_dates_are_points_and_confirmation_time_is_irrelevant(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from datetime import UTC, datetime

    material = await create_material(session_factory)
    saturday = date(2026, 9, 12)
    await create_priced_line(
        session_factory,
        material_id=material,
        price=5,
        received_date=saturday,
        confirmed_at=datetime(2026, 10, 1, 9, 0, tzinfo=UTC),
    )

    points = await _series(session_factory, material)

    assert [p.received_date for p in points] == [saturday]


async def test_two_lines_confirmed_on_different_days_still_group_by_received_date(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from datetime import UTC, datetime

    material = await create_material(session_factory)
    received = date(2026, 9, 12)
    await create_priced_line(
        session_factory,
        material_id=material,
        price=9,
        received_date=received,
        confirmed_at=datetime(2026, 9, 12, 9, 0, tzinfo=UTC),
    )
    await create_priced_line(
        session_factory,
        material_id=material,
        price=4,
        received_date=received,
        confirmed_at=datetime(2026, 10, 20, 9, 0, tzinfo=UTC),
    )

    points = await _series(session_factory, material)

    assert [(p.received_date, int(p.price)) for p in points] == [(received, 4)]


async def test_a_confirmed_version_without_confirmed_at_is_ignored_like_the_dashboard(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material = await create_material(session_factory)
    day = date(2026, 9, 15)
    await create_priced_line(
        session_factory, material_id=material, price=1, received_date=day, confirmed_at_null=True
    )
    await create_priced_line(session_factory, material_id=material, price=8, received_date=day)

    points = await _series(session_factory, material)

    assert [int(p.price) for p in points] == [8]


async def test_the_converted_vnd_per_kg_price_is_used_not_the_original(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material = await create_material(session_factory)
    await create_priced_line(
        session_factory,
        material_id=material,
        price=1,
        price_converted=26000,
        received_date=date(2026, 9, 15),
    )

    points = await _series(session_factory, material)

    assert [int(p.price) for p in points] == [26000]


async def test_equal_prices_on_one_day_pick_the_earliest_confirmed_line(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from datetime import UTC, datetime

    material = await create_material(session_factory)
    day = date(2026, 9, 15)
    await create_priced_line(
        session_factory,
        material_id=material,
        price=5,
        received_date=day,
        confirmed_at=datetime(2026, 9, 16, tzinfo=UTC),
    )
    early_version, early_line = await create_priced_line(
        session_factory,
        material_id=material,
        price=5,
        received_date=day,
        confirmed_at=datetime(2026, 9, 15, tzinfo=UTC),
    )

    points = await _series(session_factory, material)

    assert [(p.line_id, p.version_id) for p in points] == [(early_line, early_version)]
