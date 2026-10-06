"""Độ mới của giá theo vật tư trên PostgreSQL thật (Telegram 1D, Slice 1)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from db_helpers import (
    create_material,
    create_priced_line,
    create_quote_shell,
    create_user,
    create_version_with_lines,
)
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Material, PriceFreshnessMaterial
from app.schemas.quotify_material_freshness import QuotifyMaterialFreshnessResponse
from app.services.quotify_material_freshness_service import QuotifyMaterialFreshnessService

pytestmark = pytest.mark.integration

# Tuần quá khứ cố định (thứ Hai) để dữ liệu của các test khác (gần hôm nay) không lẫn vào.
WEEK = date(2025, 3, 3)
SUNDAY = WEEK + timedelta(days=6)
TODAY = date(2026, 10, 6)


# Dọn CẢ bảng cấu hình theo dõi: an toàn khi chưa test nào khác dùng bảng này. Các slice sau (API
# cấu hình, lệnh nạp mặc định) phải dùng vật tư riêng của từng test hoặc cách dọn riêng.
@pytest.fixture(autouse=True)
async def clean_watch_list(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[None]:
    async def clean() -> None:
        async with session_factory() as session:
            await session.execute(delete(PriceFreshnessMaterial))
            await session.commit()

    await clean()
    yield
    await clean()


async def _watch(
    session_factory: async_sessionmaker[AsyncSession],
    material_id: uuid.UUID,
    interval: int,
    *,
    watched: bool = True,
) -> None:
    async with session_factory() as session:
        session.add(
            PriceFreshnessMaterial(
                material_id=material_id,
                is_watched=watched,
                expected_interval_days=interval,
            ),
        )
        await session.commit()


async def _table(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    week_start: date = WEEK,
    today: date = TODAY,
) -> dict[str, Any]:
    async with session_factory() as session:
        return await QuotifyMaterialFreshnessService(session).get_material_freshness(
            week_start=week_start,
            today=today,
        )


def _rows(data: dict[str, Any]) -> dict[uuid.UUID, dict[str, Any]]:
    return {item["material_id"]: item for item in data["items"]}


@pytest.mark.asyncio
async def test_week_table_lists_updated_and_overdue_materials_and_skips_idle_unwatched(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await create_user(session_factory)
    updated = await create_material(session_factory, name="Vật tư có giá mới")
    overdue = await create_material(session_factory, name="Vật tư quá hạn")
    idle = await create_material(session_factory, name="Vật tư không theo dõi")
    await _watch(session_factory, updated, 7)
    await _watch(session_factory, overdue, 14)
    # Hai phiếu hợp lệ trong tuần của hai nhà cung cấp khác nhau.
    await create_priced_line(
        session_factory,
        material_id=updated,
        price=100,
        received_date=WEEK + timedelta(days=1),
        created_by_id=user_id,
    )
    await create_priced_line(
        session_factory,
        material_id=updated,
        price=110,
        received_date=WEEK + timedelta(days=3),
        created_by_id=user_id,
    )
    # Lần cuối nhận giá cách Chủ nhật của tuần 20 ngày, chu kỳ 14 ngày.
    await create_priced_line(
        session_factory,
        material_id=overdue,
        price=90,
        received_date=SUNDAY - timedelta(days=20),
        created_by_id=user_id,
    )

    data = await _table(session_factory)

    rows = _rows(data)
    assert rows[updated]["update_count"] == 2
    assert rows[updated]["supplier_count"] == 2
    assert rows[updated]["status"] == "updated"
    assert rows[overdue]["update_count"] == 0
    assert rows[overdue]["age_days"] == 20
    assert rows[overdue]["status"] == "overdue"
    assert idle not in rows


@pytest.mark.asyncio
async def test_update_count_counts_versions_not_lines(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material = await create_material(session_factory)
    await _watch(session_factory, material, 7)
    quote_id = await create_quote_shell(session_factory)
    # Một phiên bản có hai dòng cùng vật tư (hai kỳ giao hàng) vẫn là MỘT lần cập nhật.
    await create_version_with_lines(
        session_factory,
        quote_id=quote_id,
        version_number=1,
        received_date=WEEK + timedelta(days=2),
        lines=[
            (material, 100, date(2025, 4, 1)),
            (material, 105, date(2025, 5, 1)),
        ],
    )

    row = _rows(await _table(session_factory))[material]

    assert row["update_count"] == 1
    assert row["supplier_count"] == 1


@pytest.mark.asyncio
async def test_draft_cancelled_unconfirmed_and_superseded_versions_are_not_updates(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material = await create_material(session_factory)
    await _watch(session_factory, material, 7)
    received = WEEK + timedelta(days=1)
    await create_priced_line(
        session_factory, material_id=material, price=1, received_date=received, status="draft"
    )
    await create_priced_line(
        session_factory, material_id=material, price=1, received_date=received, cancelled=True
    )
    await create_priced_line(
        session_factory,
        material_id=material,
        price=1,
        received_date=received,
        confirmed_at_null=True,
    )
    # Phiếu được sửa: bản cũ thành `superseded`, chỉ bản mới được đếm (không đếm đôi).
    quote_id = await create_quote_shell(session_factory)
    old_version, _ = await create_version_with_lines(
        session_factory,
        quote_id=quote_id,
        version_number=1,
        received_date=received,
        lines=[(material, 100, date(2025, 4, 1))],
    )
    await create_version_with_lines(
        session_factory,
        quote_id=quote_id,
        version_number=2,
        received_date=received,
        lines=[(material, 101, date(2025, 4, 1))],
        supersedes_version_id=old_version,
    )

    row = _rows(await _table(session_factory))[material]

    assert row["update_count"] == 1


@pytest.mark.asyncio
async def test_week_boundaries_follow_received_date_not_entry_time(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material = await create_material(session_factory)
    await _watch(session_factory, material, 7)
    # Thứ Hai và Chủ nhật của tuần thuộc tuần; Chủ nhật trước đó và thứ Hai kế tiếp thì không.
    for received in (
        WEEK,
        SUNDAY,
        WEEK - timedelta(days=1),
        SUNDAY + timedelta(days=1),
    ):
        await create_priced_line(
            session_factory,
            material_id=material,
            price=1,
            received_date=received,
        )
    # Phiếu nhập muộn: nhận trong tuần nhưng chốt (nhập) sau đó nhiều tháng vẫn tính vào tuần nhận.
    await create_priced_line(
        session_factory,
        material_id=material,
        price=1,
        received_date=WEEK + timedelta(days=3),
        confirmed_at=datetime(2025, 9, 1, 8, 0, tzinfo=UTC),
    )

    row = _rows(await _table(session_factory))[material]

    assert row["update_count"] == 3


@pytest.mark.asyncio
async def test_past_week_is_evaluated_at_its_sunday_and_ignores_later_receipts(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material = await create_material(session_factory)
    await _watch(session_factory, material, 7)
    await create_priced_line(
        session_factory,
        material_id=material,
        price=1,
        received_date=SUNDAY - timedelta(days=10),
    )
    # Phiếu nhận SAU Chủ nhật của tuần không được dùng làm "ngày nhận gần nhất" của tuần đó.
    await create_priced_line(
        session_factory,
        material_id=material,
        price=1,
        received_date=SUNDAY + timedelta(days=3),
    )

    data = await _table(session_factory)
    row = _rows(data)[material]

    assert data["as_of_date"] == SUNDAY
    assert row["last_received_date"] == SUNDAY - timedelta(days=10)
    assert row["age_days"] == 10
    assert row["status"] == "overdue"


@pytest.mark.asyncio
async def test_current_week_is_evaluated_today_and_future_receipts_do_not_count(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material = await create_material(session_factory)
    await _watch(session_factory, material, 7)
    week = date(2026, 10, 5)  # tuần chứa TODAY (thứ Ba 06/10)
    await create_priced_line(
        session_factory,
        material_id=material,
        price=1,
        received_date=date(2026, 10, 1),
    )
    # Ngày nhận ở tương lai (thứ Sáu 09/10) chưa tới: không tính, tuổi không âm.
    await create_priced_line(
        session_factory,
        material_id=material,
        price=1,
        received_date=date(2026, 10, 9),
    )

    data = await _table(session_factory, week_start=week, today=TODAY)
    row = _rows(data)[material]

    assert data["as_of_date"] == TODAY
    assert row["update_count"] == 0
    assert row["last_received_date"] == date(2026, 10, 1)
    assert row["age_days"] == 5
    assert row["status"] == "on_time"


@pytest.mark.asyncio
async def test_watched_material_without_any_price_is_never(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material = await create_material(session_factory)
    await _watch(session_factory, material, 14)

    row = _rows(await _table(session_factory))[material]

    assert row["status"] == "never"
    assert row["last_received_date"] is None
    assert row["age_days"] is None
    assert row["update_count"] == 0
    assert row["last_enterer_id"] is None
    assert row["last_enterer_label"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("age", "expected"),
    [(14, "on_time"), (15, "overdue")],
)
async def test_age_equal_to_interval_is_still_on_time(
    session_factory: async_sessionmaker[AsyncSession],
    age: int,
    expected: str,
) -> None:
    material = await create_material(session_factory)
    await _watch(session_factory, material, 14)
    await create_priced_line(
        session_factory,
        material_id=material,
        price=1,
        received_date=SUNDAY - timedelta(days=age),
    )

    row = _rows(await _table(session_factory))[material]

    assert row["age_days"] == age
    assert row["status"] == expected


@pytest.mark.asyncio
async def test_inactive_material_is_hidden_even_when_watched_and_updated(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material = await create_material(session_factory)
    await _watch(session_factory, material, 7)
    await create_priced_line(
        session_factory,
        material_id=material,
        price=1,
        received_date=WEEK + timedelta(days=1),
    )
    async with session_factory() as session:
        await session.execute(
            update(Material).where(Material.id == material).values(status="inactive")
        )
        await session.commit()

    assert material not in _rows(await _table(session_factory))


@pytest.mark.asyncio
async def test_unwatched_material_with_update_is_listed_without_interval(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    never_configured = await create_material(session_factory)
    turned_off = await create_material(session_factory)
    await _watch(session_factory, turned_off, 7, watched=False)
    for material in (never_configured, turned_off):
        await create_priced_line(
            session_factory,
            material_id=material,
            price=1,
            received_date=WEEK + timedelta(days=1),
        )

    rows = _rows(await _table(session_factory))

    for material in (never_configured, turned_off):
        assert rows[material]["is_watched"] is False
        assert rows[material]["expected_interval_days"] is None
        assert rows[material]["status"] == "updated"
        assert rows[material]["update_count"] == 1


@pytest.mark.asyncio
async def test_unwatched_idle_material_that_was_turned_off_is_not_listed(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material = await create_material(session_factory)
    await _watch(session_factory, material, 7, watched=False)

    assert material not in _rows(await _table(session_factory))


@pytest.mark.asyncio
async def test_summary_counts_watched_materials_and_adds_up(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # Tuần rất xa để chỉ dữ liệu của test này nằm trong tuần.
    week = date(2019, 2, 4)
    sunday = week + timedelta(days=6)
    updated, on_time, overdue, never, unwatched = [
        await create_material(session_factory) for _ in range(5)
    ]
    for material in (updated, on_time, overdue, never):
        await _watch(session_factory, material, 7)
    await create_priced_line(
        session_factory, material_id=updated, price=1, received_date=week + timedelta(days=2)
    )
    await create_priced_line(
        session_factory, material_id=on_time, price=1, received_date=sunday - timedelta(days=7)
    )
    await create_priced_line(
        session_factory, material_id=overdue, price=1, received_date=sunday - timedelta(days=8)
    )
    await create_priced_line(
        session_factory, material_id=unwatched, price=1, received_date=week + timedelta(days=1)
    )

    data = await _table(session_factory, week_start=week)

    assert data["summary"] == {
        "watched_count": 4,
        "updated_count": 1,
        "on_time_count": 1,
        "overdue_count": 2,  # quá hạn và chưa từng có giá
        "unwatched_updated_count": 1,
    }
    summary = data["summary"]
    assert summary["watched_count"] == (
        summary["updated_count"] + summary["on_time_count"] + summary["overdue_count"]
    )


@pytest.mark.asyncio
async def test_last_enterer_is_the_creator_of_the_latest_received_version(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    older_user = await create_user(session_factory, full_name="Người Nhập Cũ")
    newer_user = await create_user(session_factory, full_name="Người Nhập Mới")
    material = await create_material(session_factory)
    await _watch(session_factory, material, 7)
    await create_priced_line(
        session_factory,
        material_id=material,
        price=1,
        received_date=WEEK + timedelta(days=1),
        created_by_id=older_user,
    )
    await create_priced_line(
        session_factory,
        material_id=material,
        price=1,
        received_date=WEEK + timedelta(days=4),
        created_by_id=newer_user,
    )

    row = _rows(await _table(session_factory))[material]

    assert row["last_received_date"] == WEEK + timedelta(days=4)
    assert row["last_enterer_id"] == newer_user
    assert row["last_enterer_label"] == "Người Nhập Mới"


@pytest.mark.asyncio
async def test_last_enterer_breaks_same_day_ties_by_latest_confirmation(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # Nhiều phiên bản cùng ngày nhận: id là UUID ngẫu nhiên nên chỉ `confirmed_at` mới quyết
    # định đúng người; thứ tự tạo bị xáo để không trùng thứ tự chốt.
    users = [await create_user(session_factory, full_name=f"Người chốt {i}") for i in range(6)]
    material = await create_material(session_factory)
    await _watch(session_factory, material, 7)
    received = WEEK + timedelta(days=2)
    for hour, user_id in zip((10, 7, 12, 9, 8, 11), users, strict=True):
        await create_priced_line(
            session_factory,
            material_id=material,
            price=1,
            received_date=received,
            created_by_id=user_id,
            confirmed_at=datetime(2025, 3, 5, hour, 0, tzinfo=UTC),
        )

    row = _rows(await _table(session_factory))[material]

    assert row["last_enterer_id"] == users[2]  # chốt lúc 12:00, muộn nhất


@pytest.mark.asyncio
async def test_future_week_has_no_updates_and_is_evaluated_today(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material = await create_material(session_factory)
    await _watch(session_factory, material, 7)
    await create_priced_line(
        session_factory,
        material_id=material,
        price=1,
        received_date=TODAY - timedelta(days=3),
    )

    data = await _table(session_factory, week_start=date(2026, 12, 7), today=TODAY)
    row = _rows(data)[material]

    assert data["week_start"] == date(2026, 12, 7)
    assert data["as_of_date"] == TODAY
    assert row["update_count"] == 0
    assert row["age_days"] == 3
    assert row["status"] == "on_time"


@pytest.mark.asyncio
async def test_week_start_in_the_middle_of_the_week_is_normalized_to_monday(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    data = await _table(session_factory, week_start=date(2025, 3, 6))  # thứ Năm

    assert data["week_start"] == WEEK
    assert data["week_end"] == SUNDAY


@pytest.mark.asyncio
async def test_real_service_output_is_a_valid_api_response(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await create_user(session_factory)
    material = await create_material(session_factory)
    never = await create_material(session_factory)
    await _watch(session_factory, material, 7)
    await _watch(session_factory, never, 7)
    await create_priced_line(
        session_factory,
        material_id=material,
        price=1,
        received_date=WEEK + timedelta(days=1),
        created_by_id=user_id,
    )

    data = await _table(session_factory)
    response = QuotifyMaterialFreshnessResponse.model_validate(data)

    by_id = {item.material_id: item for item in response.items}
    assert by_id[material].status == "updated"
    assert by_id[never].status == "never"
    assert response.week_start == WEEK
