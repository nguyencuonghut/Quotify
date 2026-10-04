"""Ngưỡng theo vật tư và tùy chọn cá nhân trên PostgreSQL thật."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from decimal import Decimal

import pytest
from db_helpers import create_material, create_user
from sqlalchemy import delete, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
    Material,
    PriceAlertMaterialThreshold,
    PriceAlertSetting,
    Role,
    User,
    UserAlertPreference,
)
from app.services.price_alert_material_threshold_service import (
    MaterialNotFoundError,
    MaterialThresholdPage,
    MaterialThresholdView,
    PriceAlertMaterialThresholdService,
)
from app.services.user_alert_preference_service import UserAlertPreferenceService

pytestmark = pytest.mark.integration

D = Decimal


@pytest.fixture(autouse=True)
async def reset_defaults(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[None]:
    async def reset() -> None:
        async with session_factory() as session:
            await session.execute(
                update(PriceAlertSetting).values(
                    light_from_percent=D("2.50"),
                    medium_from_percent=D("5.00"),
                    large_over_percent=D("10.00"),
                    anomaly_percent=D("30.00"),
                ),
            )
            await session.commit()

    await reset()
    yield
    await reset()


async def _set(
    session_factory: async_sessionmaker[AsyncSession],
    material_id: uuid.UUID,
    user_id: uuid.UUID,
    light: str = "1.00",
    medium: str = "3.00",
    large: str = "6.00",
    anomaly: str | None = None,
) -> list[dict[str, str]]:
    async with session_factory() as session:
        result = await PriceAlertMaterialThresholdService(session).set_override(
            material_id=material_id,
            light=D(light),
            medium=D(medium),
            large=D(large),
            anomaly=D(anomaly) if anomaly is not None else None,
            updated_by_id=user_id,
        )
        await session.commit()
        return result.changes


async def _row(
    session_factory: async_sessionmaker[AsyncSession],
    material_id: uuid.UUID,
) -> PriceAlertMaterialThreshold | None:
    async with session_factory() as session:
        return (
            await session.execute(
                select(PriceAlertMaterialThreshold).where(
                    PriceAlertMaterialThreshold.material_id == material_id,
                ),
            )
        ).scalar_one_or_none()


async def _list(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> MaterialThresholdPage:
    async with session_factory() as session:
        page = await PriceAlertMaterialThresholdService(session).list_materials(
            limit=limit,
            offset=offset,
            search=search,
        )
        await session.commit()
        return page


async def _item(
    session_factory: async_sessionmaker[AsyncSession],
    material_id: uuid.UUID,
) -> MaterialThresholdView:
    async with session_factory() as session:
        code = (
            await session.execute(select(Material.code).where(Material.id == material_id))
        ).scalar_one()
    page = await _list(session_factory, search=code)
    return next(i for i in page.items if i.material_id == material_id)


@pytest.mark.asyncio
async def test_override_is_saved_and_effective_uses_it_with_default_anomaly(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material_id = await create_material(session_factory)
    user_id = await create_user(session_factory)

    changes = await _set(session_factory, material_id, user_id)

    assert [c["field"] for c in changes] == [
        "light_from_percent",
        "medium_from_percent",
        "large_over_percent",
    ]
    assert changes[0] == {
        "field": "light_from_percent",
        "label": "Ngưỡng Nhẹ từ (%)",
        "old_value": "mặc định",
        "new_value": "1.00",
    }
    row = await _row(session_factory, material_id)
    assert row is not None
    assert (row.light_from_percent, row.medium_from_percent, row.large_over_percent) == (
        D("1.00"),
        D("3.00"),
        D("6.00"),
    )
    assert row.anomaly_percent is None
    assert row.updated_by_id == user_id

    item = await _item(session_factory, material_id)
    assert item.override is not None
    assert item.effective.light_from_percent == D("1.00")
    assert item.effective.anomaly_percent == D("30.00")  # mặc định


@pytest.mark.asyncio
async def test_material_without_override_shows_defaults_and_follows_default_changes(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material_id = await create_material(session_factory)
    async with session_factory() as session:
        await session.execute(update(PriceAlertSetting).values(medium_from_percent=D("6.00")))
        await session.commit()

    item = await _item(session_factory, material_id)

    assert item.override is None
    assert item.effective.medium_from_percent == D("6.00")


@pytest.mark.asyncio
async def test_explicit_anomaly_is_used_and_second_put_updates_in_place(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material_id = await create_material(session_factory)
    user_id = await create_user(session_factory)
    await _set(session_factory, material_id, user_id, anomaly="25.00")

    changes = await _set(session_factory, material_id, user_id, medium="4.00", anomaly="25.00")

    assert [c["field"] for c in changes] == ["medium_from_percent"]
    assert changes[0]["old_value"] == "3.00"
    assert changes[0]["new_value"] == "4.00"
    row = await _row(session_factory, material_id)
    assert row is not None
    assert row.anomaly_percent == D("25.00")
    assert await _set(session_factory, material_id, user_id, medium="4.00", anomaly="25.00") == []

    async with session_factory() as session:
        count = (
            await session.execute(
                text("select count(*) from price_alert_material_thresholds where material_id=:m"),
                {"m": material_id},
            )
        ).scalar_one()
    assert count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kwargs", "fragment"),
    [
        ({"light": "3.00", "medium": "3.00"}, "tăng dần"),
        ({"light": "7.00"}, "tăng dần"),
        ({"large": "30.00"}, "bất thường"),  # anomaly mặc định 30 không lớn hơn
        ({"anomaly": "6.00"}, "bất thường"),
    ],
)
async def test_invalid_override_raises_and_writes_nothing(
    session_factory: async_sessionmaker[AsyncSession],
    kwargs: dict[str, str],
    fragment: str,
) -> None:
    material_id = await create_material(session_factory)
    user_id = await create_user(session_factory)

    with pytest.raises(ValueError, match=fragment):
        await _set(session_factory, material_id, user_id, **kwargs)

    assert await _row(session_factory, material_id) is None


@pytest.mark.asyncio
async def test_anomaly_is_checked_against_the_changed_default(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material_id = await create_material(session_factory)
    user_id = await create_user(session_factory)

    # Mặc định bất thường 30 > Lớn 29,99 thì hợp lệ.
    await _set(session_factory, material_id, user_id, large="29.99")
    assert await _row(session_factory, material_id) is not None


@pytest.mark.asyncio
async def test_unknown_material_raises_not_found_and_writes_nothing(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await create_user(session_factory)
    missing = uuid.uuid4()

    with pytest.raises(MaterialNotFoundError):
        await _set(session_factory, missing, user_id)

    assert await _row(session_factory, missing) is None


@pytest.mark.asyncio
async def test_delete_is_idempotent_and_returns_to_defaults(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material_id = await create_material(session_factory)
    user_id = await create_user(session_factory)
    await _set(session_factory, material_id, user_id, anomaly="25.00")

    async def clear() -> list[dict[str, str]]:
        async with session_factory() as session:
            changes = await PriceAlertMaterialThresholdService(session).clear_override(
                material_id=material_id,
            )
            await session.commit()
            return changes

    first = await clear()
    second = await clear()

    assert [c["field"] for c in first] == [
        "light_from_percent",
        "medium_from_percent",
        "large_over_percent",
        "anomaly_percent",
    ]
    assert first[0]["new_value"] == "mặc định"
    assert second == []
    assert await _row(session_factory, material_id) is None
    async with session_factory() as session:
        missing = await PriceAlertMaterialThresholdService(session).clear_override(
            material_id=uuid.uuid4(),
        )
    assert missing == []


@pytest.mark.asyncio
async def test_search_matches_code_or_name_case_insensitively_and_escapes_wildcards(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tag = uuid.uuid4().hex[:6]
    by_name = await create_material(session_factory, name=f"Ngô hạt {tag}")
    other = await create_material(session_factory, name=f"Khác {tag}")
    async with session_factory() as session:
        code = (
            await session.execute(select(Material.code).where(Material.id == other))
        ).scalar_one()

    by_name_page = await _list(session_factory, search=f"NGÔ HẠT {tag}")
    assert [i.material_id for i in by_name_page.items] == [by_name]
    assert by_name_page.total == 1

    by_code_page = await _list(session_factory, search=code.lower())
    assert [i.material_id for i in by_code_page.items] == [other]

    wildcard = await _list(session_factory, search="%")
    assert wildcard.total == 0
    underscore = await _list(session_factory, search=f"Khác_{tag}")
    assert underscore.total == 0


@pytest.mark.asyncio
async def test_pagination_total_and_stable_order(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tag = uuid.uuid4().hex[:6]
    ids = [await create_material(session_factory, name=f"Phân trang {tag} {n}") for n in range(5)]

    full = await _list(session_factory, search=f"Phân trang {tag}", limit=100)
    page1 = await _list(session_factory, search=f"Phân trang {tag}", limit=2, offset=0)
    page2 = await _list(session_factory, search=f"Phân trang {tag}", limit=2, offset=2)
    page3 = await _list(session_factory, search=f"Phân trang {tag}", limit=2, offset=4)

    assert full.total == page1.total == page2.total == page3.total == 5
    paged = [i.material_id for p in (page1, page2, page3) for i in p.items]
    assert paged == [i.material_id for i in full.items]
    assert set(paged) == set(ids)
    assert len(paged) == 5


@pytest.mark.asyncio
async def test_concurrent_puts_leave_one_consistent_row(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material_id = await create_material(session_factory)
    user_id = await create_user(session_factory)

    await asyncio.gather(
        _set(session_factory, material_id, user_id, light="1.00", medium="2.00", large="3.00"),
        _set(session_factory, material_id, user_id, light="4.00", medium="5.00", large="6.00"),
    )

    row = await _row(session_factory, material_id)
    assert row is not None
    assert row.light_from_percent < row.medium_from_percent < row.large_over_percent  # type: ignore[operator]


@pytest.mark.asyncio
async def test_db_check_constraints_back_up_the_service_rules(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Ghi chú ràng buộc: DB tự chặn dữ liệu sai dù service bị bỏ qua."""
    material_id = await create_material(session_factory)

    async def insert(**values: object) -> None:
        async with session_factory() as session:
            session.add(PriceAlertMaterialThreshold(material_id=material_id, **values))
            await session.commit()

    with pytest.raises(IntegrityError, match="all_or_none"):
        await insert(light_from_percent=D("1.00"))
    with pytest.raises(IntegrityError, match="ordered"):
        await insert(
            light_from_percent=D("5.00"),
            medium_from_percent=D("3.00"),
            large_over_percent=D("6.00"),
        )
    with pytest.raises(IntegrityError, match="anomaly_above_large"):
        await insert(
            light_from_percent=D("1.00"),
            medium_from_percent=D("3.00"),
            large_over_percent=D("6.00"),
            anomaly_percent=D("6.00"),
        )


