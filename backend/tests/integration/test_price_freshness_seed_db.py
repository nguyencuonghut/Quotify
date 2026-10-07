"""Lệnh nạp danh sách theo dõi mặc định từ dữ liệu thật (Telegram 1D, Slice 4)."""

from __future__ import annotations

import csv
import io
import uuid
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from db_helpers import (
    create_material,
    create_priced_line,
    create_quote_shell,
    create_version_with_lines,
)
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Material, PriceFreshnessMaterial
from app.price_freshness_seed import (
    Suggestion,
    apply_suggestions,
    compute_suggestions,
    run,
    suggest_interval,
)

pytestmark = pytest.mark.integration

TODAY = date(2026, 10, 1)


async def _days(
    session_factory: async_sessionmaker[AsyncSession],
    material_id: uuid.UUID,
    offsets: list[int],
    **kwargs: object,
) -> None:
    """Mỗi mốc `offsets` (số ngày trước TODAY) là một phiếu hợp lệ của vật tư."""
    for offset in offsets:
        await create_priced_line(
            session_factory,
            material_id=material_id,
            price=1,
            received_date=TODAY - timedelta(days=offset),
            **kwargs,  # type: ignore[arg-type]
        )


async def _suggest(
    session_factory: async_sessionmaker[AsyncSession],
    **kwargs: int,
) -> dict[uuid.UUID, Suggestion]:
    async with session_factory() as session:
        found = await compute_suggestions(session, today=TODAY, **kwargs)
    return {item.material_id: item for item in found}


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


@pytest.mark.parametrize(
    ("gap", "interval"),
    [
        ("0.5", 7),
        ("5.0", 7),
        ("5.01", 14),
        ("12.0", 14),
        ("12.01", 30),
        ("90", 30),
    ],
)
def test_suggest_interval_uses_the_three_tiers(gap: str, interval: int) -> None:
    assert suggest_interval(Decimal(gap)) == interval


@pytest.mark.asyncio
async def test_suggests_materials_with_at_least_three_update_days_and_a_tier(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    frequent = await create_material(session_factory)
    rare = await create_material(session_factory)
    inactive = await create_material(session_factory)
    await _days(session_factory, frequent, [1, 4, 7, 10])  # cách đều 3 ngày
    await _days(session_factory, rare, [2, 30])  # chỉ 2 ngày
    await _days(session_factory, inactive, [1, 4, 7])
    async with session_factory() as session:
        await session.execute(
            update(Material).where(Material.id == inactive).values(status="inactive")
        )
        await session.commit()

    found = await _suggest(session_factory)

    assert found[frequent].interval_days == 7
    assert found[frequent].update_days == 4
    assert found[frequent].mean_gap_days == Decimal("3")
    assert found[frequent].last_received_date == TODAY - timedelta(days=1)
    assert rare not in found
    assert inactive not in found


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("offsets", "interval"),
    [([1, 7, 13], 14), ([1, 14, 27], 30), ([1, 6, 11], 7), ([1, 6, 12], 14), ([1, 5, 9], 7)],
)
async def test_interval_follows_the_mean_gap_between_update_days(
    session_factory: async_sessionmaker[AsyncSession],
    offsets: list[int],
    interval: int,
) -> None:
    material = await create_material(session_factory)
    await _days(session_factory, material, offsets)

    assert (await _suggest(session_factory))[material].interval_days == interval


