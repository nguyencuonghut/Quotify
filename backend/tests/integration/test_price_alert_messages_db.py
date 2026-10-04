"""Gộp sự kiện thành tin theo người nhận (D5b, L18, L27) trên PostgreSQL thật."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from db_helpers import create_confirmed_quote_version, create_material, ensure_role
from price_alert_scene import Scene
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
    Material,
    PriceAlertEvent,
    PriceAlertMessage,
    PriceAlertMessageEvent,
    PriceAlertScanRun,
    PriceAlertSetting,
)
from app.services.price_alert_candidates import BUSINESS_TIMEZONE
from app.services.price_alert_messages import (
    ROLLING_CAP,
    BuildResult,
    PriceAlertMessageService,
)

pytestmark = pytest.mark.integration

RECEIVE_ALL = "price_alerts.receive_all"
BASE = datetime(2047, 3, 3, 3, 0, tzinfo=UTC)
_runs = iter(range(10_000))


@pytest.fixture
async def scene(session_factory: async_sessionmaker[AsyncSession]) -> Scene:
    await ensure_role(session_factory, "it-manager", [RECEIVE_ALL])
    built = await Scene(session_factory).setup()
    async with session_factory() as session:
        await session.execute(
            update(PriceAlertSetting).values(immediate_cap_per_scan=30, staff_lookback_days=90)
        )
        await session.commit()
    return built


def moment(days: int = 0, minutes: int = 0) -> datetime:
    """Mỗi test một khoảng ngày riêng (DB dùng chung) cộng độ lệch phút trong ngày."""
    return BASE + timedelta(days=next(_runs) * 40 + days, minutes=minutes)


async def new_run(sf: async_sessionmaker[AsyncSession], at: datetime) -> uuid.UUID:
    async with sf() as session:
        run = PriceAlertScanRun(started_at=at)
        session.add(run)
        await session.commit()
        return run.id


async def add_event(
    sf: async_sessionmaker[AsyncSession],
    run_id: uuid.UUID,
    material: uuid.UUID,
    level: str,
    direction: str = "up",
    month: date = date(2047, 12, 1),
    prior_alert_price: Decimal | None = None,
) -> uuid.UUID:
    version = await create_confirmed_quote_version(sf)
    async with sf() as session:
        event = PriceAlertEvent(
            scan_run_id=run_id,
            quote_version_id=version,
            material_id=material,
            delivery_month=month,
            kind="change",
            direction=direction,
            level=level,
            rule="R1",
            percent_change=Decimal("6.00"),
            price_new=Decimal(106),
            price_ref=Decimal(100),
            received_date_new=date(2047, 3, 3),
            received_date_ref=date(2047, 3, 2),
            window_min=Decimal(95),
            window_max=Decimal(105),
            window_min_date=date(2047, 2, 28),
            window_max_date=date(2047, 3, 1),
            reference_point_count=3,
            prior_alert_price=prior_alert_price,
        )
        session.add(event)
        await session.commit()
        return event.id


async def build(
    sf: async_sessionmaker[AsyncSession],
    run_id: uuid.UUID,
    at: datetime,
    scene: Scene,
    *,
    pilot: frozenset[str] = frozenset(),
    cap: int | None = None,
) -> BuildResult:
    async with sf() as session:
        settings = (await session.execute(select(PriceAlertSetting))).scalar_one()
        if cap is not None:
            session.expunge(settings)  # chỉ đổi bản sao trong bộ nhớ, không ghi DB
            settings.immediate_cap_per_scan = cap
        result = await PriceAlertMessageService(
            session, seed_user_id=None, pilot_emails=pilot
        ).build_for_run(scan_run_id=run_id, now=at, settings=settings)
        await session.commit()
    return result


async def messages(
    sf: async_sessionmaker[AsyncSession], scene: Scene, **filters: object
) -> list[PriceAlertMessage]:
    async with sf() as session:
        rows = (
            await session.execute(
                select(PriceAlertMessage)
                .where(
                    PriceAlertMessage.user_id.in_(scene.mine), PriceAlertMessage.kind != "digest"
                )
                .order_by(PriceAlertMessage.sequence_number)
            )
        ).scalars()
        return [m for m in rows if all(getattr(m, k) == v for k, v in filters.items())]


async def test_two_delivery_months_of_one_material_make_one_message_linking_both_events(
    scene: Scene,
) -> None:
    sf = scene.sf
    manager = await scene.person("it-manager")
    at = moment()
    run = await new_run(sf, at)
    medium = await add_event(sf, run, scene.material, "medium", month=date(2047, 11, 1))
    large = await add_event(sf, run, scene.material, "large", month=date(2047, 12, 1))

    result = await build(sf, run, at, scene)

    [message] = await messages(sf, scene)
    assert (message.user_id, message.material_id) == (manager, scene.material)
    assert (message.level_max, message.direction, message.status) == ("large", "up", "pending")
    assert message.kind == "change"
    assert message.local_date == at.astimezone(BUSINESS_TIMEZONE).date()
    assert result.created >= 1
    async with sf() as session:
        linked = set(
            (
                await session.execute(
                    select(PriceAlertMessageEvent.event_id).where(
                        PriceAlertMessageEvent.message_id == message.id
                    )
                )
            ).scalars()
        )
    assert linked == {medium, large}


async def test_a_light_event_is_queued_for_the_digest_and_never_pending(scene: Scene) -> None:
    sf = scene.sf
    staff = await scene.person()
    await scene.entered(staff, received=date(2046, 6, 15))
    at = datetime(2046, 6, 15, 3, 0, tzinfo=UTC)
    run = await new_run(sf, at)
    await add_event(sf, run, scene.material, "light")

    await build(sf, run, at, scene)

    [message] = await messages(sf, scene)
    assert (message.status, message.status_reason, message.level_max) == (
        "digest_queued",
        "light",
        "light",
    )


async def test_the_same_day_repeat_is_suppressed_but_escalation_or_a_flip_is_sent(
    scene: Scene,
) -> None:
    sf = scene.sf
    await scene.person("it-manager")
    base = moment()

    async def scan(minutes: int, level: str, direction: str = "up") -> None:
        at = base + timedelta(minutes=minutes)
        run = await new_run(sf, at)
        await add_event(sf, run, scene.material, level, direction)
        await build(sf, run, at, scene)

    await scan(0, "medium")
    await scan(1, "medium")  # cùng mức, cùng chiều
    await scan(2, "large")  # leo thang
    await scan(3, "medium")  # thấp hơn mức cao nhất
    await scan(4, "large", "down")  # đổi chiều

    assert [(m.status, m.level_max, m.direction) for m in await messages(sf, scene)] == [
        ("pending", "medium", "up"),
        ("suppressed", "medium", "up"),
        ("pending", "large", "up"),
        ("suppressed", "medium", "up"),
        ("pending", "large", "down"),
    ]


async def test_a_new_local_day_starts_again(scene: Scene) -> None:
    sf = scene.sf
    await scene.person("it-manager")
    day_one = moment()
    for at in (day_one, day_one + timedelta(days=1)):
        run = await new_run(sf, at)
        await add_event(sf, run, scene.material, "medium")
        await build(sf, run, at, scene)

    assert [m.status for m in await messages(sf, scene)] == ["pending", "pending"]


async def test_the_per_scan_cap_queues_the_rest_and_adds_one_summary(scene: Scene) -> None:
    sf = scene.sf
    manager = await scene.person("it-manager")
    # Vật tư Lớn có id sắp sau cùng: nếu không ưu tiên theo mức thì nó bị trần cắt nhầm.
    materials = sorted([await create_material(sf) for _ in range(4)], key=str)
    at = moment()
    run = await new_run(sf, at)
    large_material = materials[-1]
    for material in materials[:-1]:
        await add_event(sf, run, material, "medium")
    await add_event(sf, run, large_material, "large")

    result = await build(sf, run, at, scene, cap=2)

    by_material = {m.material_id: m for m in await messages(sf, scene)}
    assert by_material[large_material].status == "pending"  # mức cao đi trước, không bị cắt
    statuses = sorted(m.status for m in by_material.values())
    assert statuses == ["digest_queued", "digest_queued", "pending", "pending"]
    assert all(
        m.status_reason == "cap" for m in by_material.values() if m.status == "digest_queued"
    )
    async with sf() as session:
        [summary] = (
            await session.execute(
                select(PriceAlertMessage).where(
                    PriceAlertMessage.user_id == manager, PriceAlertMessage.kind == "digest"
                )
            )
        ).scalars()
        linked = (
            await session.execute(
                select(func.count()).where(PriceAlertMessageEvent.message_id == summary.id)
            )
        ).scalar_one()
    assert (summary.status, summary.status_reason, summary.material_id) == (
        "pending",
        "overflow",
        None,
    )
    assert linked == 2
    assert result.created >= 5


async def test_the_ten_minute_cap_counts_what_the_person_already_received(scene: Scene) -> None:
    sf = scene.sf
    manager = await scene.person("it-manager")
    at = moment()
    other_materials = [await create_material(sf) for _ in range(ROLLING_CAP - 1)]
    async with sf() as session:
        for other in other_materials:
            session.add(
                PriceAlertMessage(
                    user_id=manager,
                    material_id=other,
                    local_date=at.date(),
                    kind="change",
                    level_max="medium",
                    direction="up",
                    status="sent",
                    created_at=at - timedelta(minutes=5),
                )
            )
        await session.commit()
    run = await new_run(sf, at)
    first, second = await create_material(sf), await create_material(sf)
    await add_event(sf, run, first, "large")
    await add_event(sf, run, second, "medium")

    await build(sf, run, at, scene)

    statuses = {
        m.material_id: m.status
        for m in await messages(sf, scene, user_id=manager)
        if m.material_id in (first, second)
    }
    assert statuses == {first: "pending", second: "digest_queued"}

    # Sau 11 phút các tin cũ ra khỏi cửa sổ nên trần được tính lại.
    later = at + timedelta(minutes=11)
    run2 = await new_run(sf, later)
    third = await create_material(sf)
    await add_event(sf, run2, third, "medium")
    await build(sf, run2, later, scene)
    [last] = [m for m in await messages(sf, scene) if m.material_id == third]
    assert last.status == "pending"


async def test_building_twice_for_the_same_run_creates_nothing_new(scene: Scene) -> None:
    sf = scene.sf
    await scene.person("it-manager")
    at = moment()
    run = await new_run(sf, at)
    await add_event(sf, run, scene.material, "medium")

    first = await build(sf, run, at, scene)
    second = await build(sf, run, at, scene)

    assert first.created >= 1
    assert second.created == 0
    assert len(await messages(sf, scene)) == 1


async def test_people_outside_the_pilot_list_get_a_skipped_message_with_the_reason(
    scene: Scene,
) -> None:
    sf = scene.sf
    keep_email = f"keep-{uuid.uuid4().hex[:8]}@example.com"
    keep = await scene.person("it-manager", email=keep_email)
    other = await scene.person("it-manager", email=f"other-{uuid.uuid4().hex[:8]}@example.com")
    at = moment()
    run = await new_run(sf, at)
    await add_event(sf, run, scene.material, "large")

    await build(sf, run, at, scene, pilot=frozenset({keep_email}))

    by_user = {m.user_id: m for m in await messages(sf, scene)}
    assert by_user[keep].status == "pending"
    assert (by_user[other].status, by_user[other].status_reason) == ("skipped", "pilot")
    assert by_user[other].telegram_account_id is None


async def test_a_run_without_events_or_recipients_creates_no_message(scene: Scene) -> None:
    sf = scene.sf
    at = moment()
    empty_run = await new_run(sf, at)
    nobody_run = await new_run(sf, at)
    await add_event(sf, nobody_run, scene.material, "large")

    assert (await build(sf, empty_run, at, scene)).created == 0
    await build(sf, nobody_run, at, scene)
    assert await messages(sf, scene) == []


async def test_a_message_cut_by_the_cap_does_not_block_the_same_event_next_scan(
    scene: Scene,
) -> None:
    sf = scene.sf
    await scene.person("it-manager")
    first = moment()
    run_one = await new_run(sf, first)
    await add_event(sf, run_one, scene.material, "medium")
    await build(sf, run_one, first, scene, cap=0)  # trần 0: bị cắt, chưa từng được gửi riêng
    second = first + timedelta(minutes=1)
    run_two = await new_run(sf, second)
    await add_event(sf, run_two, scene.material, "medium")

    await build(sf, run_two, second, scene)

    assert [(m.status, m.status_reason) for m in await messages(sf, scene)] == [
        ("digest_queued", "cap"),
        ("pending", None),
    ]


async def test_two_scans_of_twenty_share_one_ten_minute_cap_and_one_summary(
    scene: Scene,
) -> None:
    sf = scene.sf
    manager = await scene.person("it-manager")
    start = moment()
    for index in range(3):
        at = start + timedelta(seconds=30 * index)
        run = await new_run(sf, at)
        for _ in range(20 if index < 2 else 5):
            await add_event(sf, run, await create_material(sf), "medium")
        await build(sf, run, at, scene)

    statuses = [m.status for m in await messages(sf, scene)]
    assert statuses.count("pending") == ROLLING_CAP
    assert statuses.count("digest_queued") == 15
    async with sf() as session:
        summaries = (
            await session.execute(
                select(func.count()).where(
                    PriceAlertMessage.user_id == manager, PriceAlertMessage.kind == "digest"
                )
            )
        ).scalar_one()
    assert summaries == 1


async def test_the_local_date_is_the_vietnam_date_not_the_utc_date(scene: Scene) -> None:
    sf = scene.sf
    await scene.person("it-manager")
    # 17:30 UTC = 00:30 hôm sau ở Việt Nam.
    at = datetime(2048, 5, 10, 17, 30, tzinfo=UTC)
    run = await new_run(sf, at)
    await add_event(sf, run, scene.material, "medium")

    await build(sf, run, at, scene)

    [message] = await messages(sf, scene)
    assert message.local_date == date(2048, 5, 11)


async def test_a_stored_message_loads_into_the_view_the_formatter_needs(scene: Scene) -> None:
    from app.services.price_alert_formatter import chart_title, format_caption, format_details
    from app.services.price_alert_message_view import load_message_view

    sf = scene.sf
    await scene.person("it-manager")
    at = moment()
    run = await new_run(sf, at)
    await add_event(sf, run, scene.material, "medium", month=date(2047, 11, 1))
    await add_event(sf, run, scene.material, "large", "down", month=date(2047, 12, 1))
    await build(sf, run, at, scene)
    [message] = await messages(sf, scene)
    async with sf() as session:
        settings = (await session.execute(select(PriceAlertSetting))).scalar_one()
        view = await load_message_view(session, message.id, settings)
        material_name = (
            await session.execute(select(Material.name).where(Material.id == scene.material))
        ).scalar_one()

    assert view is not None
    assert view.material_name == material_name
    assert [e.delivery_month for e in view.events] == [date(2047, 11, 1), date(2047, 12, 1)]
    assert view.reference_working_days == 7
    assert chart_title(view).startswith("▼ GIẢM LỚN")
    assert "➕ Kỳ 12/2047 và 1 kỳ khác" in format_caption(view)
    assert "🟠 11/2047" in format_details(view, base_url="https://x.example")


async def test_loading_a_digest_or_unknown_message_returns_nothing(scene: Scene) -> None:
    from app.services.price_alert_message_view import load_message_view

    async with scene.sf() as session:
        settings = (await session.execute(select(PriceAlertSetting))).scalar_one()
        assert await load_message_view(session, uuid.uuid4(), settings) is None


async def test_a_stored_message_renders_a_decodable_chart_for_its_strongest_period(
    scene: Scene,
) -> None:
    import io

    from db_helpers import create_priced_line
    from PIL import Image

    from app.services.price_alert_chart import render_price_chart
    from app.services.price_alert_message_view import load_chart_spec, load_message_view

    sf = scene.sf
    await scene.person("it-manager")
    at = moment()
    new_day = date(2047, 3, 3)
    for offset, price in {-4: 7900, -3: 7720, -1: 7800, 0: 8150}.items():
        await create_priced_line(
            sf,
            material_id=scene.material,
            price=price,
            received_date=new_day + timedelta(days=offset),
            delivery_month=date(2047, 12, 1),
        )
    run = await new_run(sf, at)
    await add_event(sf, run, scene.material, "medium", month=date(2047, 12, 1))
    await build(sf, run, at, scene)
    [message] = await messages(sf, scene)

    async with sf() as session:
        settings = (await session.execute(select(PriceAlertSetting))).scalar_one()
        view = await load_message_view(session, message.id, settings)
        assert view is not None
        spec = await load_chart_spec(session, message.id, view)

    assert spec is not None
    assert [p[0] for p in spec.points][-1] == new_day
    assert spec.title.startswith("▲ TĂNG TRUNG BÌNH")
    png = await render_price_chart(spec)
    assert Image.open(io.BytesIO(png)).size == (900, 500)


async def test_a_message_made_only_of_a_cancelled_quotes_event_does_not_suppress_the_next_one(
    scene: Scene,
) -> None:
    from sqlalchemy import update as sa_update

    from app.models import Quote, QuoteVersion

    sf = scene.sf
    await scene.person("it-manager")
    base = moment()
    run_one = await new_run(sf, base)
    event_one = await add_event(sf, run_one, scene.material, "medium")
    await build(sf, run_one, base, scene)
    async with sf() as session:
        quote_id = (
            await session.execute(
                select(QuoteVersion.quote_id)
                .join(PriceAlertEvent, PriceAlertEvent.quote_version_id == QuoteVersion.id)
                .where(PriceAlertEvent.id == event_one)
            )
        ).scalar_one()
        await session.execute(
            sa_update(Quote).where(Quote.id == quote_id).values(cancelled_at=base)
        )
        await session.commit()
    later = base + timedelta(minutes=1)
    run_two = await new_run(sf, later)
    await add_event(sf, run_two, scene.material, "medium")

    await build(sf, run_two, later, scene)

    assert [m.status for m in await messages(sf, scene)] == ["pending", "pending"]


async def test_a_follow_up_event_gets_a_message_even_though_the_level_did_not_rise(
    scene: Scene,
) -> None:
    sf = scene.sf
    await scene.person("it-manager")
    base = moment()
    run_one = await new_run(sf, base)
    await add_event(sf, run_one, scene.material, "large", "down")
    await build(sf, run_one, base, scene)
    later = base + timedelta(minutes=1)
    plain = await new_run(sf, later)
    await add_event(sf, plain, scene.material, "large", "down")
    await build(sf, plain, later, scene)
    final = base + timedelta(minutes=2)
    follow = await new_run(sf, final)
    await add_event(sf, follow, scene.material, "large", "down", prior_alert_price=Decimal(6500))

    await build(sf, follow, final, scene)

    assert [m.status for m in await messages(sf, scene)] == ["pending", "suppressed", "pending"]


async def test_a_follow_up_in_a_weaker_period_does_not_unlock_the_whole_group(scene: Scene) -> None:
    sf = scene.sf
    await scene.person("it-manager")
    base = moment()
    first = await new_run(sf, base)
    await add_event(sf, first, scene.material, "large", "down", month=date(2047, 11, 1))
    await build(sf, first, base, scene)
    later = base + timedelta(minutes=1)
    second = await new_run(sf, later)
    # kỳ đứng đầu (Lớn) là lặp thường; chỉ kỳ yếu hơn là báo tiếp
    await add_event(sf, second, scene.material, "large", "down", month=date(2047, 11, 1))
    await add_event(
        sf,
        second,
        scene.material,
        "medium",
        "down",
        month=date(2047, 12, 1),
        prior_alert_price=Decimal(100),
    )

    await build(sf, second, later, scene)

    assert [m.status for m in await messages(sf, scene)] == ["pending", "suppressed"]
