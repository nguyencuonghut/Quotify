"""Gửi tin biến động giá tới Telegram (giả lập bằng MockTransport) trên PostgreSQL thật (L25)."""

from __future__ import annotations

import asyncio
import io
import json
import logging
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
from db_helpers import create_confirmed_quote_version, create_priced_line, ensure_role
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
    UserStatus,
)
from app.services.price_alert_message_view import load_message_view
from app.services.price_alert_sender import MAX_ATTEMPTS, PriceAlertSender

pytestmark = pytest.mark.integration

TOKEN = "123456789:AAFakeTokenFakeTokenFakeTokenFake12"
BASE_URL = "https://quotify.example"
NOW = datetime(2049, 4, 5, 3, 0, tzinfo=UTC)
NEW_DAY = date(2049, 4, 5)
MONTH = date(2049, 12, 1)

Handler = Callable[[httpx.Request], httpx.Response]


class Telegram:
    """Telegram giả: ghi lại request, trả lời theo `handler` (mặc định luôn thành công)."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.handler: Handler = self.ok
        self._ids = iter(range(1000, 9999))

    def ok(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True, "result": {"message_id": next(self._ids)}})

    def methods(self) -> list[str]:
        return [r.url.path.rsplit("/", 1)[-1] for r in self.requests]

    def client(self) -> tuple[TelegramClient, httpx.AsyncClient]:
        def respond(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            return self.handler(request)

        http = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        return TelegramClient(token=TOKEN, http_client=http), http


def error(code: int, description: str, **extra: object) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            code, json={"ok": False, "error_code": code, "description": description, **extra}
        )

    return handler


@pytest.fixture
async def telegram() -> AsyncIterator[Telegram]:
    yield Telegram()


@pytest.fixture
async def scene(session_factory: async_sessionmaker[AsyncSession]) -> Scene:
    await ensure_role(session_factory, "it-manager", ["price_alerts.receive_all"])
    async with session_factory() as session:
        # Các tin còn dang dở của test khác không được lọt vào lô gửi của test này.
        await session.execute(
            update(PriceAlertMessage)
            .where(PriceAlertMessage.status.in_(("pending", "sending")))
            .values(status="failed", status_reason="test_cleanup")
        )
        await session.execute(update(PriceAlertSetting).values(is_enabled=True))
        await session.commit()
    return await Scene(session_factory).setup()


async def make_message(
    scene: Scene,
    *,
    with_chart: bool = True,
    kind: str = "change",
    **person_kwargs: object,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Một tin `pending` cho một trưởng phòng đã liên kết; trả `(message_id, user_id)`."""
    sf = scene.sf
    user = await scene.person("it-manager", **person_kwargs)  # type: ignore[arg-type]
    if with_chart:
        for offset, price in {-3: 7900, -2: 7720, -1: 7800, 0: 8150}.items():
            await create_priced_line(
                sf,
                material_id=scene.material,
                price=price,
                received_date=NEW_DAY + timedelta(days=offset),
                delivery_month=MONTH,
            )
    version = await create_confirmed_quote_version(sf)
    async with sf() as session:
        run = PriceAlertScanRun(started_at=NOW)
        session.add(run)
        await session.flush()
        account_id = (
            await session.execute(select(TelegramAccount.id).where(TelegramAccount.user_id == user))
        ).scalar_one_or_none()
        event = PriceAlertEvent(
            scan_run_id=run.id,
            quote_version_id=version,
            material_id=scene.material,
            delivery_month=MONTH,
            kind="change",
            direction="up",
            level="medium",
            rule="R2",
            percent_change=Decimal("5.57"),
            price_new=Decimal(8150),
            price_ref=Decimal(7720),
            received_date_new=NEW_DAY,
            received_date_ref=NEW_DAY - timedelta(days=2),
            window_min=Decimal(7720),
            window_max=Decimal(7900),
            window_min_date=NEW_DAY - timedelta(days=2),
            window_max_date=NEW_DAY - timedelta(days=3),
            reference_point_count=3,
        )
        session.add(event)
        await session.flush()
        message = PriceAlertMessage(
            user_id=user,
            telegram_account_id=account_id,
            material_id=None if kind == "digest" else scene.material,
            local_date=NEW_DAY,
            scan_run_id=run.id,
            kind=kind,
            level_max="medium",
            direction="up",
            status="pending",
            created_at=NOW,
        )
        session.add(message)
        await session.flush()
        session.add(PriceAlertMessageEvent(message_id=message.id, event_id=event.id))
        await session.commit()
        return message.id, user