@pytest.mark.asyncio
async def test_only_valid_distinct_days_inside_the_window_count(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material = await create_material(session_factory)
    await _days(session_factory, material, [1, 2])  # hai ngày hợp lệ
    await _days(session_factory, material, [3], status="draft")
    await _days(session_factory, material, [4], cancelled=True)
    await _days(session_factory, material, [5], confirmed_at_null=True)
    await _days(session_factory, material, [100, 120])  # ngoài cửa sổ 90 ngày
    quote_id = await create_quote_shell(session_factory)
    old, _ = await create_version_with_lines(
        session_factory,
        quote_id=quote_id,
        version_number=1,
        received_date=TODAY - timedelta(days=6),
        lines=[(material, 1, date(2026, 12, 1))],
    )
    await create_version_with_lines(
        session_factory,
        quote_id=quote_id,
        version_number=2,
        received_date=TODAY - timedelta(days=7),
        lines=[(material, 1, date(2026, 12, 1))],
        supersedes_version_id=old,
    )

    # Hai ngày đầu + ngày 7 (bản sửa còn hiệu lực; bản cũ ngày 6 đã bị thay) = 3 ngày.
    assert (await _suggest(session_factory))[material].update_days == 3
    assert material not in await _suggest(session_factory, min_days=4)
    assert (await _suggest(session_factory, window_days=200))[material].update_days == 5


@pytest.mark.asyncio
async def test_many_versions_on_one_day_count_as_one_update_day(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material = await create_material(session_factory)
    await _days(session_factory, material, [1, 1, 1, 1])
    await _days(session_factory, material, [4, 8])

    assert (await _suggest(session_factory))[material].update_days == 3


@pytest.mark.asyncio
async def test_apply_inserts_once_and_never_overwrites_a_managers_choice(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    fresh = await create_material(session_factory)
    edited = await create_material(session_factory)
    turned_off = await create_material(session_factory)
    for material in (fresh, edited, turned_off):
        await _days(session_factory, material, [1, 4, 7])
    async with session_factory() as session:
        session.add_all(
            [
                PriceFreshnessMaterial(
                    material_id=edited, is_watched=True, expected_interval_days=3
                ),
                PriceFreshnessMaterial(
                    material_id=turned_off, is_watched=False, expected_interval_days=30
                ),
            ],
        )
        await session.commit()
    mine = [
        s
        for s in (await _suggest(session_factory)).values()
        if s.material_id in {fresh, edited, turned_off}
    ]

    async with session_factory() as session:
        inserted = await apply_suggestions(session, mine)
        await session.commit()
    async with session_factory() as session:
        again = await apply_suggestions(session, mine)
        await session.commit()

    assert inserted == 1
    assert again == 0
    created = await _row(session_factory, fresh)
    assert created is not None
    assert (created.is_watched, created.expected_interval_days, created.updated_by_id) == (
        True,
        7,
        None,
    )
    kept = await _row(session_factory, edited)
    assert kept is not None and (kept.is_watched, kept.expected_interval_days) == (True, 3)
    off = await _row(session_factory, turned_off)
    assert off is not None and (off.is_watched, off.expected_interval_days) == (False, 30)


@pytest.mark.asyncio
async def test_run_is_a_dry_run_by_default_and_writes_a_reviewable_csv(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    material = await create_material(session_factory, name="Vật tư thử CSV")
    await _days(session_factory, material, [1, 4, 7])
    out = io.StringIO()
    csv_path = tmp_path / "proposal.csv"

    code = await run(
        session_factory,
        apply=False,
        min_days=3,
        window_days=90,
        today=TODAY,
        csv_path=csv_path,
        out=out,
    )

    assert code == 0
    assert await _row(session_factory, material) is None
    assert "dry-run" in out.getvalue().lower()
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    mine = [r for r in rows if r["material_name"] == "Vật tư thử CSV"]
    assert mine and mine[0]["interval_days"] == "7" and mine[0]["update_days"] == "3"


@pytest.mark.asyncio
async def test_run_with_apply_saves_the_rows(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material = await create_material(session_factory)
    await _days(session_factory, material, [1, 4, 7])
    out = io.StringIO()

    code = await run(
        session_factory,
        apply=True,
        min_days=3,
        window_days=90,
        today=TODAY,
        csv_path=None,
        out=out,
    )

    assert code == 0
    saved = await _row(session_factory, material)
    assert saved is not None and saved.expected_interval_days == 7
    # `run(apply=True)` nạp cho MỌI vật tư đủ điều kiện trong DB dùng chung của phiên test: dọn hết
    # để các test sau không thấy hàng cấu hình thừa.
    async with session_factory() as session:
        await session.execute(delete(PriceFreshnessMaterial))
        await session.commit()
    assert "đã nạp" in out.getvalue().lower()


@pytest.mark.asyncio
async def test_window_includes_its_first_day_and_excludes_the_day_before_and_the_future(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material = await create_material(session_factory)
    # Cửa sổ 90 ngày gồm 90 ngày, tính cả hôm nay: ngày TODAY-89 vào, TODAY-90 không vào.
    await _days(session_factory, material, [89, 90, 0])
    await create_priced_line(
        session_factory,
        material_id=material,
        price=1,
        received_date=TODAY + timedelta(days=2),
    )

    assert (await _suggest(session_factory, min_days=2))[material].update_days == 2


@pytest.mark.asyncio
async def test_a_mean_gap_of_exactly_twelve_days_is_still_the_14_day_tier(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material = await create_material(session_factory)
    await _days(session_factory, material, [1, 13, 25])  # 24 ngày chia 2 khoảng = 12,0

    found = (await _suggest(session_factory))[material]

    assert found.mean_gap_days == Decimal("12")
    assert found.interval_days == 14


@pytest.mark.asyncio
async def test_csv_cells_that_look_like_formulas_are_neutralised(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    material = await create_material(session_factory, name="=HYPERLINK(1)")
    await _days(session_factory, material, [1, 4, 7])
    csv_path = tmp_path / "proposal.csv"

    await run(
        session_factory,
        apply=False,
        min_days=3,
        window_days=90,
        today=TODAY,
        csv_path=csv_path,
        out=io.StringIO(),
    )

    names = [r["material_name"] for r in csv.DictReader(csv_path.open(encoding="utf-8"))]
    assert "'=HYPERLINK(1)" in names
    assert "=HYPERLINK(1)" not in names
