"""Ai nhận tin nhắc cập nhật giá (Telegram 1D, Slice 5, F11) trên PostgreSQL thật."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from db_helpers import create_material, ensure_role
from price_alert_scene import NOW, TODAY, Scene
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import UserStatus
from app.services.price_alert_recipients import (
    FreshnessRecipient,
    SkippedRecipient,
    resolve_freshness_recipients,
)

pytestmark = pytest.mark.integration

RECEIVE_ALL = "price_alerts.receive_all"


@pytest.fixture
async def scene(session_factory: async_sessionmaker[AsyncSession]) -> Scene:
    await ensure_role(session_factory, "it-manager", [RECEIVE_ALL])
    await ensure_role(session_factory, "admin", [RECEIVE_ALL])
    return await Scene(session_factory).setup()


async def resolve(
    scene: Scene,
    materials: set[uuid.UUID],
    **kwargs: object,
) -> dict[uuid.UUID, FreshnessRecipient]:
    async with scene.sf() as session:
        recipients, _ = await resolve_freshness_recipients(
            session,
            material_ids=materials,
            now=NOW,
            seed_user_id=kwargs.pop("seed_user_id", None),  # type: ignore[arg-type]
            **kwargs,  # type: ignore[arg-type]
        )
    return {r.user_id: r for r in recipients if r.user_id in scene.mine}


async def skipped(
    scene: Scene, materials: set[uuid.UUID], **kwargs: object
) -> list[SkippedRecipient]:
    async with scene.sf() as session:
        _, skips = await resolve_freshness_recipients(
            session,
            material_ids=materials,
            now=NOW,
            seed_user_id=None,
            **kwargs,  # type: ignore[arg-type]
        )
    return [s for s in skips if s.user_id in scene.mine]


async def test_a_manager_gets_every_material_and_staff_only_the_ones_they_entered(
    scene: Scene,
) -> None:
    a, b = scene.material, await create_material(scene.sf)
    manager = await scene.person("it-manager")
    staff_a = await scene.person()
    staff_b = await scene.person()
    stranger = await scene.person()
    await scene.entered(staff_a, material=a)
    await scene.entered(staff_b, material=b)

    found = await resolve(scene, {a, b})

    assert set(found) == {manager, staff_a, staff_b}
    assert found[manager].audience == "manager"
    assert found[manager].material_ids == frozenset({a, b})
    assert found[staff_a].audience == "staff"
    assert found[staff_a].material_ids == frozenset({a})
    assert found[staff_b].material_ids == frozenset({b})
    assert stranger not in found


async def test_a_manager_who_also_entered_a_material_still_gets_one_entry(scene: Scene) -> None:
    a, b = scene.material, await create_material(scene.sf)
    manager = await scene.person("it-manager")
    await scene.entered(manager, material=a)

    found = await resolve(scene, {a, b})

    assert list(found) == [manager]
    assert found[manager].material_ids == frozenset({a, b})


async def test_staff_only_get_materials_that_are_actually_overdue(scene: Scene) -> None:
    a, b = scene.material, await create_material(scene.sf)
    staff = await scene.person()
    await scene.entered(staff, material=a)
    await scene.entered(staff, material=b)

    found = await resolve(scene, {a})

    assert found[staff].material_ids == frozenset({a})


async def test_admin_only_receives_when_the_personal_switch_is_on(scene: Scene) -> None:
    a = scene.material
    off = await scene.person("admin")
    on = await scene.person("admin")
    await scene.prefer(on, admin_receive_all=True)

    found = await resolve(scene, {a})

    assert off not in found
    assert found[on].audience == "admin"
    assert found[on].material_ids == frozenset({a})


async def test_people_who_switched_notifications_off_or_cannot_receive_are_left_out(
    scene: Scene,
) -> None:
    a = scene.material
    muted = await scene.person("it-manager")
    await scene.prefer(muted, is_enabled=False)
    seed = await scene.person("it-manager")
    unlinked = await scene.person("it-manager", linked=False)
    revoked = await scene.person("it-manager", account_status="revoked")
    locked_user = await scene.person("it-manager", status=UserStatus.LOCKED)
    ok = await scene.person("it-manager")

    found = await resolve(scene, {a}, seed_user_id=seed)

    assert set(found) == {ok}
    assert {muted, seed, unlinked, revoked, locked_user}.isdisjoint(found)


async def test_staff_lookback_ignores_old_drafts_and_cancelled_entries(scene: Scene) -> None:
    a = scene.material
    recent = await scene.person()
    old = await scene.person()
    draft = await scene.person()
    cancelled = await scene.person()
    await scene.entered(recent, received=TODAY - timedelta(days=10), material=a)
    await scene.entered(old, received=TODAY - timedelta(days=100), material=a)
    await scene.entered(draft, status="draft", material=a)
    await scene.entered(cancelled, cancelled=True, material=a)

    found = await resolve(scene, {a}, staff_lookback_days=90)

    assert set(found) == {recent}
    assert set(await resolve(scene, {a}, staff_lookback_days=200)) == {recent, old}


async def test_the_pilot_list_limits_recipients_and_records_who_was_skipped(scene: Scene) -> None:
    a = scene.material
    pilot = await scene.person("it-manager", email="pilot-1d@example.com")
    outsider = await scene.person("it-manager")

    found = await resolve(scene, {a}, pilot_emails=frozenset({"pilot-1d@example.com"}))
    skips = await skipped(scene, {a}, pilot_emails=frozenset({"pilot-1d@example.com"}))

    assert set(found) == {pilot}
    assert [s.user_id for s in skips] == [outsider]
    assert skips[0].reason == "pilot"


async def test_nothing_overdue_means_nobody_is_resolved(scene: Scene) -> None:
    await scene.person("it-manager")

    assert await resolve(scene, set()) == {}