async def sender_for(
    sf: async_sessionmaker[AsyncSession], telegram: Telegram, **kwargs: object
) -> PriceAlertSender:
    client, _http = telegram.client()
    return PriceAlertSender(sf, client, base_url=BASE_URL, **kwargs)  # type: ignore[arg-type]


async def row(sf: async_sessionmaker[AsyncSession], message_id: uuid.UUID) -> PriceAlertMessage:
    async with sf() as session:
        message = await session.get(PriceAlertMessage, message_id)
        assert message is not None
        return message


async def test_a_pending_message_is_sent_as_a_photo_then_a_detail_text(
    scene: Scene, telegram: Telegram
) -> None:
    message_id, _ = await make_message(scene)
    sender = await sender_for(scene.sf, telegram)

    outcome = await sender.run_once(NOW)

    assert (outcome.claimed, outcome.sent) == (1, 1)
    assert telegram.methods() == ["sendPhoto", "sendMessage"]
    saved = await row(scene.sf, message_id)
    assert saved.status == "sent"
    assert saved.sent_at is not None and abs((saved.sent_at - NOW).total_seconds()) < 2
    assert saved.telegram_message_id is not None and saved.attempts == 1
    assert saved.lease_until is None
    photo, text = telegram.requests
    assert b"TRUNG B" in photo.content  # tiêu đề trong caption (HTML, tiếng Việt)
    payload = json.loads(text.content)
    assert payload["parse_mode"] == "HTML"
    assert "/quotes/" in payload["text"]
    assert payload["disable_notification"] is True  # ảnh đã báo, tin chi tiết gửi im lặng


async def test_without_chart_data_only_the_text_is_sent(scene: Scene, telegram: Telegram) -> None:
    message_id, _ = await make_message(scene, with_chart=False)

    await (await sender_for(scene.sf, telegram)).run_once(NOW)

    assert telegram.methods() == ["sendMessage"]
    assert "disable_notification" not in json.loads(telegram.requests[0].content)
    assert (await row(scene.sf, message_id)).status == "sent"


async def test_the_chart_image_is_a_decodable_png(scene: Scene, telegram: Telegram) -> None:
    from PIL import Image

    await make_message(scene)
    await (await sender_for(scene.sf, telegram)).run_once(NOW)

    request = telegram.requests[0]
    start = request.content.index(b"\x89PNG")
    end = request.content.index(b"IEND") + 8
    assert Image.open(io.BytesIO(request.content[start:end])).size == (900, 500)


async def test_a_rate_limit_waits_for_retry_after_then_sends(
    scene: Scene, telegram: Telegram
) -> None:
    message_id, _ = await make_message(scene)
    sender = await sender_for(scene.sf, telegram)
    telegram.handler = error(429, "Too Many Requests", parameters={"retry_after": 7})

    first = await sender.run_once(NOW)
    saved = await row(scene.sf, message_id)
    assert (first.retried, saved.status, saved.last_error) == (1, "pending", "rate_limit")
    assert saved.lease_until is not None
    assert abs((saved.lease_until - NOW - timedelta(seconds=8)).total_seconds()) < 2

    telegram.handler = telegram.ok
    too_early = await sender.run_once(NOW + timedelta(seconds=5))
    on_time = await sender.run_once(NOW + timedelta(seconds=9))

    assert (too_early.claimed, on_time.sent) == (0, 1)
    assert (await row(scene.sf, message_id)).status == "sent"