@pytest.mark.asyncio
async def test_deleting_a_material_cascades_its_override(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material_id = await create_material(session_factory)
    user_id = await create_user(session_factory)
    await _set(session_factory, material_id, user_id)

    async with session_factory() as session:
        await session.execute(delete(Material).where(Material.id == material_id))
        await session.commit()

    assert await _row(session_factory, material_id) is None


# --- tùy chọn cá nhân ---------------------------------------------------------


def _actor(user_id: uuid.UUID, *role_names: str) -> User:
    user = User(id=user_id, email="x@example.com")
    user.roles = [Role(id=uuid.uuid4(), name=name) for name in role_names]
    return user


@pytest.mark.asyncio
async def test_missing_preference_row_returns_defaults_without_creating_one(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await create_user(session_factory)

    async with session_factory() as session:
        staff = await UserAlertPreferenceService(session).get(_actor(user_id, "user"))
        manager = await UserAlertPreferenceService(session).get(_actor(user_id, "manager"))
        rows = (await session.execute(select(UserAlertPreference))).scalars().all()

    assert (staff.is_enabled, staff.min_level, staff.effective_min_level) == (True, None, "light")
    assert manager.effective_min_level == "medium"
    assert staff.admin_receive_all is False
    assert user_id not in {r.user_id for r in rows}


@pytest.mark.asyncio
async def test_put_creates_then_updates_one_row_and_null_returns_to_role_default(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await create_user(session_factory)
    manager = _actor(user_id, "manager")

    async with session_factory() as session:
        service = UserAlertPreferenceService(session)
        first = await service.upsert(
            manager,
            is_enabled=False,
            min_level="large",
            admin_receive_all=False,
        )
        await session.commit()
    assert (first.is_enabled, first.min_level, first.effective_min_level) == (
        False,
        "large",
        "large",
    )

    async with session_factory() as session:
        second = await UserAlertPreferenceService(session).upsert(
            manager,
            is_enabled=True,
            min_level=None,
            admin_receive_all=False,
        )
        await session.commit()
        count = (
            await session.execute(
                text("select count(*) from user_alert_preferences where user_id=:u"),
                {"u": user_id},
            )
        ).scalar_one()
    assert (second.is_enabled, second.min_level, second.effective_min_level) == (
        True,
        None,
        "medium",
    )
    assert count == 1


@pytest.mark.asyncio
async def test_admin_receive_all_only_for_admin_and_nothing_is_written_otherwise(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await create_user(session_factory)

    async with session_factory() as session:
        with pytest.raises(PermissionError):
            await UserAlertPreferenceService(session).upsert(
                _actor(user_id, "manager"),
                is_enabled=True,
                min_level=None,
                admin_receive_all=True,
            )
        await session.rollback()
        saved = await UserAlertPreferenceService(session).upsert(
            _actor(user_id, "admin"),
            is_enabled=True,
            min_level=None,
            admin_receive_all=True,
        )
        await session.commit()
    assert saved.admin_receive_all is True

    async with session_factory() as session:
        again = await UserAlertPreferenceService(session).get(_actor(user_id, "admin"))
    assert again.admin_receive_all is True


@pytest.mark.asyncio
async def test_invalid_level_is_rejected_and_db_check_backs_it_up(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await create_user(session_factory)

    async with session_factory() as session:
        with pytest.raises(ValueError, match="light"):
            await UserAlertPreferenceService(session).upsert(
                _actor(user_id, "user"),
                is_enabled=True,
                min_level="huge",
                admin_receive_all=False,
            )

    async with session_factory() as session:
        session.add(UserAlertPreference(user_id=user_id, min_level="huge"))
        with pytest.raises(IntegrityError, match="min_level"):
            await session.commit()
