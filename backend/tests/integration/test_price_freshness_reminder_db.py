"""Nhắc cập nhật giá theo vật tư trên PostgreSQL thật (Telegram 1D, Slice 5)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest
from db_helpers import build_account, create_material, create_user, insert_rows, next_telegram_id
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
    PriceAlertMessage,
    PriceAlertMessageMaterial,
)

pytestmark = pytest.mark.integration


async def _account(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[uuid.UUID, uuid.UUID]:
    user_id = await create_user(session_factory)
    account = build_account(user_id, next_telegram_id())
    await insert_rows(session_factory, account)
    return user_id, account.id


def _message(user_id: uuid.UUID, account_id: uuid.UUID, **overrides: object) -> PriceAlertMessage:
    values: dict[str, object] = {
        "user_id": user_id,
        "telegram_account_id": account_id,
        "material_id": None,
        "local_date": date(2054, 3, 4),
        "scan_run_id": None,
        "kind": "freshness",
        "status": "pending",
        "created_at": datetime(2054, 3, 4, 2, 0, tzinfo=UTC),
    }
    return PriceAlertMessage(**{**values, **overrides})


@pytest.mark.asyncio
async def test_a_freshness_message_needs_no_material_but_only_one_per_user_and_day(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id, account_id = await _account(session_factory)
    await insert_rows(session_factory, _message(user_id, account_id))

    with pytest.raises(IntegrityError):
        await insert_rows(session_factory, _message(user_id, account_id))

    # Ngày khác hoặc người khác vẫn được.
    await insert_rows(session_factory, _message(user_id, account_id, local_date=date(2054, 3, 5)))
    other_user, other_account = await _account(session_factory)
    await insert_rows(session_factory, _message(other_user, other_account))


@pytest.mark.asyncio
async def test_other_kinds_keep_their_rules(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id, account_id = await _account(session_factory)

    with pytest.raises(IntegrityError):
        await insert_rows(session_factory, _message(user_id, account_id, kind="change"))
    with pytest.raises(IntegrityError):
        await insert_rows(session_factory, _message(user_id, account_id, kind="bogus"))
    material = await create_material(session_factory)
    await insert_rows(
        session_factory, _message(user_id, account_id, kind="change", material_id=material)
    )


@pytest.mark.asyncio
async def test_message_materials_are_removed_with_their_message_and_keyed_per_material(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id, account_id = await _account(session_factory)
    material = await create_material(session_factory)
    message = _message(user_id, account_id)
    await insert_rows(session_factory, message)
    row = PriceAlertMessageMaterial(
        message_id=message.id,
        material_id=material,
        age_days=18,
        interval_days=14,
        last_received_date=date(2054, 2, 14),
        last_enterer_id=user_id,
    )
    await insert_rows(session_factory, row)

    with pytest.raises(IntegrityError):
        await insert_rows(
            session_factory,
            PriceAlertMessageMaterial(
                message_id=message.id,
                material_id=material,
                age_days=1,
                interval_days=7,
                last_received_date=date(2054, 3, 3),
            ),
        )
    async with session_factory() as session:
        await session.execute(
            text("delete from price_alert_messages where id = :id"), {"id": message.id}
        )
        await session.commit()
        left = (
            await session.execute(
                select(PriceAlertMessageMaterial).where(
                    PriceAlertMessageMaterial.message_id == message.id
                )
            )
        ).all()
    assert left == []


@pytest.mark.asyncio
async def test_settings_and_state_have_the_freshness_columns_with_safe_defaults(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        rows = (
            await session.execute(
                text(
                    "select table_name, column_name, column_default, is_nullable "
                    "from information_schema.columns "
                    "where column_name in "
                    "('freshness_enabled','freshness_hour_local','last_freshness_local_date')"
                )
            )
        ).all()

    found = {(r.table_name, r.column_name): (r.column_default, r.is_nullable) for r in rows}
    assert found[("price_alert_settings", "freshness_enabled")] == ("false", "NO")
    assert found[("price_alert_settings", "freshness_hour_local")] == ("'9'::smallint", "NO")
    assert found[("price_alert_scan_state", "last_freshness_local_date")][1] == "YES"


@pytest.mark.asyncio
async def test_freshness_hour_must_be_a_valid_hour(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(text("update price_alert_settings set freshness_hour_local = 24"))
        await session.rollback()


# --- xếp tin nhắc (Slice 5) -----------------------------------------------------------------

from datetime import timedelta  # noqa: E402

from db_helpers import create_priced_line, ensure_role  # noqa: E402
from price_alert_scene import Scene  # noqa: E402
from sqlalchemy import delete, update  # noqa: E402

from app.models import (  # noqa: E402
    Material,
    PriceAlertScanState,
    PriceAlertSetting,
    PriceFreshnessMaterial,
    TelegramAccount,
)
from app.services.price_alert_candidates import BUSINESS_TIMEZONE  # noqa: E402
from app.services.price_freshness_reminder import (  # noqa: E402
    FRESHNESS_ADVISORY_LOCK_KEY,
    PriceFreshnessReminderService,
)

WED = date(2054, 3, 4)


def vn(day: date, hour: int = 9, minute: int = 20) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=BUSINESS_TIMEZONE)


@pytest.fixture
async def scene(session_factory: async_sessionmaker[AsyncSession]) -> Scene:
    await ensure_role(session_factory, "it-manager", ["price_alerts.receive_all"])
    async with session_factory() as session:
        await session.execute(
            update(PriceAlertSetting).values(
                is_enabled=True,
                freshness_enabled=True,
                freshness_hour_local=9,
                staff_lookback_days=90,
            )
        )
        await session.execute(update(PriceAlertScanState).values(last_freshness_local_date=None))
        await session.execute(delete(PriceFreshnessMaterial))
        await session.execute(
            update(PriceAlertMessage)
            .where(PriceAlertMessage.status.in_(("pending", "sending")))
            .values(status="failed", status_reason="test_cleanup")
        )
        await session.execute(update(TelegramAccount).values(status="revoked"))
        await session.commit()
    return await Scene(session_factory).setup()


async def watch(
    scene: Scene, material: uuid.UUID, interval: int = 7, *, watched: bool = True
) -> None:
    await insert_rows(
        scene.sf,
        PriceFreshnessMaterial(
            material_id=material, is_watched=watched, expected_interval_days=interval
        ),
    )


async def price(
    scene: Scene, material: uuid.UUID, received: date, user_id: uuid.UUID | None
) -> None:
    await create_priced_line(
        scene.sf, material_id=material, price=100, received_date=received, created_by_id=user_id
    )


async def run_at(
    scene: Scene,
    now: datetime,
    **kwargs: object,
) -> object:
    async with scene.sf() as session:
        settings = (await session.execute(select(PriceAlertSetting))).scalar_one()
        result = await PriceFreshnessReminderService(session).run_once(
            now=now,
            settings=settings,
            seed_user_id=None,
            **kwargs,  # type: ignore[arg-type]
        )
        await session.commit()
    return result


async def messages(
    scene: Scene,
) -> dict[uuid.UUID, tuple[PriceAlertMessage, list[PriceAlertMessageMaterial]]]:
    async with scene.sf() as session:
        rows = (
            (
                await session.execute(
                    select(PriceAlertMessage).where(
                        PriceAlertMessage.kind == "freshness",
                        PriceAlertMessage.user_id.in_(scene.mine),
                    )
                )
            )
            .scalars()
            .all()
        )
        out = {}
        for message in rows:
            links = (
                (
                    await session.execute(
                        select(PriceAlertMessageMaterial).where(
                            PriceAlertMessageMaterial.message_id == message.id
                        )
                    )
                )
                .scalars()
                .all()
            )
            out[message.user_id] = (message, list(links))
        return out


async def state_date(scene: Scene) -> date | None:
    async with scene.sf() as session:
        return (
            await session.execute(select(PriceAlertScanState.last_freshness_local_date))
        ).scalar_one()


async def test_reminders_go_to_a_manager_and_the_staff_who_entered_the_overdue_material(
    scene: Scene,
) -> None:
    overdue, on_time, still_early = (
        scene.material,
        await create_material(scene.sf),
        await create_material(scene.sf),
    )
    manager = await scene.person("it-manager")
    staff = await scene.person()
    for material in (overdue, on_time, still_early):
        await watch(scene, material)
    await price(
        scene, overdue, date(2054, 2, 24), staff
    )  # hạn 03/03, hôm nay là ngày làm việc thứ 1
    await price(scene, on_time, date(2054, 2, 26), staff)  # hạn 03/05: còn hạn
    await price(
        scene, still_early, date(2054, 2, 23), staff
    )  # hạn 03/02: ngày thứ 2, chưa tới nhịp

    await run_at(scene, vn(WED))

    found = await messages(scene)
    assert set(found) == {manager, staff}
    for user_id in (manager, staff):
        message, links = found[user_id]
        assert (message.kind, message.status, message.local_date) == ("freshness", "pending", WED)
        assert message.material_id is None and message.scan_run_id is None
        assert message.audience is None and message.digest_kind is None
        assert [link.material_id for link in links] == [overdue]
        assert (links[0].age_days, links[0].interval_days) == (8, 7)
        assert links[0].last_received_date == date(2054, 2, 24)
        assert links[0].last_enterer_id == staff
    assert await state_date(scene) == WED


async def test_running_again_the_same_day_creates_nothing_more(scene: Scene) -> None:
    manager = await scene.person("it-manager")
    await watch(scene, scene.material)
    await price(scene, scene.material, date(2054, 2, 24), None)
    await run_at(scene, vn(WED))

    again = await run_at(scene, vn(WED, 11, 30))

    assert again.skipped == "already_sent"  # type: ignore[attr-defined]
    assert len(await messages(scene)) == 1
    assert manager in await messages(scene)


async def test_the_unique_index_holds_even_if_the_state_date_is_lost(scene: Scene) -> None:
    await scene.person("it-manager")
    await watch(scene, scene.material)
    await price(scene, scene.material, date(2054, 2, 24), None)
    await run_at(scene, vn(WED))
    async with scene.sf() as session:
        await session.execute(update(PriceAlertScanState).values(last_freshness_local_date=None))
        await session.commit()

    await run_at(scene, vn(WED, 10, 20))

    assert len(await messages(scene)) == 1


async def test_nothing_is_created_before_the_hour_and_a_late_worker_still_sends_that_day(
    scene: Scene,
) -> None:
    await scene.person("it-manager")
    await watch(scene, scene.material)
    await price(scene, scene.material, date(2054, 2, 24), None)

    early = await run_at(scene, vn(WED, 8, 50))
    assert early.skipped == "not_due"  # type: ignore[attr-defined]
    assert await messages(scene) == {}
    assert await state_date(scene) is None

    await run_at(scene, vn(WED, 11, 30))
    assert len(await messages(scene)) == 1


async def test_weekends_are_skipped_and_monday_after_a_friday_deadline_is_the_first_day(
    scene: Scene,
) -> None:
    await scene.person("it-manager")
    await watch(scene, scene.material)
    await price(scene, scene.material, date(2054, 2, 27), None)  # thứ Sáu; hạn thứ Sáu 03/06

    saturday = await run_at(scene, vn(date(2054, 3, 7)))
    assert saturday.skipped == "not_working_day"  # type: ignore[attr-defined]
    assert await state_date(scene) is None
    assert await messages(scene) == {}

    await run_at(scene, vn(date(2054, 3, 9)))  # thứ Hai: ngày làm việc đầu tiên sau hạn
    assert len(await messages(scene)) == 1


async def test_no_overdue_material_creates_no_message_but_marks_the_day_done(scene: Scene) -> None:
    await scene.person("it-manager")
    await watch(scene, scene.material)
    await price(scene, scene.material, WED - timedelta(days=2), None)

    result = await run_at(scene, vn(WED))

    assert await messages(scene) == {}
    assert result.messages_created == 0  # type: ignore[attr-defined]
    assert await state_date(scene) == WED


@pytest.mark.parametrize(
    ("days_since_last", "expected"),
    # Cuối tuần không phải ngày làm việc nên số ngày dừng ở 3 qua d = 10..12 và ở 13 qua d = 24..26.
    [
        (7, 0),
        (8, 1),
        (9, 0),
        (10, 0),
        (13, 1),
        (14, 0),
        (16, 1),
        (21, 1),
        (24, 1),
        (27, 0),
        (31, 0),
    ],
)
async def test_the_cadence_repeats_every_three_working_days_up_to_five_times(
    scene: Scene,
    days_since_last: int,
    expected: int,
) -> None:
    # Ngày hôm nay luôn là thứ Tư 04/03; chu kỳ 7 ngày. `days_since_last` đổi ngày nhận cuối.
    await scene.person("it-manager")
    await watch(scene, scene.material)
    await price(scene, scene.material, WED - timedelta(days=days_since_last), None)

    await run_at(scene, vn(WED))

    assert len(await messages(scene)) == expected


async def test_materials_that_are_not_watched_inactive_or_never_priced_are_never_reminded(
    scene: Scene,
) -> None:
    await scene.person("it-manager")
    unwatched = await create_material(scene.sf)
    turned_off = await create_material(scene.sf)
    inactive = await create_material(scene.sf)
    never = await create_material(scene.sf)
    await watch(scene, turned_off, watched=False)
    await watch(scene, inactive)
    await watch(scene, never)
    for material in (unwatched, turned_off, inactive):
        await price(scene, material, date(2054, 2, 24), None)
    async with scene.sf() as session:
        await session.execute(
            update(Material).where(Material.id == inactive).values(status="inactive")
        )
        await session.commit()

    await run_at(scene, vn(WED))

    assert await messages(scene) == {}


async def test_a_new_price_ends_the_overdue_streak(scene: Scene) -> None:
    await scene.person("it-manager")
    await watch(scene, scene.material)
    await price(scene, scene.material, date(2054, 2, 24), None)
    await price(scene, scene.material, WED - timedelta(days=1), None)

    await run_at(scene, vn(WED))

    assert await messages(scene) == {}


async def test_the_pilot_list_and_personal_switch_are_respected(scene: Scene) -> None:
    pilot = await scene.person("it-manager", email="pilot-1d-queue@example.com")
    await scene.person("it-manager")
    muted = await scene.person("it-manager", email="pilot-1d-muted@example.com")
    await scene.prefer(muted, is_enabled=False)
    await watch(scene, scene.material)
    await price(scene, scene.material, date(2054, 2, 24), None)

    await run_at(
        scene,
        vn(WED),
        pilot_emails=frozenset({"pilot-1d-queue@example.com", "pilot-1d-muted@example.com"}),
    )

    assert set(await messages(scene)) == {pilot}


async def test_the_advisory_lock_key_is_distinct_from_scan_and_digest() -> None:
    assert FRESHNESS_ADVISORY_LOCK_KEY == 7_620_261_007


# --- gửi tin nhắc (sender) ------------------------------------------------------------------

import json  # noqa: E402

import httpx  # noqa: E402

from app.integrations.telegram import TelegramClient  # noqa: E402
from app.services.price_alert_digest import PriceAlertDigestService  # noqa: E402
from app.services.price_alert_sender import PriceAlertSender  # noqa: E402


async def deliver(
    scene: Scene,
    now: datetime,
    **kwargs: object,
) -> tuple[object, list[dict[str, object]]]:
    sent: list[dict[str, object]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 21}})

    client = TelegramClient(
        token="123456789:AAFakeTokenFakeTokenFakeTokenFake12",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
    )
    outcome = await PriceAlertSender(
        scene.sf,
        client,
        base_url="https://q.example",
        **kwargs,  # type: ignore[arg-type]
    ).run_once(now)
    return outcome, sent


async def test_the_sender_delivers_one_loud_reminder_listing_only_the_recipients_materials(
    scene: Scene,
) -> None:
    other = await create_material(scene.sf, name="Khô đậu tương thử")
    await scene.person("it-manager")
    staff = await scene.person()
    await watch(scene, scene.material)
    await watch(scene, other, 14)
    await price(scene, scene.material, date(2054, 2, 24), staff)
    await price(scene, other, date(2054, 2, 17), None)  # quá 14 ngày, k = 1
    now = vn(WED)
    await run_at(scene, now)

    outcome, sent = await deliver(scene, now + timedelta(seconds=1))

    assert outcome.sent == 2  # type: ignore[attr-defined]
    by_chat = {int(p["chat_id"]): str(p["text"]) for p in sent}  # type: ignore[call-overload]
    assert len(by_chat) == 2
    texts = sorted(by_chat.values(), key=len)
    # Nhân viên chỉ thấy vật tư mình nhập; trưởng phòng thấy cả hai.
    assert texts[0].count("•") == 1 and texts[1].count("•") == 2
    assert "Khô đậu tương thử — 15 ngày (chu kỳ 14)" in texts[1]
    assert all("<b>Vật tư chưa có giá mới" in t and "04/03" in t for t in texts)
    assert all("disable_notification" not in p and "reply_markup" not in p for p in sent)


async def test_a_reminder_without_any_material_left_is_not_sent(scene: Scene) -> None:
    await scene.person("it-manager")
    await watch(scene, scene.material)
    await price(scene, scene.material, date(2054, 2, 24), None)
    now = vn(WED)
    await run_at(scene, now)
    async with scene.sf() as session:
        await session.execute(delete(PriceAlertMessageMaterial))
        await session.commit()

    outcome, sent = await deliver(scene, now + timedelta(seconds=1))

    assert sent == []
    assert outcome.failed == 1  # type: ignore[attr-defined]


async def test_the_sender_skips_people_outside_the_pilot_list(scene: Scene) -> None:
    await scene.person("it-manager", email="not-in-pilot-1d@example.com")
    await watch(scene, scene.material)
    await price(scene, scene.material, date(2054, 2, 24), None)
    now = vn(WED)
    await run_at(scene, now)

    outcome, sent = await deliver(
        scene, now + timedelta(seconds=1), pilot_emails=frozenset({"someone-else@example.com"})
    )

    assert sent == []
    assert outcome.skipped == 1  # type: ignore[attr-defined]


async def test_the_daily_digest_job_leaves_freshness_messages_alone(scene: Scene) -> None:
    manager = await scene.person("it-manager")
    await watch(scene, scene.material)
    await price(scene, scene.material, date(2054, 2, 24), None)
    now = vn(WED)
    await run_at(scene, now)
    async with scene.sf() as session:
        settings = (await session.execute(select(PriceAlertSetting))).scalar_one()
        await PriceAlertDigestService(session).run_once(now=now, settings=settings)
        await session.commit()

    message, links = (await messages(scene))[manager]

    assert (message.status, message.status_reason) == ("pending", None)
    assert len(links) == 1


# --- cron của worker ------------------------------------------------------------------------

from types import SimpleNamespace  # noqa: E402

import app.worker as worker  # noqa: E402


class _FixedClock(datetime):
    @classmethod
    def now(cls, tz: object = None) -> datetime:  # type: ignore[override]
        return vn(WED, 9, 20).astimezone(tz)  # type: ignore[arg-type]


@pytest.fixture
def worker_env(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    env = SimpleNamespace(
        telegram_enabled=True,
        auth_seed_admin_email="seed-1d-none@example.invalid",
        price_alert_recipient_email_set=frozenset(),
    )
    monkeypatch.setattr(worker, "get_settings", lambda: env)
    monkeypatch.setattr(worker, "datetime", _FixedClock)
    return env


async def _overdue_scene(scene: Scene) -> None:
    await scene.person("it-manager")
    await watch(scene, scene.material)
    await price(scene, scene.material, date(2054, 2, 24), None)


async def test_the_cron_job_queues_the_reminders_when_everything_is_on(
    scene: Scene,
    worker_env: SimpleNamespace,
) -> None:
    await _overdue_scene(scene)

    await worker.send_price_alert_freshness({"session_factory": scene.sf})

    assert len(await messages(scene)) == 1


@pytest.mark.parametrize(
    "switch",
    ["telegram", "master", "freshness"],
)
async def test_the_cron_job_does_nothing_when_any_switch_is_off(
    scene: Scene,
    worker_env: SimpleNamespace,
    switch: str,
) -> None:
    await _overdue_scene(scene)
    if switch == "telegram":
        worker_env.telegram_enabled = False
    else:
        column = "is_enabled" if switch == "master" else "freshness_enabled"
        async with scene.sf() as session:
            await session.execute(update(PriceAlertSetting).values(**{column: False}))
            await session.commit()

    await worker.send_price_alert_freshness({"session_factory": scene.sf})

    assert await messages(scene) == {}
    assert await state_date(scene) is None


async def test_the_cron_job_never_reminds_the_seed_account(
    scene: Scene,
    worker_env: SimpleNamespace,
) -> None:
    seed = await scene.person("it-manager", email="seed-1d@example.com")
    worker_env.auth_seed_admin_email = "seed-1d@example.com"
    await watch(scene, scene.material)
    await price(scene, scene.material, date(2054, 2, 24), None)

    await worker.send_price_alert_freshness({"session_factory": scene.sf})

    assert seed not in await messages(scene)
