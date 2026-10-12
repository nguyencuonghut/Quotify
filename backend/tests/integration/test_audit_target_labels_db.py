"""Nhãn "Đối tượng" của nhật ký audit tra từ DB thật: thấy phiếu/người dùng, không thấy id."""

from __future__ import annotations

import uuid

import pytest
from db_helpers import build_account, create_quote_shell, create_user, insert_rows
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import AuditLog, Quote, Supplier
from app.services.audit_log_admin import AuditLogAdminService

pytestmark = pytest.mark.integration


async def _labels(
    session_factory: async_sessionmaker[AsyncSession],
    *rows: AuditLog,
) -> dict[uuid.UUID, str]:
    await insert_rows(session_factory, *rows)
    async with session_factory() as session:
        saved = list(
            (
                await session.execute(select(AuditLog).where(AuditLog.id.in_([r.id for r in rows])))
            ).scalars()
        )
        return await AuditLogAdminService(session).resolve_target_labels(saved)


def _row(action: str, entity_type: str, entity_id: str | None, **metadata: object) -> AuditLog:
    return AuditLog(
        id=uuid.uuid4(),
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata_json=metadata or None,
    )


@pytest.mark.asyncio
async def test_quote_events_are_labelled_with_the_quote_number_and_supplier(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    quote_id = await create_quote_shell(session_factory)
    async with session_factory() as session:
        quote = await session.get(Quote, quote_id)
        supplier = await session.get(Supplier, quote.supplier_id)  # type: ignore[union-attr]
        expected = f"Phiếu #{quote.sequence_number} · {supplier.code}"  # type: ignore[union-attr]
    version_id = str(uuid.uuid4())

    on_quote = _row("quotes.cancelled", "quote", str(quote_id), quote_id=str(quote_id))
    on_version = _row(
        "quotes.version_confirmed", "quote_version", version_id, quote_id=str(quote_id)
    )
    on_line = _row(
        "quotes.purchase_marked", "quote_line", str(uuid.uuid4()), quote_id=str(quote_id)
    )

    labels = await _labels(session_factory, on_quote, on_version, on_line)

    assert labels == {on_quote.id: expected, on_version.id: expected, on_line.id: expected}


@pytest.mark.asyncio
async def test_a_telegram_link_is_labelled_with_the_owners_email(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    email = f"it_tg_{uuid.uuid4().hex[:8]}@example.com"
    user = await create_user(session_factory, email=email)
    account = build_account(user, 720_000_001)
    await insert_rows(session_factory, account)

    row = _row("telegram.unlinked", "telegram_account", str(account.id))

    assert await _labels(session_factory, row) == {row.id: email}


@pytest.mark.asyncio
async def test_rows_that_cannot_be_resolved_get_no_label(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    gone = _row("quotes.cancelled", "quote", str(uuid.uuid4()), quote_id=str(uuid.uuid4()))
    bad_id = _row("telegram.unlinked", "telegram_account", "not-a-uuid")
    other = _row("backups.run_completed", "backup_log", str(uuid.uuid4()))

    assert await _labels(session_factory, gone, bad_id, other) == {}