async def test_a_blocked_bot_blocks_the_account_and_skips_every_message_of_the_user(
    scene: Scene, telegram: Telegram
) -> None:
    first_id, user = await make_message(scene, with_chart=False)
    telegram.handler = error(403, "Forbidden: bot was blocked by the user")
    sender = await sender_for(scene.sf, telegram)

    await sender.run_once(NOW)

    saved = await row(scene.sf, first_id)
    assert (saved.status, saved.status_reason) == ("skipped", "blocked")
    async with scene.sf() as session:
        account = (
            await session.execute(select(TelegramAccount).where(TelegramAccount.user_id == user))
        ).scalar_one()
    assert account.status == "blocked"

    # Tin khác của cùng người: tài khoản đã bị chặn nên bị bỏ qua, không gọi Telegram nữa.
    async with scene.sf() as session:
        second = PriceAlertMessage(
            user_id=user,
            telegram_account_id=account.id,
            material_id=scene.material,
            local_date=NEW_DAY,
            kind="change",
            level_max="medium",
            direction="up",
            status="pending",
            created_at=NOW,
        )
        session.add(second)
        await session.commit()
        second_id = second.id
    calls = len(telegram.requests)
    await sender.run_once(NOW + timedelta(minutes=1))
    assert len(telegram.requests) == calls
    assert (await row(scene.sf, second_id)).status_reason == "ineligible"


async def test_a_rejected_message_fails_for_good(scene: Scene, telegram: Telegram) -> None:
    message_id, _ = await make_message(scene, with_chart=False)
    telegram.handler = error(400, "Bad Request: can't parse entities: Unsupported start tag")
    sender = await sender_for(scene.sf, telegram)

    await sender.run_once(NOW)
    calls = len(telegram.requests)
    await sender.run_once(NOW + timedelta(hours=1))

    saved = await row(scene.sf, message_id)
    assert (saved.status, saved.status_reason) == ("failed", "telegram_rejected")
    assert "can't parse entities" in (saved.last_error or "")
    assert len(telegram.requests) == calls


async def test_network_errors_back_off_then_fail_after_the_attempt_limit(
    scene: Scene, telegram: Telegram, caplog: pytest.LogCaptureFixture
) -> None:
    message_id, _ = await make_message(scene, with_chart=False)

    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"boom {request.url}")

    telegram.handler = boom
    sender = await sender_for(scene.sf, telegram)
    now = NOW
    delays = []
    with caplog.at_level(logging.DEBUG):
        for attempt in range(1, MAX_ATTEMPTS + 1):
            outcome = await sender.run_once(now)
            saved = await row(scene.sf, message_id)
            if attempt < MAX_ATTEMPTS:
                assert (outcome.retried, saved.status) == (1, "pending")
                assert saved.lease_until is not None
                delays.append((saved.lease_until - now).total_seconds())
                now = saved.lease_until
    saved = await row(scene.sf, message_id)
    assert (saved.status, saved.status_reason, saved.attempts) == (
        "failed",
        "max_attempts",
        MAX_ATTEMPTS,
    )
    assert [round(d) for d in delays] == [30, 60, 120, 240]
    assert TOKEN not in caplog.text
    assert TOKEN not in (saved.last_error or "")


async def test_a_server_error_is_retried(scene: Scene, telegram: Telegram) -> None:
    message_id, _ = await make_message(scene, with_chart=False)
    telegram.handler = error(502, "Bad Gateway")

    outcome = await (await sender_for(scene.sf, telegram)).run_once(NOW)

    assert outcome.retried == 1
    assert (await row(scene.sf, message_id)).status == "pending"


