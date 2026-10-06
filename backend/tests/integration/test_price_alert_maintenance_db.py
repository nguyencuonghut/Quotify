"""Nhắc, hết hạn và dọn dữ liệu của thẻ giá bất thường (Slice 14, L19)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
from price_alert_scene import Scene
from sqlalchemy import select, update
from test_price_alert_anomaly_messages_db import build, flag, new_run, scene  # noqa: F401

from app.integrations.telegram import TelegramClient
from app.models import (
    PriceAlertEvent,
    PriceAlertMessage,
    PriceAlertScanRun,
    PriceAlertSetting,
    Quote,
    QuoteVersion,
)
from app.services.price_alert_anomaly import excluded_line_ids
from app.services.price_alert_maintenance import PriceAlertMaintenanceService, edit_expired_cards

pytestmark = pytest.mark.integration

# Một thứ Hai làm mốc: thứ Hai + 2 ngày làm việc = thứ Tư, + 7 ngày làm việc = thứ Tư tuần sau.
MONDAY = datetime(2052, 6, 3, 3, 0, tzinfo=UTC)


async def card(
    scene: Scene,  # noqa: F811
    *,
    created: datetime = MONDAY,
    **kwargs: object,
) -> uuid.UUID:
    run = await new_run(scene.sf)
    event_id = await flag(scene.sf, run, scene.material, None, with_line=True, **kwargs)  # type: ignore[arg-type]
    async with scene.sf() as session:
        await session.execute(
            update(PriceAlertEvent).where(PriceAlertEvent.id == event_id).values(created_at=created)
        )
        await session.commit()
    return event_id


async def maintain(scene: Scene, now: datetime):  # type: ignore[no-untyped-def]  # noqa: F811
    async with scene.sf() as session:
        settings = (await session.execute(select(PriceAlertSetting))).scalar_one()
        result = await PriceAlertMaintenanceService(session, seed_user_id=None).remind_and_expire(
            now=now, settings=settings
        )
        await session.commit()
    return result


async def event_row(scene: Scene, event_id: uuid.UUID) -> PriceAlertEvent:  # noqa: F811
    async with scene.sf() as session:
        event = await session.get(PriceAlertEvent, event_id)
        assert event is not None
        return event


async def reminders(scene: Scene) -> list[PriceAlertMessage]:  # noqa: F811
    async with scene.sf() as session:
        return list(
            (
                await session.execute(
                    select(PriceAlertMessage)
                    .where(PriceAlertMessage.user_id.in_(scene.mine))
                    .order_by(PriceAlertMessage.sequence_number)
                )
            ).scalars()
        )


async def test_a_pending_card_gets_one_reminder_after_two_working_days(scene: Scene) -> None:  # noqa: F811
    manager = await scene.person("it-manager")
    event_id = await card(scene)

    await maintain(scene, MONDAY + timedelta(days=2))
    await maintain(scene, MONDAY + timedelta(days=2, hours=3))

    (message,) = await reminders(scene)
    assert (message.user_id, message.kind, message.audience) == (manager, "anomaly", "manager")
    assert message.status == "pending"
    event = await event_row(scene, event_id)
    assert (
        event.reminded_at == MONDAY + timedelta(days=2) and message.created_at == event.reminded_at
    )


async def test_working_days_skip_the_weekend_when_deciding_to_remind(scene: Scene) -> None:  # noqa: F811
    await scene.person("it-manager")
    friday = MONDAY + timedelta(days=4)
    await card(scene, created=friday)

    for days_after, expected in ((2, 0), (3, 0), (4, 1)):  # Chủ nhật, thứ Hai, thứ Ba
        await maintain(scene, friday + timedelta(days=days_after))
        assert len(await reminders(scene)) == expected


async def test_a_card_older_than_seven_working_days_expires_and_stays_excluded(
    scene: Scene,  # noqa: F811
) -> None:
    await scene.person("it-manager")
    event_id = await card(scene)
    attached = await card(scene, price=980, attached_to=event_id)
    saved = await event_row(scene, event_id)

    result = await maintain(scene, MONDAY + timedelta(days=9))

    assert event_id in result.expired_event_ids
    assert (await event_row(scene, event_id)).review_status == "expired"
    assert (await event_row(scene, attached)).review_status == "expired"
    assert await reminders(scene) == []  # hết hạn thì ngừng nhắc
    async with scene.sf() as session:
        assert saved.quote_line_id in await excluded_line_ids(
            session, scene.material, saved.delivery_month
        )


async def test_cards_already_reviewed_are_left_alone(scene: Scene) -> None:  # noqa: F811
    await scene.person("it-manager")
    event_id = await card(scene)
    async with scene.sf() as session:
        await session.execute(
            update(PriceAlertEvent)
            .where(PriceAlertEvent.id == event_id)
            .values(review_status="accepted")
        )
        await session.commit()

    result = await maintain(scene, MONDAY + timedelta(days=9))

    assert result.expired_event_ids == [] and result.reminded == 0
    assert (await event_row(scene, event_id)).review_status == "accepted"


async def test_a_card_of_a_cancelled_quote_is_not_reminded_but_still_expires(
    scene: Scene,  # noqa: F811
) -> None:
    await scene.person("it-manager")
    event_id = await card(scene)
    saved = await event_row(scene, event_id)
    async with scene.sf() as session:
        quote_id = (
            await session.execute(
                select(QuoteVersion.quote_id).where(QuoteVersion.id == saved.quote_version_id)
            )
        ).scalar_one()
        await session.execute(update(Quote).where(Quote.id == quote_id).values(cancelled_at=MONDAY))
        await session.commit()

    await maintain(scene, MONDAY + timedelta(days=2))
    assert await reminders(scene) == []
    await maintain(scene, MONDAY + timedelta(days=9))
    assert (await event_row(scene, event_id)).review_status == "expired"


async def test_cleanup_removes_old_records_but_never_pending_cards_or_unsent_messages(
    scene: Scene,  # noqa: F811
) -> None:
    await scene.person("it-manager")
    # Dùng giờ thật: cleanup xóa cả version đã quét của test khác nếu `now` bị đẩy xa về sau.
    now = datetime.now(UTC)
    old = now - timedelta(days=200)
    pending_card = await card(scene, created=old)
    rejected = await card(scene, created=old)
    fresh = await card(scene, created=now - timedelta(days=1))
    async with scene.sf() as session:
        await session.execute(
            update(PriceAlertEvent)
            .where(PriceAlertEvent.id == rejected)
            .values(review_status="rejected")
        )
        old_run = PriceAlertScanRun(started_at=old)
        session.add(old_run)
        await session.commit()
        old_run_id = old_run.id

    async with scene.sf() as session:
        deleted = await PriceAlertMaintenanceService(session, seed_user_id=None).cleanup(now=now)
        await session.commit()

    assert deleted["events"] >= 1 and deleted["scan_runs"] >= 1
    assert await event_row_or_none(scene, rejected) is None
    assert await event_row_or_none(scene, pending_card) is not None
    assert await event_row_or_none(scene, fresh) is not None
    async with scene.sf() as session:
        assert await session.get(PriceAlertScanRun, old_run_id) is None


async def event_row_or_none(scene: Scene, event_id: uuid.UUID) -> PriceAlertEvent | None:  # noqa: F811
    async with scene.sf() as session:
        return await session.get(PriceAlertEvent, event_id)


async def test_old_unsent_messages_survive_the_cleanup_and_old_sent_ones_do_not(
    scene: Scene,  # noqa: F811
) -> None:
    manager = await scene.person("it-manager")
    now = datetime.now(UTC)
    old = now - timedelta(days=200)
    run = await new_run(scene.sf)
    await flag(scene.sf, run, scene.material, None)
    other = await new_run(scene.sf)
    await flag(scene.sf, other, scene.material, None, month=date(2053, 1, 1))

    await build(scene.sf, run)
    await build(scene.sf, other)
    async with scene.sf() as session:
        ids = list(
            (
                await session.execute(
                    select(PriceAlertMessage.id)
                    .where(PriceAlertMessage.user_id == manager)
                    .order_by(PriceAlertMessage.sequence_number)
                )
            ).scalars()
        )
        await session.execute(
            update(PriceAlertMessage).where(PriceAlertMessage.id.in_(ids)).values(created_at=old)
        )
        await session.execute(
            update(PriceAlertMessage).where(PriceAlertMessage.id == ids[0]).values(status="sent")
        )
        await session.commit()

    async with scene.sf() as session:
        await PriceAlertMaintenanceService(session, seed_user_id=None).cleanup(now=now)
        await session.commit()
        remaining = set((await session.execute(select(PriceAlertMessage.id))).scalars())

    assert ids[0] not in remaining and ids[1] in remaining


async def test_the_message_of_an_expired_card_is_edited_to_say_so_and_loses_its_buttons(
    scene: Scene,  # noqa: F811
) -> None:
    manager = await scene.person("it-manager")
    run = await new_run(scene.sf)
    event_id = await flag(scene.sf, run, scene.material, None, with_line=True)
    await build(scene.sf, run)
    async with scene.sf() as session:
        await session.execute(
            update(PriceAlertMessage)
            .where(PriceAlertMessage.user_id == manager)
            .values(status="sent", telegram_message_id=777)
        )
        await session.execute(
            update(PriceAlertEvent)
            .where(PriceAlertEvent.id == event_id)
            .values(review_status="expired")
        )
        await session.commit()
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "result": True})

    client = TelegramClient(
        token="123456789:AAFakeTokenFakeTokenFakeTokenFake12",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
    )

    edited = await edit_expired_cards(
        scene.sf, client, [event_id], base_url="https://quotify.example"
    )

    assert edited == 1
    payload = json.loads(requests[0].content)
    assert payload["message_id"] == 777 and "hết hạn" in payload["text"]
    assert "reply_markup" not in payload


async def test_the_sender_marks_a_reminder_card_and_keeps_its_buttons(scene: Scene) -> None:  # noqa: F811
    from app.services.price_alert_sender import PriceAlertSender

    await scene.person("it-manager")
    event_id = await card(scene, created=datetime.now(UTC) - timedelta(days=4))
    now = datetime.now(UTC)
    result = await maintain(scene, now)
    assert result.reminded == 1
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 9}})

    client = TelegramClient(
        token="123456789:AAFakeTokenFakeTokenFakeTokenFake12",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
    )
    outcome = await PriceAlertSender(scene.sf, client, base_url="https://q.example").run_once(
        now + timedelta(seconds=1)
    )

    assert outcome.sent == 1
    payload = json.loads(requests[0].content)
    assert payload["text"].startswith("⏰ <b>Nhắc lại:</b>")
    assert payload["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == f"pa:ok:{event_id}"


async def test_the_card_expires_on_the_seventh_working_day_not_the_sixth(scene: Scene) -> None:  # noqa: F811
    await scene.person("it-manager")
    event_id = await card(scene)

    await maintain(scene, MONDAY + timedelta(days=8))  # thứ Ba tuần sau: ngày làm việc thứ 6
    assert (await event_row(scene, event_id)).review_status == "pending"

    await maintain(scene, MONDAY + timedelta(days=9))  # thứ Tư: ngày làm việc thứ 7
    assert (await event_row(scene, event_id)).review_status == "expired"


async def test_reminders_wait_for_a_working_day_but_expiry_does_not(scene: Scene) -> None:  # noqa: F811
    await scene.person("it-manager")
    friday = MONDAY + timedelta(days=4)
    await card(scene, created=friday - timedelta(days=7))  # đã quá 2 ngày làm việc vào cuối tuần

    result = await maintain(scene, friday + timedelta(days=1))  # thứ Bảy

    assert result.reminded == 0 and await reminders(scene) == []
    assert (await maintain(scene, friday + timedelta(days=3))).reminded == 1  # thứ Hai


async def test_only_the_cards_that_were_reminded_get_marked_as_reminded(scene: Scene) -> None:  # noqa: F811
    await scene.person("it-manager")
    due = await card(scene)
    fresh = await card(scene, created=MONDAY + timedelta(days=2), price=990)

    result = await maintain(scene, MONDAY + timedelta(days=2, hours=2))

    assert result.reminded == 1
    assert (await event_row(scene, due)).reminded_at is not None
    assert (await event_row(scene, fresh)).reminded_at is None
