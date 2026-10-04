"""Ai nhận tin của một vật tư (D7 đến D10, L12, L16) trên PostgreSQL thật."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from db_helpers import (
    build_account,
    create_material,
    create_priced_line,
    create_user,
    ensure_role,
    insert_rows,
    next_telegram_id,
)
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import QuoteVersion, UserAlertPreference, UserStatus
from app.services.price_alert_recipients import RecipientDecision, resolve_recipients

pytestmark = pytest.mark.integration

NOW = datetime(2046, 6, 15, 3, 0, tzinfo=UTC)
TODAY = date(2046, 6, 15)
RECEIVE_ALL = "price_alerts.receive_all"


class Scene:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.sf = session_factory
        self.mine: set[uuid.UUID] = set()
        self.material: uuid.UUID

    async def setup(self) -> Scene:
        self.material = await create_material(self.sf)
        return self

    async def person(
        self,
        *roles: str,
        linked: bool = True,
        status: UserStatus = UserStatus.ACTIVE,
        email: str | None = None,
        account_status: str = "active",
    ) -> uuid.UUID:
        user_id = await create_user(self.sf, status=status, email=email, role_names=roles)
        if linked:
            await insert_rows(self.sf, build_account(user_id, next_telegram_id(), account_status))
        self.mine.add(user_id)
        return user_id

    async def entered(
        self,
        user_id: uuid.UUID,
        *,
        received: date = TODAY,
        status: str = "confirmed",
        cancelled: bool = False,
        material: uuid.UUID | None = None,
    ) -> tuple[uuid.UUID, uuid.UUID]:
        return await create_priced_line(
            self.sf,
            material_id=material or self.material,
            price=100,
            received_date=received,
            status=status,
            cancelled=cancelled,
            created_by_id=user_id,
        )

    async def prefer(self, user_id: uuid.UUID, **values: object) -> None:
        await insert_rows(self.sf, UserAlertPreference(user_id=user_id, **values))

    async def resolve(self, level: str | None = "medium", **kwargs: object) -> RecipientDecision:
        async with self.sf() as session:
            decision = await resolve_recipients(
                session,
                material_id=kwargs.pop("material_id", self.material),  # type: ignore[arg-type]
                event_level=level,
                kind=kwargs.pop("kind", "change"),  # type: ignore[arg-type]
                now=NOW,
                seed_user_id=kwargs.pop("seed_user_id", None),  # type: ignore[arg-type]
                **kwargs,  # type: ignore[arg-type]
            )
        return RecipientDecision(
            [r for r in decision.recipients if r.user_id in self.mine],
            [s for s in decision.skipped if s.user_id in self.mine],
        )

    @staticmethod
    def ids(decision: RecipientDecision) -> set[uuid.UUID]:
        return {r.user_id for r in decision.recipients}


@pytest.fixture
async def scene(session_factory: async_sessionmaker[AsyncSession]) -> Scene:
    await ensure_role(session_factory, "it-manager", [RECEIVE_ALL])
    await ensure_role(session_factory, "admin", [RECEIVE_ALL])
    return await Scene(session_factory).setup()


async def test_a_linked_manager_receives_a_medium_event_of_any_material(scene: Scene) -> None:
    manager = await scene.person("it-manager")

    decision = await scene.resolve("medium")

    [recipient] = decision.recipients
    assert (recipient.user_id, recipient.audience) == (manager, "manager")
    assert recipient.chat_id > 0


async def test_a_manager_does_not_receive_light_by_default_but_staff_does(scene: Scene) -> None:
    manager = await scene.person("it-manager")
    staff = await scene.person()
    await scene.entered(staff)

    decision = await scene.resolve("light")

    assert scene.ids(decision) == {staff}
    assert manager not in scene.ids(decision)


async def test_staff_receive_only_materials_they_entered_recently(scene: Scene) -> None:
    staff = await scene.person()
    other_material = await create_material(scene.sf)
    await scene.entered(staff, received=TODAY - timedelta(days=89))
    await scene.entered(staff, material=other_material, received=TODAY - timedelta(days=89))

    assert scene.ids(await scene.resolve("medium")) == {staff}
    assert (
        scene.ids(await scene.resolve("medium", material_id=await create_material(scene.sf)))
        == set()
    )


async def test_staff_outside_the_lookback_window_do_not_receive(scene: Scene) -> None:
    staff = await scene.person()
    await scene.entered(staff, received=TODAY - timedelta(days=91))

    assert scene.ids(await scene.resolve("large")) == set()
    assert scene.ids(await scene.resolve("large", staff_lookback_days=120)) == {staff}


@pytest.mark.parametrize(
    "kwargs",
    [{"status": "draft"}, {"status": "superseded"}, {"cancelled": True}],
)
async def test_staff_do_not_receive_for_draft_superseded_or_cancelled_quotes(
    scene: Scene, kwargs: dict[str, object]
) -> None:
    staff = await scene.person()
    await scene.entered(staff, **kwargs)  # type: ignore[arg-type]

    assert scene.ids(await scene.resolve("large")) == set()


async def test_staff_are_decided_by_the_quote_creator_not_the_version_creator(
    scene: Scene,
) -> None:
    quote_creator, version_creator = await scene.person(), await scene.person()
    version, _ = await scene.entered(quote_creator)
    async with scene.sf() as session:
        await session.execute(
            update(QuoteVersion)
            .where(QuoteVersion.id == version)
            .values(created_by_id=version_creator)
        )
        await session.commit()

    assert scene.ids(await scene.resolve("large")) == {quote_creator}
    # D12: người nhập của thẻ bất thường là người tạo version.
    anomaly = await scene.resolve(None, kind="anomaly", entered_by_id=version_creator)
    assert scene.ids(anomaly) == {version_creator}
    assert anomaly.recipients[0].audience == "enterer"


async def test_admin_receives_only_with_the_opt_in_even_though_it_holds_receive_all(
    scene: Scene,
) -> None:
    admin = await scene.person("admin")
    assert scene.ids(await scene.resolve("large")) == set()

    await scene.prefer(admin, admin_receive_all=True)

    decision = await scene.resolve("large")
    assert scene.ids(decision) == {admin}
    assert decision.recipients[0].audience == "admin"


async def test_the_seed_account_is_excluded_and_a_missing_seed_excludes_nobody(
    scene: Scene,
) -> None:
    seed = await scene.person("it-manager")
    other = await scene.person("it-manager")

    assert scene.ids(await scene.resolve("large", seed_user_id=seed)) == {other}
    assert scene.ids(await scene.resolve("large", seed_user_id=None)) == {seed, other}


@pytest.mark.parametrize("case", ["inactive", "locked", "unlinked", "blocked", "revoked"])
async def test_users_who_cannot_be_reached_are_excluded(scene: Scene, case: str) -> None:
    options: dict[str, object] = {
        "inactive": {"status": UserStatus.INACTIVE},
        "locked": {"status": UserStatus.LOCKED},
        "unlinked": {"linked": False},
        "blocked": {"account_status": "blocked"},
        "revoked": {"account_status": "revoked"},
    }[case]  # type: ignore[assignment]
    await scene.person("it-manager", **options)  # type: ignore[arg-type]

    assert scene.ids(await scene.resolve("large")) == set()


async def test_personal_minimum_level_and_the_off_switch(scene: Scene) -> None:
    wants_large = await scene.person("it-manager")
    wants_light = await scene.person("it-manager")
    off = await scene.person("it-manager")
    await scene.prefer(wants_large, min_level="large")
    await scene.prefer(wants_light, min_level="light")
    await scene.prefer(off, is_enabled=False)

    assert scene.ids(await scene.resolve("light")) == {wants_light}
    assert scene.ids(await scene.resolve("medium")) == {wants_light}
    assert scene.ids(await scene.resolve("large")) == {wants_large, wants_light}


async def test_anomaly_cards_ignore_the_minimum_level_but_respect_the_off_switch(
    scene: Scene,
) -> None:
    strict = await scene.person("it-manager")
    off = await scene.person("it-manager")
    await scene.prefer(strict, min_level="large")
    await scene.prefer(off, is_enabled=False)

    decision = await scene.resolve(None, kind="anomaly")

    assert scene.ids(decision) == {strict}


async def test_the_pilot_list_keeps_only_the_listed_people_and_marks_the_rest_skipped(
    scene: Scene,
) -> None:
    keep = await scene.person("it-manager", email="Pilot.Keep@Example.com")
    other = await scene.person("it-manager", email="other@example.com")

    decision = await scene.resolve("large", pilot_emails=frozenset({"pilot.keep@example.com"}))

    assert scene.ids(decision) == {keep}
    assert [(s.user_id, s.reason) for s in decision.skipped] == [(other, "pilot")]


async def test_a_manager_who_is_also_the_enterer_gets_one_manager_entry(scene: Scene) -> None:
    both = await scene.person("it-manager")
    await scene.entered(both)

    decision = await scene.resolve("large")
    anomaly = await scene.resolve(None, kind="anomaly", entered_by_id=both)

    assert [r.audience for r in decision.recipients] == ["manager"]
    assert [r.audience for r in anomaly.recipients] == ["manager"]


async def test_a_quote_without_creator_does_not_break_staff_lookup(scene: Scene) -> None:
    await create_priced_line(
        scene.sf, material_id=scene.material, price=10, received_date=TODAY, created_by_id=None
    )

    assert (await scene.resolve("large")).recipients == []


async def test_unknown_event_level_reaches_nobody_for_change_events(scene: Scene) -> None:
    await scene.person("it-manager")

    assert (await scene.resolve(None)).recipients == []
