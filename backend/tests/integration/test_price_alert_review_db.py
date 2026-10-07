"""Duyệt thẻ giá bất thường (Giá đúng / Nhập sai) trên PostgreSQL thật (Slice 13, L22 đến L24)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from price_alert_scene import Scene
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from test_price_alert_anomaly_messages_db import flag, new_run, scene  # noqa: F401

from app.models import AuditLog, Material, PriceAlertEvent
from app.services.price_alert_anomaly import excluded_line_ids
from app.services.price_alert_review_service import PriceAlertReviewService, ReviewOutcome

pytestmark = pytest.mark.integration

AT = datetime(2052, 5, 5, 4, 0, tzinfo=UTC)


async def review(
    sf: async_sessionmaker[AsyncSession], event_id: uuid.UUID, action: str, actor: uuid.UUID
):  # type: ignore[no-untyped-def]
    async with sf() as session:
        result = await PriceAlertReviewService(session).review(
            event_id, action, actor_user_id=actor, now=AT
        )
        await session.commit()
    return result


async def event_row(sf: async_sessionmaker[AsyncSession], event_id: uuid.UUID) -> PriceAlertEvent:
    async with sf() as session:
        event = await session.get(PriceAlertEvent, event_id)
        assert event is not None
        return event


async def test_a_manager_confirming_the_price_makes_the_line_valid_again(scene: Scene) -> None:  # noqa: F811
    manager = await scene.person("it-manager")
    run = await new_run(scene.sf)
    event_id = await flag(scene.sf, run, scene.material, None, with_line=True)
    saved = await event_row(scene.sf, event_id)
    async with scene.sf() as session:
        assert saved.quote_line_id in await excluded_line_ids(
            session, scene.material, saved.delivery_month
        )

    result = await review(scene.sf, event_id, "ok", manager)

    assert result.outcome is ReviewOutcome.REVIEWED
    after = await event_row(scene.sf, event_id)
    assert (after.review_status, after.reviewed_by_id, after.reviewed_at) == (
        "accepted",
        manager,
        AT,
    )
    async with scene.sf() as session:
        assert saved.quote_line_id not in await excluded_line_ids(
            session, scene.material, saved.delivery_month
        )
        audit = (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.action == "price_alerts.anomaly_reviewed",
                    AuditLog.actor_user_id == manager,
                )
            )
        ).scalar_one()
    assert audit.metadata_json["status"] == "accepted"
    assert "telegram_user_id" not in audit.metadata_json
    async with scene.sf() as session:
        code = (
            await session.execute(select(Material.code).where(Material.id == scene.material))
        ).scalar_one()
    # Người đọc nhật ký cần thấy vật tư nào, không chỉ id của thẻ.
    assert audit.metadata_json["material_code"] == code
    assert audit.metadata_json["material_name"] == "Vật tư thử"


async def test_marking_the_price_wrong_keeps_the_line_excluded(scene: Scene) -> None:  # noqa: F811
    manager = await scene.person("it-manager")
    run = await new_run(scene.sf)
    event_id = await flag(scene.sf, run, scene.material, None, with_line=True)
    saved = await event_row(scene.sf, event_id)

    result = await review(scene.sf, event_id, "no", manager)

    assert (result.outcome, result.status) == (ReviewOutcome.REVIEWED, "rejected")
    async with scene.sf() as session:
        excluded = await excluded_line_ids(session, scene.material, saved.delivery_month)
    assert saved.quote_line_id in excluded


async def test_attached_points_follow_the_decision_of_their_card(scene: Scene) -> None:  # noqa: F811
    manager = await scene.person("it-manager")
    run = await new_run(scene.sf)
    card = await flag(scene.sf, run, scene.material, None, with_line=True)
    attached = await flag(
        scene.sf, run, scene.material, None, with_line=True, attached_to=card, price=980
    )

    await review(scene.sf, card, "ok", manager)

    assert (await event_row(scene.sf, attached)).review_status == "accepted"


async def test_an_attached_point_cannot_be_reviewed_on_its_own(scene: Scene) -> None:  # noqa: F811
    manager = await scene.person("it-manager")
    run = await new_run(scene.sf)
    card = await flag(scene.sf, run, scene.material, None)
    attached = await flag(scene.sf, run, scene.material, None, attached_to=card, price=980)

    result = await review(scene.sf, attached, "ok", manager)

    assert result.outcome is ReviewOutcome.NOT_FOUND
    assert (await event_row(scene.sf, attached)).review_status == "pending"


async def test_people_without_the_permission_or_inactive_cannot_review(scene: Scene) -> None:  # noqa: F811
    from app.models import UserStatus

    staff = await scene.person()
    locked = await scene.person("it-manager", status=UserStatus.INACTIVE)
    run = await new_run(scene.sf)
    event_id = await flag(scene.sf, run, scene.material, None)

    for actor in (staff, locked):
        assert (await review(scene.sf, event_id, "ok", actor)).outcome is ReviewOutcome.FORBIDDEN

    assert (await event_row(scene.sf, event_id)).review_status == "pending"


async def test_two_managers_pressing_at_once_leave_exactly_one_winner(scene: Scene) -> None:  # noqa: F811
    first = await scene.person("it-manager")
    second = await scene.person("it-manager")
    run = await new_run(scene.sf)
    event_id = await flag(scene.sf, run, scene.material, None)

    results = await asyncio.gather(
        review(scene.sf, event_id, "ok", first), review(scene.sf, event_id, "no", second)
    )

    outcomes = sorted(r.outcome for r in results)
    assert outcomes == [ReviewOutcome.ALREADY_REVIEWED, ReviewOutcome.REVIEWED]
    winner = next(r for r in results if r.outcome is ReviewOutcome.REVIEWED)
    loser = next(r for r in results if r.outcome is ReviewOutcome.ALREADY_REVIEWED)
    assert (loser.status, loser.reviewer_name) == (winner.status, winner.reviewer_name)
    async with scene.sf() as session:
        audits = (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.action == "price_alerts.anomaly_reviewed",
                    AuditLog.entity_id == str(event_id),
                )
            )
        ).scalars()
        assert len(list(audits)) == 1


async def test_pressing_a_resolved_or_unknown_card_reports_it_without_changes(scene: Scene) -> None:  # noqa: F811
    manager = await scene.person("it-manager")
    run = await new_run(scene.sf)
    event_id = await flag(scene.sf, run, scene.material, None)
    await review(scene.sf, event_id, "ok", manager)

    again = await review(scene.sf, event_id, "no", manager)
    unknown = await review(scene.sf, uuid.uuid4(), "ok", manager)

    assert (again.outcome, again.status) == (ReviewOutcome.ALREADY_REVIEWED, "accepted")
    assert unknown.outcome is ReviewOutcome.NOT_FOUND
