"""Chọn version cần quét và dòng ứng viên trên PostgreSQL thật (L1, L2, L3, D6)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from db_helpers import (
    create_material,
    create_quote_shell,
    create_user,
    create_version_with_lines,
)
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import PriceAlertScannedVersion, Quote, QuoteVersion
from app.services.price_alert_candidates import (
    VersionToScan,
    record_scanned_version,
    resolve_candidate_lines,
    select_versions_to_scan,
)

pytestmark = pytest.mark.integration

DEC = date(2026, 12, 1)
RECEIVED = date(2026, 10, 5)
# Mỗi test dùng một mốc riêng (DB dùng chung cả phiên) nên watermark nằm ngay trước mốc đó.
_clock = iter(datetime(2040, 1, 1, tzinfo=UTC) + timedelta(days=i) for i in range(10_000))


def _moment() -> datetime:
    return next(_clock)


async def _scan(
    session_factory: async_sessionmaker[AsyncSession], since: datetime, limit: int | None = None
) -> list[VersionToScan]:
    async with session_factory() as session:
        return await select_versions_to_scan(session, watermark=since, limit=limit)


async def test_a_confirmed_version_of_a_live_quote_is_selected_with_its_creator(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user = await create_user(session_factory)
    material = await create_material(session_factory)
    quote = await create_quote_shell(session_factory, created_by_id=user)
    at = _moment()
    version, _ = await create_version_with_lines(
        session_factory,
        quote_id=quote,
        version_number=1,
        received_date=RECEIVED,
        lines=[(material, 100, DEC)],
        confirmed_at=at,
    )

    found = await _scan(session_factory, at - timedelta(minutes=1))

    assert [v.version_id for v in found] == [version]
    assert found[0].quote_created_by_id == user
    assert found[0].received_date == RECEIVED


async def test_only_confirmed_uncancelled_unscanned_versions_after_the_overlap_are_selected(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material = await create_material(session_factory)
    at = _moment()
    lines = [(material, 100, DEC)]

    async def make(
        *, cancelled: bool = False, status: str = "confirmed", when: datetime = at
    ) -> uuid.UUID:
        quote = await create_quote_shell(session_factory, cancelled=cancelled)
        version, _ = await create_version_with_lines(
            session_factory,
            quote_id=quote,
            version_number=1,
            received_date=RECEIVED,
            lines=lines,
            status=status,
            confirmed_at=when,
        )
        return version

    wanted = await make()
    inside_overlap = await make(when=at - timedelta(minutes=4))
    await make(cancelled=True)
    await make(status="draft")
    await make(when=at - timedelta(minutes=6))
    scanned = await make()
    async with session_factory() as session:
        await record_scanned_version(
            session, version_id=scanned, is_trigger_source=True, trigger_delay_working_days=0
        )
        await session.commit()

    found = await _scan(session_factory, at)

    assert {v.version_id for v in found} == {wanted, inside_overlap}


async def test_versions_come_back_ordered_by_confirmation_time_and_respect_the_limit(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material = await create_material(session_factory)
    base = _moment()
    ids = []
    for minutes in (3, 1, 2):
        quote = await create_quote_shell(session_factory)
        version, _ = await create_version_with_lines(
            session_factory,
            quote_id=quote,
            version_number=1,
            received_date=RECEIVED,
            lines=[(material, 100, DEC)],
            confirmed_at=base + timedelta(minutes=minutes),
        )
        ids.append((minutes, version))
    expected = [v for _, v in sorted(ids)]

    assert [v.version_id for v in await _scan(session_factory, base)] == expected
    assert [v.version_id for v in await _scan(session_factory, base, limit=2)] == expected[:2]


async def test_an_adjusted_version_reports_its_source_and_only_changed_lines_are_candidates(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material, other = await create_material(session_factory), await create_material(session_factory)
    quote = await create_quote_shell(session_factory)
    at = _moment()
    first, _ = await create_version_with_lines(
        session_factory,
        quote_id=quote,
        version_number=1,
        received_date=RECEIVED,
        lines=[(material, 100, DEC), (other, 200, DEC)],
        confirmed_at=at,
    )
    second, second_lines = await create_version_with_lines(
        session_factory,
        quote_id=quote,
        version_number=2,
        received_date=RECEIVED,
        lines=[(material, 100, DEC), (other, 210, DEC)],
        confirmed_at=at + timedelta(hours=1),
        supersedes_version_id=first,
    )
    async with session_factory() as session:
        await record_scanned_version(
            session, version_id=first, is_trigger_source=True, trigger_delay_working_days=0
        )
        await session.commit()

    found = await _scan(session_factory, at + timedelta(minutes=30))

    assert [v.version_id for v in found] == [second]
    async with session_factory() as session:
        candidates = await resolve_candidate_lines(session, found[0])
    assert [line.line_id for line in candidates] == [second_lines[1]]


async def test_an_unscanned_source_or_a_moved_received_date_makes_every_line_a_candidate(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material = await create_material(session_factory)
    at = _moment()

    async def adjusted(new_date: date, source_scanned: bool) -> tuple[uuid.UUID, list[uuid.UUID]]:
        quote = await create_quote_shell(session_factory)
        first, _ = await create_version_with_lines(
            session_factory,
            quote_id=quote,
            version_number=1,
            received_date=RECEIVED,
            lines=[(material, 100, DEC)],
            confirmed_at=at,
        )
        new_version, new_lines = await create_version_with_lines(
            session_factory,
            quote_id=quote,
            version_number=2,
            received_date=new_date,
            lines=[(material, 100, DEC)],
            confirmed_at=at + timedelta(hours=1),
            supersedes_version_id=first,
        )
        if source_scanned:
            async with session_factory() as session:
                await record_scanned_version(
                    session,
                    version_id=first,
                    is_trigger_source=True,
                    trigger_delay_working_days=0,
                )
                await session.commit()
        return new_version, new_lines

    unscanned_version, unscanned_lines = await adjusted(RECEIVED, source_scanned=False)
    moved_version, moved_lines = await adjusted(RECEIVED + timedelta(days=1), source_scanned=True)
    same_version, _ = await adjusted(RECEIVED, source_scanned=True)

    async with session_factory() as session:
        found = await select_versions_to_scan(session, watermark=at + timedelta(minutes=30))
        by_version = {
            v.version_id: [line.line_id for line in await resolve_candidate_lines(session, v)]
            for v in found
        }
    assert by_version == {
        unscanned_version: unscanned_lines,
        moved_version: moved_lines,
        same_version: [],
    }


async def test_a_first_version_makes_every_line_a_candidate(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material = await create_material(session_factory)
    quote = await create_quote_shell(session_factory)
    at = _moment()
    _, line_ids = await create_version_with_lines(
        session_factory,
        quote_id=quote,
        version_number=1,
        received_date=RECEIVED,
        lines=[(material, 100, DEC), (material, 100, DEC)],
        confirmed_at=at,
    )

    found = await _scan(session_factory, at - timedelta(minutes=1))
    async with session_factory() as session:
        candidates = await resolve_candidate_lines(session, found[0])

    assert [line.line_id for line in candidates] == line_ids


async def test_recording_a_scanned_version_is_idempotent_and_keeps_the_first_values(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material = await create_material(session_factory)
    quote = await create_quote_shell(session_factory)
    version, _ = await create_version_with_lines(
        session_factory,
        quote_id=quote,
        version_number=1,
        received_date=RECEIVED,
        lines=[(material, 100, DEC)],
    )

    async with session_factory() as session:
        await record_scanned_version(
            session, version_id=version, is_trigger_source=True, trigger_delay_working_days=2
        )
        await record_scanned_version(
            session, version_id=version, is_trigger_source=False, trigger_delay_working_days=None
        )
        await session.commit()
    async with session_factory() as session:
        rows = (
            (
                await session.execute(
                    select(PriceAlertScannedVersion).where(
                        PriceAlertScannedVersion.version_id == version
                    )
                )
            )
            .scalars()
            .all()
        )

    assert len(rows) == 1
    assert rows[0].is_trigger_source is True
    assert rows[0].trigger_delay_working_days == 2


async def test_one_version_replacing_two_sources_needs_both_scanned_to_diff_lines(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material = await create_material(session_factory)
    quote = await create_quote_shell(session_factory)
    at = _moment()
    v1, _ = await create_version_with_lines(
        session_factory,
        quote_id=quote,
        version_number=1,
        received_date=RECEIVED,
        lines=[(material, 100, DEC)],
        confirmed_at=at,
    )
    v2, _ = await create_version_with_lines(
        session_factory,
        quote_id=quote,
        version_number=2,
        received_date=RECEIVED,
        lines=[(material, 100, DEC)],
        confirmed_at=at,
        supersedes_version_id=v1,
    )
    v3, v3_lines = await create_version_with_lines(
        session_factory,
        quote_id=quote,
        version_number=3,
        received_date=RECEIVED,
        lines=[(material, 100, DEC)],
        confirmed_at=at + timedelta(hours=1),
        supersedes_version_id=v2,
    )
    async with session_factory() as session:
        old = await session.get(QuoteVersion, v1)
        assert old is not None
        old.superseded_by_version_id = v3  # v1 và v2 cùng trỏ về v3
        await record_scanned_version(
            session, version_id=v2, is_trigger_source=True, trigger_delay_working_days=0
        )
        await session.commit()

    [found] = [v for v in await _scan(session_factory, at + timedelta(minutes=30))]
    async with session_factory() as session:
        before = [line.line_id for line in await resolve_candidate_lines(session, found)]
        await record_scanned_version(
            session, version_id=v1, is_trigger_source=True, trigger_delay_working_days=0
        )
        after = [line.line_id for line in await resolve_candidate_lines(session, found)]

    assert before == v3_lines  # v1 chưa quét nên mọi dòng là ứng viên
    assert after == []


async def test_the_overlap_boundary_is_strict_and_unconfirmed_versions_are_ignored(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material = await create_material(session_factory)
    watermark = _moment()

    async def make(when: datetime) -> uuid.UUID:
        quote = await create_quote_shell(session_factory)
        version, _ = await create_version_with_lines(
            session_factory,
            quote_id=quote,
            version_number=1,
            received_date=RECEIVED,
            lines=[(material, 100, DEC)],
            confirmed_at=when,
        )
        return version

    on_boundary = await make(watermark - timedelta(minutes=5))
    just_inside = await make(watermark - timedelta(minutes=5) + timedelta(seconds=1))

    found = {v.version_id for v in await _scan(session_factory, watermark)}

    assert just_inside in found
    assert on_boundary not in found


async def test_a_reactivated_quote_does_not_replay_a_version_confirmed_before_the_watermark(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    material = await create_material(session_factory)
    quote = await create_quote_shell(session_factory)
    watermark = _moment()
    version, _ = await create_version_with_lines(
        session_factory,
        quote_id=quote,
        version_number=1,
        received_date=RECEIVED,
        lines=[(material, 100, DEC)],
        confirmed_at=watermark - timedelta(days=2),
    )
    async with session_factory() as session:
        await session.execute(update(Quote).where(Quote.id == quote).values(cancelled_at=watermark))
        await session.commit()
        assert version not in {
            v.version_id for v in await select_versions_to_scan(session, watermark=watermark)
        }
        await session.execute(update(Quote).where(Quote.id == quote).values(cancelled_at=None))
        await session.commit()

    assert version not in {v.version_id for v in await _scan(session_factory, watermark)}
