"""Tin giá bất thường: người nhận, thẻ có/không nút, tin tóm tắt và gửi (Slice 12, L28)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
from db_helpers import create_confirmed_quote_version, create_material, ensure_role
from price_alert_scene import Scene
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.integrations.telegram import TelegramClient
from app.models import (
    PriceAlertEvent,
    PriceAlertMessage,
    PriceAlertMessageEvent,
    PriceAlertScanRun,
    PriceAlertSetting,
    TelegramAccount,
)
from app.services.price_alert_anomaly_messages import build_anomaly_messages
from app.services.price_alert_sender import PriceAlertSender

pytestmark = pytest.mark.integration

TOKEN = "123456789:AAFakeTokenFakeTokenFakeTokenFake12"
NOW = datetime(2052, 5, 5, 3, 0, tzinfo=UTC)
MONTH = date(2052, 12, 1)


@pytest.fixture
async def scene(session_factory: async_sessionmaker[AsyncSession]) -> Scene:
    await ensure_role(session_factory, "it-manager", ["price_alerts.receive_all"])
    async with session_factory() as session:
        await session.execute(
            update(PriceAlertMessage)
            .where(PriceAlertMessage.status.in_(("pending", "sending")))
            .values(status="failed", status_reason="test_cleanup")
        )
        await session.execute(update(PriceAlertSetting).values(is_enabled=True))
        # Trưởng phòng của test khác (DB dùng chung) không được lọt vào danh sách người nhận.
        await session.execute(update(TelegramAccount).values(status="revoked"))
        await session.commit()
    return await Scene(session_factory).setup()


async def new_run(sf: async_sessionmaker[AsyncSession]) -> uuid.UUID:
    async with sf() as session:
        run = PriceAlertScanRun(started_at=NOW)
        session.add(run)
        await session.commit()
        return run.id


async def flag(
    sf: async_sessionmaker[AsyncSession],
    run: uuid.UUID,
    material: uuid.UUID,
    enterer: uuid.UUID | None,
    *,
    month: date = MONTH,
    attached_to: uuid.UUID | None = None,
    price: int = 970,
) -> uuid.UUID:
    version = await create_confirmed_quote_version(sf, created_by_id=enterer)
    async with sf() as session:
        event = PriceAlertEvent(
            scan_run_id=run,
            quote_version_id=version,
            material_id=material,
            delivery_month=month,
            kind="anomaly",
            direction="down",
            percent_change=Decimal("-96.21"),
            price_new=Decimal(price),
            price_ref=Decimal(25600),
            received_date_new=NOW.date(),
            reference_point_count=3,
            reference_prices=[Decimal(25600), Decimal(25435), Decimal(25900)],
            review_status="pending",
            attached_to_event_id=attached_to,
            created_at=NOW,
        )
        session.add(event)
        await session.commit()
        return event.id


async def build(
    sf: async_sessionmaker[AsyncSession], run: uuid.UUID, *, pilot: frozenset[str] = frozenset()
) -> int:
    async with sf() as session:
        settings = (await session.execute(select(PriceAlertSetting))).scalar_one()
        created, _ = await build_anomaly_messages(
            session, scan_run_id=run, now=NOW, settings=settings, seed_user_id=None,
            pilot_emails=pilot,
        )  # fmt: skip
        await session.commit()
    return created


async def stored(sf: async_sessionmaker[AsyncSession], scene: Scene) -> list[PriceAlertMessage]:
    async with sf() as session:
        rows = (
            await session.execute(
                select(PriceAlertMessage)
                .where(PriceAlertMessage.user_id.in_(scene.mine))
                .order_by(PriceAlertMessage.sequence_number)
            )
        ).scalars()
        return list(rows)


async def test_manager_and_enterer_each_get_one_card_with_their_audience(scene: Scene) -> None:
    manager = await scene.person("it-manager")
    enterer = await scene.person()
    stranger = await scene.person()  # nhân viên khác, không nhập phiếu này
    run = await new_run(scene.sf)
    await flag(scene.sf, run, scene.material, enterer)

    assert await build(scene.sf, run) == 2

    by_user = {m.user_id: m for m in await stored(scene.sf, scene)}
    assert set(by_user) == {manager, enterer}
    assert stranger not in by_user
    assert (by_user[manager].audience, by_user[enterer].audience) == ("manager", "enterer")
    assert all(m.kind == "anomaly" and m.status == "pending" for m in by_user.values())


async def test_a_manager_who_entered_the_quote_gets_one_card_with_buttons(scene: Scene) -> None:
    manager = await scene.person("it-manager")
    run = await new_run(scene.sf)
    await flag(scene.sf, run, scene.material, manager)

    assert await build(scene.sf, run) == 1

    (message,) = await stored(scene.sf, scene)
    assert message.audience == "manager"


async def test_an_attached_point_makes_no_message_of_its_own(scene: Scene) -> None:
    await scene.person("it-manager")
    run = await new_run(scene.sf)
    first = await flag(scene.sf, run, scene.material, None)
    await flag(scene.sf, run, scene.material, None, month=MONTH, attached_to=first, price=980)

    assert await build(scene.sf, run) == 1

    (message,) = await stored(scene.sf, scene)
    async with scene.sf() as session:
        linked = (
            await session.execute(
                select(PriceAlertMessageEvent.event_id).where(
                    PriceAlertMessageEvent.message_id == message.id
                )
            )
        ).scalars()
        assert list(linked) == [first]


async def test_three_points_for_one_person_collapse_into_one_summary(scene: Scene) -> None:
    manager = await scene.person("it-manager")
    other = await create_material(scene.sf)
    run = await new_run(scene.sf)
    ids = [
        await flag(scene.sf, run, scene.material, None),
        await flag(scene.sf, run, scene.material, None, month=date(2053, 1, 1)),
        await flag(scene.sf, run, other, None),
    ]

    assert await build(scene.sf, run) == 1

    (message,) = await stored(scene.sf, scene)
    assert (message.user_id, message.kind, message.status_reason) == (
        manager,
        "digest",
        "anomaly_cluster",
    )
    async with scene.sf() as session:
        linked = (
            await session.execute(
                select(PriceAlertMessageEvent.event_id).where(
                    PriceAlertMessageEvent.message_id == message.id
                )
            )
        ).scalars()
        assert set(linked) == set(ids)


async def test_building_twice_creates_nothing_new(scene: Scene) -> None:
    await scene.person("it-manager")
    run = await new_run(scene.sf)
    await flag(scene.sf, run, scene.material, None)

    assert await build(scene.sf, run) == 1
    assert await build(scene.sf, run) == 0


async def test_people_outside_the_pilot_list_are_skipped_with_the_reason(scene: Scene) -> None:
    await scene.person("it-manager", email=f"pilot-{uuid.uuid4().hex[:6]}@example.test")
    run = await new_run(scene.sf)
    await flag(scene.sf, run, scene.material, None)

    assert await build(scene.sf, run, pilot=frozenset({"someone-else@example.test"})) == 1

    (message,) = await stored(scene.sf, scene)
    assert (message.status, message.status_reason) == ("skipped", "pilot")


async def test_a_personal_off_switch_stops_the_card(scene: Scene) -> None:
    manager = await scene.person("it-manager")
    await scene.prefer(manager, is_enabled=False)
    run = await new_run(scene.sf)
    await flag(scene.sf, run, scene.material, None)

    assert await build(scene.sf, run) == 0


def telegram_client(requests: list[httpx.Request]) -> TelegramClient:
    counter = iter(range(1000, 9999))

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": next(counter)}})

    return TelegramClient(
        token=TOKEN, http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond))
    )


async def test_the_sender_attaches_buttons_for_managers_only(scene: Scene) -> None:
    manager = await scene.person("it-manager")
    enterer = await scene.person()
    run = await new_run(scene.sf)
    event = await flag(scene.sf, run, scene.material, enterer)
    await build(scene.sf, run)
    requests: list[httpx.Request] = []
    sender = PriceAlertSender(
        scene.sf, telegram_client(requests), base_url="https://quotify.example"
    )

    outcome = await sender.run_once(NOW + timedelta(seconds=1))

    assert outcome.sent == 2
    assert [r.url.path.rsplit("/", 1)[-1] for r in requests] == ["sendMessage"] * 2
    payloads = [json.loads(r.content) for r in requests]
    with_buttons = [p for p in payloads if "reply_markup" in p]
    assert len(with_buttons) == 1
    buttons = with_buttons[0]["reply_markup"]["inline_keyboard"][0]
    assert [b["callback_data"] for b in buttons] == [f"pa:ok:{event}", f"pa:no:{event}"]
    assert all("disable_notification" not in p for p in payloads)  # thẻ bất thường có âm báo
    assert all("GIÁ BẤT THƯỜNG" in p["text"] for p in payloads)
    assert manager != enterer


async def test_the_sender_renders_a_cluster_summary_with_one_button_row_per_point(
    scene: Scene,
) -> None:
    await scene.person("it-manager")
    run = await new_run(scene.sf)
    for month in (date(2052, 12, 1), date(2053, 1, 1), date(2053, 2, 1)):
        await flag(scene.sf, run, scene.material, None, month=month)
    await build(scene.sf, run)
    requests: list[httpx.Request] = []
    sender = PriceAlertSender(
        scene.sf, telegram_client(requests), base_url="https://quotify.example"
    )

    outcome = await sender.run_once(NOW + timedelta(seconds=1))

    assert outcome.sent == 1
    payload = json.loads(requests[0].content)
    assert payload["text"].startswith("<b>⚠️ 3 GIÁ BẤT THƯỜNG")
    assert len(payload["reply_markup"]["inline_keyboard"]) == 3


async def test_a_cluster_summary_keeps_its_buttons_after_a_failed_send_is_retried(
    scene: Scene,
) -> None:
    await scene.person("it-manager")
    run = await new_run(scene.sf)
    for month in (date(2052, 12, 1), date(2053, 1, 1), date(2053, 2, 1)):
        await flag(scene.sf, run, scene.material, None, month=month)
    await build(scene.sf, run)
    requests: list[httpx.Request] = []
    failing = {"on": True}

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if failing["on"]:
            return httpx.Response(502, text="bad gateway")
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 7}})

    client = TelegramClient(
        token=TOKEN, http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond))
    )
    sender = PriceAlertSender(scene.sf, client, base_url="https://quotify.example")

    first = await sender.run_once(NOW + timedelta(seconds=1))
    failing["on"] = False
    second = await sender.run_once(NOW + timedelta(minutes=5))

    assert (first.retried, second.sent) == (1, 1)
    payload = json.loads(requests[-1].content)
    assert payload["text"].startswith("<b>⚠️ 3 GIÁ BẤT THƯỜNG")
    assert len(payload["reply_markup"]["inline_keyboard"]) == 3
