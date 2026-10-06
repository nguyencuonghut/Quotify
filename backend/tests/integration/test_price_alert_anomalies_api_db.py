"""API duyệt giá bất thường qua HTTP trên PostgreSQL thật (1C, Slice 2, M6 và M7)."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from price_alert_scene import Scene
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from test_price_alert_anomaly_messages_db import build, flag, new_run, scene  # noqa: F401

from app.api.v1.price_alert_anomalies import get_telegram_client_for_review
from app.auth.jwt import issue_access_token
from app.core.application import create_app
from app.core.config import Settings
from app.db.session import get_db_session
from app.integrations.telegram import TelegramClient
from app.models import AuditLog, PriceAlertEvent, PriceAlertMessage, Quote, QuoteVersion
from app.services.price_alert_anomaly import excluded_line_ids

pytestmark = pytest.mark.integration

URL = "/api/v1/price-alerts/anomalies"


class Harness:
    def __init__(
        self,
        scene: Scene,  # noqa: F811
        client: AsyncClient,
        telegram: list[httpx.Request],
    ) -> None:
        self.scene = scene
        self.client = client
        self.telegram = telegram

    @staticmethod
    def headers(user_id: uuid.UUID) -> dict[str, str]:
        token, _ = issue_access_token(user_id)
        return {"Authorization": f"Bearer {token}"}

    async def get(self, user_id: uuid.UUID, **params: object) -> httpx.Response:
        return await self.client.get(URL, params=params, headers=self.headers(user_id))

    async def review(
        self, user_id: uuid.UUID, event_id: uuid.UUID, decision: str
    ) -> httpx.Response:
        return await self.client.post(
            f"{URL}/{event_id}/review", json={"decision": decision}, headers=self.headers(user_id)
        )

    async def card(self, *, price: int = 970, month: date = date(2052, 12, 1)) -> uuid.UUID:
        run = await new_run(self.scene.sf)
        return await flag(
            self.scene.sf, run, self.scene.material, None, with_line=True, price=price, month=month
        )

    async def event(self, event_id: uuid.UUID) -> PriceAlertEvent:
        async with self.scene.sf() as session:
            row = await session.get(PriceAlertEvent, event_id)
            assert row is not None
            return row


@pytest.fixture
async def harness(
    scene: Scene,  # noqa: F811
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[Harness]:
    app: FastAPI = create_app(
        settings=Settings.model_validate(
            {"app_env": "test", "otel_enabled": False, "otel_exporter_otlp_endpoint": None}
        )
    )
    telegram: list[httpx.Request] = []

    async def db_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    def respond(request: httpx.Request) -> httpx.Response:
        telegram.append(request)
        return httpx.Response(200, json={"ok": True, "result": True})

    fake = TelegramClient(
        token="123456789:AAFakeTokenFakeTokenFakeTokenFake12",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
    )
    app.dependency_overrides[get_db_session] = db_session
    app.dependency_overrides[get_telegram_client_for_review] = lambda: fake
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield Harness(scene, client, telegram)


async def test_a_manager_sees_a_pending_card_and_confirms_it(harness: Harness) -> None:
    manager = await harness.scene.person("it-manager")
    event_id = await harness.card()

    listed = await harness.get(manager)

    assert listed.status_code == 200
    body = listed.json()
    [item] = [i for i in body["items"] if i["id"] == str(event_id)]
    assert item["review_status"] == "pending"
    assert item["material_id"] == str(harness.scene.material)
    assert item["price_new"] == "970.00" and item["percent_change"] == "-96.21"
    assert item["reference_prices"] == ["25600.00", "25435.00", "25900.00"]
    assert item["attached_count"] == 0 and item["reviewed_by_name"] is None
    assert body["total"] >= 1

    reviewed = await harness.review(manager, event_id, "accepted")

    assert reviewed.status_code == 200
    assert reviewed.json()["review_status"] == "accepted"
    saved = await harness.event(event_id)
    assert (saved.review_status, saved.reviewed_by_id) == ("accepted", manager)
    async with harness.scene.sf() as session:
        assert saved.quote_line_id not in await excluded_line_ids(
            session, harness.scene.material, saved.delivery_month
        )


async def test_people_without_the_permission_or_a_token_are_refused(harness: Harness) -> None:
    staff = await harness.scene.person()
    event_id = await harness.card()

    assert (await harness.get(staff)).status_code == 403
    assert (await harness.review(staff, event_id, "accepted")).status_code == 403
    assert (await harness.client.get(URL)).status_code == 401
    assert (await harness.event(event_id)).review_status == "pending"


async def test_marking_a_price_wrong_keeps_the_line_excluded_and_is_audited(
    harness: Harness,
) -> None:
    manager = await harness.scene.person("it-manager")
    event_id = await harness.card()
    saved = await harness.event(event_id)

    response = await harness.review(manager, event_id, "rejected")

    assert response.status_code == 200 and response.json()["review_status"] == "rejected"
    async with harness.scene.sf() as session:
        assert saved.quote_line_id in await excluded_line_ids(
            session, harness.scene.material, saved.delivery_month
        )
        audit = (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.action == "price_alerts.anomaly_reviewed",
                    AuditLog.entity_id == str(event_id),
                )
            )
        ).scalar_one()
    assert audit.actor_user_id == manager and audit.metadata_json["status"] == "rejected"


async def test_a_second_review_gets_a_conflict_that_names_who_decided(harness: Harness) -> None:
    first = await harness.scene.person("it-manager")
    second = await harness.scene.person("it-manager")
    event_id = await harness.card()
    await harness.review(first, event_id, "accepted")

    again = await harness.review(second, event_id, "rejected")

    assert again.status_code == 409
    detail = again.json()["detail"]
    assert detail["review_status"] == "accepted" and detail["reviewed_by_name"]
    assert (await harness.event(event_id)).review_status == "accepted"


async def test_unknown_attached_and_malformed_requests_are_rejected(harness: Harness) -> None:
    manager = await harness.scene.person("it-manager")
    card = await harness.card()
    run = await new_run(harness.scene.sf)
    attached = await flag(
        harness.scene.sf, run, harness.scene.material, None, attached_to=card, price=980
    )

    assert (await harness.review(manager, uuid.uuid4(), "accepted")).status_code == 404
    assert (await harness.review(manager, attached, "accepted")).status_code == 404
    assert (await harness.review(manager, card, "maybe")).status_code == 422
    assert (await harness.event(attached)).review_status == "pending"


async def test_two_managers_at_once_leave_one_winner_and_one_conflict(harness: Harness) -> None:
    first = await harness.scene.person("it-manager")
    second = await harness.scene.person("it-manager")
    event_id = await harness.card()

    responses = await asyncio.gather(
        harness.review(first, event_id, "accepted"), harness.review(second, event_id, "rejected")
    )

    assert sorted(r.status_code for r in responses) == [200, 409]


async def test_reviewing_on_the_web_edits_the_telegram_card_and_drops_its_buttons(
    harness: Harness,
) -> None:
    manager = await harness.scene.person("it-manager")
    run = await new_run(harness.scene.sf)
    event_id = await flag(harness.scene.sf, run, harness.scene.material, None, with_line=True)
    await build(harness.scene.sf, run)
    async with harness.scene.sf() as session:
        await session.execute(
            update(PriceAlertMessage)
            .where(PriceAlertMessage.user_id == manager)
            .values(status="sent", telegram_message_id=777)
        )
        await session.commit()

    response = await harness.review(manager, event_id, "accepted")

    assert response.status_code == 200
    [edit] = harness.telegram
    payload = json.loads(edit.content)
    assert edit.url.path.endswith("/editMessageText") and payload["message_id"] == 777
    assert "Đã xác nhận giá đúng" in payload["text"] and "reply_markup" not in payload


async def test_a_telegram_failure_does_not_undo_the_review(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager = await harness.scene.person("it-manager")
    event_id = await harness.card()

    async def boom(*args: object, **kwargs: object) -> int:
        raise RuntimeError("telegram down")

    monkeypatch.setattr("app.api.v1.price_alert_anomalies.edit_cards_for_events", boom)

    response = await harness.client.post(
        f"{URL}/{event_id}/review", json={"decision": "accepted"}, headers=harness.headers(manager)
    )

    assert response.status_code == 200
    assert (await harness.event(event_id)).review_status == "accepted"


async def test_the_list_counts_attached_points_without_listing_them(harness: Harness) -> None:
    manager = await harness.scene.person("it-manager")
    card = await harness.card()
    run = await new_run(harness.scene.sf)
    await flag(harness.scene.sf, run, harness.scene.material, None, attached_to=card, price=980)

    body = (await harness.get(manager, material_id=str(harness.scene.material))).json()

    assert [i["id"] for i in body["items"]] == [str(card)]
    assert body["items"][0]["attached_count"] == 1 and body["total"] == 1


async def test_pending_hides_cancelled_quotes_and_resolved_keeps_thirty_days_of_history(
    harness: Harness,
) -> None:
    manager = await harness.scene.person("it-manager")
    cancelled = await harness.card(month=date(2052, 12, 1))
    recent = await harness.card(month=date(2053, 1, 1))
    old = await harness.card(month=date(2053, 2, 1))
    now = datetime.now(UTC)
    async with harness.scene.sf() as session:
        quote_id = (
            await session.execute(
                select(QuoteVersion.quote_id)
                .join(PriceAlertEvent, PriceAlertEvent.quote_version_id == QuoteVersion.id)
                .where(PriceAlertEvent.id == cancelled)
            )
        ).scalar_one()
        await session.execute(update(Quote).where(Quote.id == quote_id).values(cancelled_at=now))
        for event_id, days in ((recent, 5), (old, 40)):
            await session.execute(
                update(PriceAlertEvent)
                .where(PriceAlertEvent.id == event_id)
                .values(
                    review_status="rejected",
                    reviewed_by_id=manager,
                    reviewed_at=now - timedelta(days=days),
                )
            )
        await session.commit()
    material = str(harness.scene.material)

    pending = (await harness.get(manager, material_id=material, status="pending")).json()
    resolved = (await harness.get(manager, material_id=material, status="resolved")).json()
    everything = (await harness.get(manager, material_id=material, status="all")).json()

    assert pending["items"] == [] and pending["total"] == 0
    assert [i["id"] for i in resolved["items"]] == [str(recent)]
    assert (
        resolved["items"][0]["reviewed_by_name"]
        and resolved["items"][0]["review_status"] == "rejected"
    )
    assert [i["id"] for i in everything["items"]] == [str(recent)]


async def test_the_list_is_paged_with_a_total_and_oldest_pending_first(harness: Harness) -> None:
    manager = await harness.scene.person("it-manager")
    ids = [await harness.card(month=date(2053, month, 1)) for month in (3, 4, 5)]
    base = datetime(2053, 1, 1, tzinfo=UTC)
    async with harness.scene.sf() as session:
        for index, event_id in enumerate(ids):
            await session.execute(
                update(PriceAlertEvent)
                .where(PriceAlertEvent.id == event_id)
                .values(created_at=base + timedelta(days=index))
            )
        await session.commit()
    material = str(harness.scene.material)

    first = (await harness.get(manager, material_id=material, limit=2, offset=0)).json()
    second = (await harness.get(manager, material_id=material, limit=2, offset=2)).json()

    assert first["total"] == second["total"] == 3
    assert [i["id"] for i in first["items"]] == [str(ids[0]), str(ids[1])]
    assert [i["id"] for i in second["items"]] == [str(ids[2])]
    assert (await harness.get(manager, limit=0)).status_code == 422


async def test_all_lists_the_pending_queue_first_oldest_first_then_the_history(
    harness: Harness,
) -> None:
    manager = await harness.scene.person("it-manager")
    old_pending = await harness.card(month=date(2053, 6, 1))
    new_pending = await harness.card(month=date(2053, 7, 1))
    resolved = await harness.card(month=date(2053, 8, 1))
    now = datetime.now(UTC)
    async with harness.scene.sf() as session:
        for event_id, created in ((old_pending, 1), (new_pending, 2), (resolved, 3)):
            await session.execute(
                update(PriceAlertEvent)
                .where(PriceAlertEvent.id == event_id)
                .values(created_at=now + timedelta(days=100 + created))
            )
        await session.execute(
            update(PriceAlertEvent)
            .where(PriceAlertEvent.id == resolved)
            .values(review_status="accepted", reviewed_by_id=manager, reviewed_at=now)
        )
        await session.commit()

    body = (
        await harness.get(manager, material_id=str(harness.scene.material), status="all")
    ).json()

    assert [i["id"] for i in body["items"]] == [str(old_pending), str(new_pending), str(resolved)]
