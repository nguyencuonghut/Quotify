"""Bản tin tổng hợp hằng ngày cho mức Nhẹ trên PostgreSQL thật (1C, Slice 1, M1 đến M4)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from db_helpers import create_confirmed_quote_version, create_material, ensure_role
from price_alert_scene import Scene
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
    PriceAlertEvent,
    PriceAlertMessage,
    PriceAlertMessageEvent,
    PriceAlertScanState,
    PriceAlertSetting,
    TelegramAccount,
    UserAlertPreference,
)
from app.services.price_alert_candidates import BUSINESS_TIMEZONE, record_scanned_version
from app.services.price_alert_digest import PriceAlertDigestService

pytestmark = pytest.mark.integration

# Thứ Tư 04/03/2054, 08:10 giờ Việt Nam. Năm 2054 để mọi dữ liệu của test khác đều "quá cũ".
TODAY = date(2054, 3, 4)
NOW = datetime(2054, 3, 4, 1, 10, tzinfo=UTC)


def vn(day: date, hour: int = 8, minute: int = 10) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=BUSINESS_TIMEZONE)


@pytest.fixture
async def scene(session_factory: async_sessionmaker[AsyncSession]) -> Scene:
    await ensure_role(session_factory, "it-manager", ["price_alerts.receive_all"])
    async with session_factory() as session:
        await session.execute(
            update(PriceAlertSetting).values(is_enabled=True, digest_hour_local=8)
        )
        await session.execute(update(PriceAlertScanState).values(last_digest_local_date=None))
        # Tin chờ của test khác (DB dùng chung) không được lọt vào bản tin của test này.
        await session.execute(
            update(PriceAlertMessage)
            .where(PriceAlertMessage.status.in_(("pending", "sending")))
            .values(status="failed", status_reason="test_cleanup")
        )
        await session.execute(update(TelegramAccount).values(status="revoked"))
        await session.commit()
    return await Scene(session_factory).setup()


async def queue(
    scene: Scene,
    user_id: uuid.UUID,
    *,
    material: uuid.UUID | None = None,
    local_date: date = TODAY - timedelta(days=1),
    percent: str = "3.20",
    price: int = 8400,
    direction: str = "up",
    reason: str = "light",
    level: str = "light",
    month: date = date(2054, 12, 1),
) -> tuple[uuid.UUID, uuid.UUID]:
    """Một tin `digest_queued` kèm sự kiện của nó; trả `(message_id, event_id)`."""
    sf = scene.sf
    version = await create_confirmed_quote_version(sf)
    async with sf() as session:
        await record_scanned_version(
            session, version_id=version, is_trigger_source=False, trigger_delay_working_days=None
        )
        event = PriceAlertEvent(
            quote_version_id=version,
            material_id=material or scene.material,
            delivery_month=month,
            kind="change",
            direction=direction,
            level=level,
            rule="R1",
            percent_change=Decimal(percent),
            price_new=Decimal(price),
            price_ref=Decimal(8140),
            received_date_new=local_date,
            received_date_ref=local_date - timedelta(days=2),
            window_min=Decimal(8100),
            window_max=Decimal(8300),
            window_min_date=local_date - timedelta(days=3),
            window_max_date=local_date - timedelta(days=4),
            reference_point_count=4,
            created_at=vn(local_date, 15, 0),
        )
        session.add(event)
        await session.flush()
        account_id = (
            await session.execute(
                select(TelegramAccount.id).where(TelegramAccount.user_id == user_id)
            )
        ).scalar_one()
        message = PriceAlertMessage(
            user_id=user_id,
            telegram_account_id=account_id,
            material_id=material or scene.material,
            local_date=local_date,
            kind="change",
            level_max=level,
            direction=direction,
            status="digest_queued",
            status_reason=reason,
            created_at=vn(local_date, 15, 0),
        )
        session.add(message)
        await session.flush()
        session.add(PriceAlertMessageEvent(message_id=message.id, event_id=event.id))
        await session.commit()
        return message.id, event.id


async def run_digest(scene: Scene, now: datetime = NOW):  # type: ignore[no-untyped-def]
    async with scene.sf() as session:
        settings = (await session.execute(select(PriceAlertSetting))).scalar_one()
        result = await PriceAlertDigestService(session).run_once(now=now, settings=settings)
        await session.commit()
    return result


async def messages_of(scene: Scene, user_id: uuid.UUID) -> list[PriceAlertMessage]:
    async with scene.sf() as session:
        return list(
            (
                await session.execute(
                    select(PriceAlertMessage)
                    .where(PriceAlertMessage.user_id == user_id)
                    .order_by(PriceAlertMessage.sequence_number)
                )
            ).scalars()
        )


async def test_queued_light_changes_become_one_daily_digest_per_person(scene: Scene) -> None:
    person = await scene.person("it-manager")
    other_material = await create_material(scene.sf)
    first, first_event = await queue(scene, person)
    second, second_event = await queue(scene, person, material=other_material, percent="2.60")

    result = await run_digest(scene)

    assert result.digests_created == 1
    rows = {m.id: m for m in await messages_of(scene, person)}
    digest = next(m for m in rows.values() if m.digest_kind == "daily")
    assert (digest.kind, digest.status, digest.local_date) == ("digest", "pending", TODAY)
    assert digest.material_id is None and digest.telegram_account_id is not None
    for source in (first, second):
        assert (rows[source].status, rows[source].status_reason) == ("sent", "in_digest")
    async with scene.sf() as session:
        linked = set(
            (
                await session.execute(
                    select(PriceAlertMessageEvent.event_id).where(
                        PriceAlertMessageEvent.message_id == digest.id
                    )
                )
            ).scalars()
        )
        state = (await session.execute(select(PriceAlertScanState))).scalar_one()
    assert linked == {first_event, second_event}
    assert state.last_digest_local_date == TODAY


async def test_running_again_the_same_day_creates_nothing_new(scene: Scene) -> None:
    person = await scene.person("it-manager")
    await queue(scene, person)

    await run_digest(scene)
    again = await run_digest(scene, NOW + timedelta(hours=1))

    assert again.skipped == "already_sent" and again.digests_created == 0
    digests = [m for m in await messages_of(scene, person) if m.digest_kind == "daily"]
    assert len(digests) == 1


async def test_with_nothing_queued_no_message_is_made_and_the_day_is_still_marked(
    scene: Scene,
) -> None:
    person = await scene.person("it-manager")

    result = await run_digest(scene)

    assert result.digests_created == 0
    assert await messages_of(scene, person) == []
    async with scene.sf() as session:
        state = (await session.execute(select(PriceAlertScanState))).scalar_one()
    assert state.last_digest_local_date == TODAY


async def test_before_the_digest_hour_nothing_runs_and_a_later_run_the_same_day_catches_up(
    scene: Scene,
) -> None:
    person = await scene.person("it-manager")
    await queue(scene, person)

    early = await run_digest(scene, vn(TODAY, 7, 10))
    assert early.skipped == "not_due"
    async with scene.sf() as session:
        state = (await session.execute(select(PriceAlertScanState))).scalar_one()
    assert state.last_digest_local_date is None

    late = await run_digest(scene, vn(TODAY, 9, 30))
    assert late.digests_created == 1


async def test_a_weekend_day_still_gets_its_digest_when_there_is_something_to_send(
    scene: Scene,
) -> None:
    person = await scene.person("it-manager")
    saturday = date(2054, 3, 7)
    await queue(scene, person, local_date=saturday - timedelta(days=1))

    result = await run_digest(scene, vn(saturday))

    assert result.digests_created == 1


async def test_capped_changes_stay_out_and_stale_ones_are_dropped(scene: Scene) -> None:
    person = await scene.person("it-manager")
    other = await create_material(scene.sf)
    third = await create_material(scene.sf)
    capped, _ = await queue(scene, person, level="medium", reason="cap")
    stale, _ = await queue(scene, person, material=other, local_date=TODAY - timedelta(days=4))
    recent, _ = await queue(scene, person, material=third, local_date=TODAY - timedelta(days=3))

    result = await run_digest(scene)

    rows = {m.id: m for m in await messages_of(scene, person)}
    assert (rows[capped].status, rows[capped].status_reason) == ("digest_queued", "cap")
    assert (rows[stale].status, rows[stale].status_reason) == ("suppressed", "stale")
    assert (rows[recent].status, rows[recent].status_reason) == ("sent", "in_digest")
    assert result.digests_created == 1 and result.stale >= 1


async def test_each_person_gets_their_own_digest_and_opted_out_people_none(
    scene: Scene,
) -> None:
    first = await scene.person("it-manager")
    second = await scene.person("it-manager")
    quiet = await scene.person("it-manager")
    async with scene.sf() as session:
        session.add(UserAlertPreference(user_id=quiet, is_enabled=False))
        await session.commit()
    other = await create_material(scene.sf)
    await queue(scene, first)
    await queue(scene, second, material=other)
    muted, _ = await queue(scene, quiet)

    result = await run_digest(scene)

    assert result.digests_created == 2
    for person in (first, second):
        digests = [m for m in await messages_of(scene, person) if m.digest_kind == "daily"]
        assert len(digests) == 1
    assert [m for m in await messages_of(scene, quiet) if m.digest_kind == "daily"] == []
    muted_row = next(m for m in await messages_of(scene, quiet) if m.id == muted)
    assert (muted_row.status, muted_row.status_reason) == ("suppressed", "opted_out")


async def test_two_runs_at_once_make_exactly_one_digest(scene: Scene) -> None:
    import asyncio

    person = await scene.person("it-manager")
    await queue(scene, person)

    await asyncio.gather(run_digest(scene), run_digest(scene))

    digests = [m for m in await messages_of(scene, person) if m.digest_kind == "daily"]
    assert len(digests) == 1


async def test_the_sender_delivers_the_daily_digest_as_one_message_per_person(scene: Scene) -> None:
    import json

    import httpx

    from app.integrations.telegram import TelegramClient
    from app.services.price_alert_sender import PriceAlertSender

    person = await scene.person("it-manager")
    other = await create_material(scene.sf)
    await queue(scene, person, percent="2.60", price=8400)
    await queue(scene, person, material=other, percent="4.10", price=7800, direction="down")
    await run_digest(scene)
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 11}})

    client = TelegramClient(
        token="123456789:AAFakeTokenFakeTokenFakeTokenFake12",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
    )
    outcome = await PriceAlertSender(scene.sf, client, base_url="https://q.example").run_once(
        NOW + timedelta(seconds=1)
    )

    assert outcome.sent == 1
    payload = json.loads(requests[0].content)
    assert payload["text"].startswith("📋 <b>Bản tin giá · 04/03</b>")
    assert "▼4.10%" in payload["text"] and "▲2.60%" in payload["text"]
    assert "disable_notification" not in payload and "reply_markup" not in payload