async def test_when_the_text_fails_after_the_photo_the_retry_does_not_resend_the_photo(
    scene: Scene, telegram: Telegram
) -> None:
    message_id, _ = await make_message(scene)
    sender = await sender_for(scene.sf, telegram)
    calls = {"n": 0}

    def photo_ok_text_down(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if request.url.path.endswith("/sendPhoto"):
            return telegram.ok(request)
        return error(502, "Bad Gateway")(request)

    telegram.handler = photo_ok_text_down
    await sender.run_once(NOW)
    saved = await row(scene.sf, message_id)
    assert (saved.status, saved.status_reason) == ("pending", "photo_sent")

    telegram.handler = telegram.ok
    await sender.run_once(saved.lease_until or NOW)

    assert telegram.methods() == ["sendPhoto", "sendMessage", "sendMessage"]
    assert (await row(scene.sf, message_id)).status == "sent"


async def test_two_senders_at_once_send_a_message_only_once(
    scene: Scene, telegram: Telegram
) -> None:
    message_id, _ = await make_message(scene, with_chart=False)

    async def slow(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.3)
        return telegram.ok(request)

    client_a, _ = telegram.client()
    client_b, _ = telegram.client()

    async def slow_transport(request: httpx.Request) -> httpx.Response:
        telegram.requests.append(request)
        return await slow(request)

    http = httpx.AsyncClient(transport=httpx.MockTransport(slow_transport))
    sender_a = PriceAlertSender(
        scene.sf, TelegramClient(token=TOKEN, http_client=http), base_url=BASE_URL
    )
    sender_b = PriceAlertSender(
        scene.sf, TelegramClient(token=TOKEN, http_client=http), base_url=BASE_URL
    )
    del client_a, client_b

    first, second = await asyncio.gather(sender_a.run_once(NOW), sender_b.run_once(NOW))

    assert first.claimed + second.claimed == 1
    assert telegram.methods().count("sendMessage") == 1
    assert (await row(scene.sf, message_id)).status == "sent"


async def test_a_live_lease_is_respected_and_an_expired_one_is_reclaimed(
    scene: Scene, telegram: Telegram
) -> None:
    message_id, _ = await make_message(scene, with_chart=False)
    async with scene.sf() as session:
        await session.execute(
            update(PriceAlertMessage)
            .where(PriceAlertMessage.id == message_id)
            .values(status="sending", lease_until=NOW + timedelta(minutes=1), attempts=1)
        )
        await session.commit()
    sender = await sender_for(scene.sf, telegram)

    assert (await sender.run_once(NOW)).claimed == 0
    assert (await sender.run_once(NOW + timedelta(minutes=2))).sent == 1


async def test_final_states_are_never_sent_again(scene: Scene, telegram: Telegram) -> None:
    ids = [(await make_message(scene, with_chart=False))[0] for _ in range(3)]
    async with scene.sf() as session:
        for message_id, status in zip(ids, ("sent", "failed", "suppressed"), strict=True):
            await session.execute(
                update(PriceAlertMessage)
                .where(PriceAlertMessage.id == message_id)
                .values(status=status)
            )
        await session.commit()

    outcome = await (await sender_for(scene.sf, telegram)).run_once(NOW)

    assert outcome.claimed == 0 and telegram.requests == []


async def test_nothing_is_sent_while_the_feature_flag_is_off(
    scene: Scene, telegram: Telegram
) -> None:
    message_id, _ = await make_message(scene, with_chart=False)
    async with scene.sf() as session:
        await session.execute(update(PriceAlertSetting).values(is_enabled=False))
        await session.commit()

    outcome = await (await sender_for(scene.sf, telegram)).run_once(NOW)

    assert outcome.claimed == 0 and telegram.requests == []
    assert (await row(scene.sf, message_id)).status == "pending"


async def test_an_inactive_user_is_skipped_without_calling_telegram(
    scene: Scene, telegram: Telegram
) -> None:
    message_id, _ = await make_message(scene, with_chart=False, status=UserStatus.INACTIVE)

    outcome = await (await sender_for(scene.sf, telegram)).run_once(NOW)

    assert outcome.skipped == 1 and telegram.requests == []
    assert (await row(scene.sf, message_id)).status_reason == "ineligible"


async def test_the_overflow_summary_is_sent_as_a_short_text(
    scene: Scene, telegram: Telegram
) -> None:
    message_id, _ = await make_message(scene, kind="digest", with_chart=False)

    await (await sender_for(scene.sf, telegram)).run_once(NOW)

    assert telegram.methods() == ["sendMessage"]
    text = json.loads(telegram.requests[0].content)["text"]
    assert "Còn 1 thay đổi giá khác" in text and f"{BASE_URL}/quotes" in text
    assert (await row(scene.sf, message_id)).status == "sent"


async def test_a_failed_send_never_changes_the_events_or_other_messages(
    scene: Scene, telegram: Telegram
) -> None:
    message_id, user = await make_message(scene, with_chart=False)
    telegram.handler = error(400, "Bad Request")
    async with scene.sf() as session:
        events_before = (
            await session.execute(select(PriceAlertEvent.id, PriceAlertEvent.level))
        ).all()

    await (await sender_for(scene.sf, telegram)).run_once(NOW)

    async with scene.sf() as session:
        events_after = (
            await session.execute(select(PriceAlertEvent.id, PriceAlertEvent.level))
        ).all()
    assert sorted(events_before) == sorted(events_after)
    assert (await row(scene.sf, message_id)).status == "failed"


async def test_an_unexpected_error_in_one_message_does_not_sink_the_rest_of_the_batch(
    scene: Scene, telegram: Telegram, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, _ = await make_message(scene, with_chart=False)
    second, _ = await make_message(scene, with_chart=False)
    real = load_message_view

    async def poisoned(session: AsyncSession, message_id: uuid.UUID, settings: object) -> object:
        if message_id == first:
            raise RuntimeError("dữ liệu hỏng")
        return await real(session, message_id, settings)  # type: ignore[arg-type]

    monkeypatch.setattr("app.services.price_alert_sender.load_message_view", poisoned)
    sender = await sender_for(scene.sf, telegram)

    outcome = await sender.run_once(NOW)

    assert (outcome.claimed, outcome.sent, outcome.retried) == (2, 1, 1)
    assert (await row(scene.sf, second)).status == "sent"
    saved = await row(scene.sf, first)
    assert (saved.status, saved.last_error) == ("pending", "internal:RuntimeError")


async def test_a_poison_message_ends_up_failed_instead_of_starving_the_queue(
    scene: Scene, telegram: Telegram, monkeypatch: pytest.MonkeyPatch
) -> None:
    poison, _ = await make_message(scene, with_chart=False)
    healthy, _ = await make_message(scene, with_chart=False)
    real = load_message_view

    async def poisoned(session: AsyncSession, message_id: uuid.UUID, settings: object) -> object:
        if message_id == poison:
            raise RuntimeError("dữ liệu hỏng")
        return await real(session, message_id, settings)  # type: ignore[arg-type]

    monkeypatch.setattr("app.services.price_alert_sender.load_message_view", poisoned)
    sender = await sender_for(scene.sf, telegram)
    now = NOW
    for _ in range(MAX_ATTEMPTS + 1):
        await sender.run_once(now)
        now += timedelta(hours=1)

    assert (await row(scene.sf, healthy)).status == "sent"
    assert (await row(scene.sf, poison)).status == "failed"


async def test_a_message_older_than_a_day_is_expired_not_sent(
    scene: Scene, telegram: Telegram
) -> None:
    message_id, _ = await make_message(scene, with_chart=False)

    outcome = await (await sender_for(scene.sf, telegram)).run_once(NOW + timedelta(hours=25))

    assert outcome.failed == 1 and telegram.requests == []
    assert (await row(scene.sf, message_id)).status_reason == "expired"


async def test_an_expired_lease_past_the_attempt_limit_becomes_failed(
    scene: Scene, telegram: Telegram
) -> None:
    message_id, _ = await make_message(scene, with_chart=False)
    async with scene.sf() as session:
        await session.execute(
            update(PriceAlertMessage)
            .where(PriceAlertMessage.id == message_id)
            .values(status="sending", lease_until=NOW - timedelta(minutes=1), attempts=MAX_ATTEMPTS)
        )
        await session.commit()

    await (await sender_for(scene.sf, telegram)).run_once(NOW)

    assert telegram.requests == []
    assert (await row(scene.sf, message_id)).status_reason == "max_attempts"


@pytest.mark.parametrize("code", [401, 404])
async def test_a_revoked_token_keeps_the_message_and_does_not_burn_an_attempt(
    scene: Scene, telegram: Telegram, code: int
) -> None:
    message_id, _ = await make_message(scene, with_chart=False)
    telegram.handler = error(code, "Unauthorized" if code == 401 else "Not Found")

    outcome = await (await sender_for(scene.sf, telegram)).run_once(NOW)

    saved = await row(scene.sf, message_id)
    assert outcome.retried == 1
    assert (saved.status, saved.attempts, saved.last_error) == ("pending", 0, f"config_{code}")
    telegram.handler = telegram.ok
    later = await (await sender_for(scene.sf, telegram)).run_once(NOW + timedelta(minutes=6))
    assert later.sent == 1


async def test_a_huge_retry_after_is_capped(scene: Scene, telegram: Telegram) -> None:
    message_id, _ = await make_message(scene, with_chart=False)
    telegram.handler = error(429, "Too Many Requests", parameters={"retry_after": 86400})

    await (await sender_for(scene.sf, telegram)).run_once(NOW)

    saved = await row(scene.sf, message_id)
    assert saved.lease_until is not None
    assert abs((saved.lease_until - NOW - timedelta(minutes=5)).total_seconds()) < 2


async def test_a_slow_worker_cannot_overwrite_the_result_of_the_worker_that_took_over(
    scene: Scene, telegram: Telegram
) -> None:
    from app.services.price_alert_sender import _Claim  # noqa: PLC2701

    message_id, _ = await make_message(scene, with_chart=False)
    sender = await sender_for(scene.sf, telegram)
    async with scene.sf() as session:
        await session.execute(
            update(PriceAlertMessage)
            .where(PriceAlertMessage.id == message_id)
            .values(status="sent", attempts=2)
        )
        await session.commit()

    await sender._retry(_Claim(message_id, 1), NOW, "network", timedelta(seconds=30))  # noqa: SLF001
    await sender._finish(_Claim(message_id, 1), "failed", reason="x", now=NOW)  # noqa: SLF001

    assert (await row(scene.sf, message_id)).status == "sent"


async def test_the_pilot_list_is_checked_again_at_send_time(
    scene: Scene, telegram: Telegram
) -> None:
    message_id, _ = await make_message(scene, with_chart=False)
    client, _http = telegram.client()
    sender = PriceAlertSender(
        scene.sf, client, base_url=BASE_URL, pilot_emails=frozenset({"someone-else@example.com"})
    )

    outcome = await sender.run_once(NOW)

    assert outcome.skipped == 1 and telegram.requests == []
    assert (await row(scene.sf, message_id)).status_reason == "pilot"


async def test_each_message_gets_its_own_lease_from_the_moment_it_is_taken(
    scene: Scene, telegram: Telegram
) -> None:
    first, _ = await make_message(scene, with_chart=False)
    second, _ = await make_message(scene, with_chart=False)
    leases: dict[uuid.UUID, datetime | None] = {}

    def slow(request: httpx.Request) -> httpx.Response:
        return telegram.ok(request)

    telegram.handler = slow
    sender = await sender_for(scene.sf, telegram)
    # Chưa tin nào được nhận trước khi tin đầu gửi xong: sau lần chạy mọi tin đều `sent`,
    # không có tin nào bị giữ ở `sending` với lease của cả lô.
    await sender.run_once(NOW)
    for message_id in (first, second):
        leases[message_id] = (await row(scene.sf, message_id)).lease_until

    assert leases == {first: None, second: None}
