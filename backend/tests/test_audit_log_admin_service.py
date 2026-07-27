from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.models import AuditLog, User, UserStatus
from app.services.audit_log_admin import (
    AuditLogAdminService,
    AuditLogListQuery,
    InvalidAuditLogCursorError,
    decode_audit_log_cursor,
    encode_audit_log_cursor,
)


class FakeScalarResult:
    def __init__(self, value: object) -> None:
        self._value = value

    def scalar_one(self) -> object:
        return self._value

    def scalars(self) -> FakeScalarResult:
        return self

    def all(self) -> list[object]:
        if isinstance(self._value, list):
            return self._value
        return [self._value]


class FakeAsyncSession:
    def __init__(self, rows: list[AuditLog], total: int) -> None:
        self.rows = rows
        self.total = total
        self.statements: list[object] = []

    async def execute(self, statement: object) -> FakeScalarResult:
        self.statements.append(statement)
        compiled = str(statement)
        if "count" in compiled:
            return FakeScalarResult(self.total)
        return FakeScalarResult(self.rows)


def build_audit_log(created_at: datetime) -> AuditLog:
    actor = User(
        id=uuid4(),
        email="actor@example.com",
        status=UserStatus.ACTIVE,
        full_name="Actor",
    )
    audit_log = AuditLog(
        id=uuid4(),
        actor_user_id=actor.id,
        action="users.user_updated",
        entity_type="user",
        entity_id=str(uuid4()),
        request_id="req-123",
        created_at=created_at,
    )
    audit_log.actor_user = actor
    return audit_log


def test_audit_log_cursor_round_trip() -> None:
    created_at = datetime(2026, 7, 24, 8, 30, tzinfo=UTC)
    audit_log_id = uuid4()

    cursor = encode_audit_log_cursor(created_at=created_at, audit_log_id=audit_log_id)
    decoded_created_at, decoded_id = decode_audit_log_cursor(cursor)

    assert decoded_created_at == created_at
    assert decoded_id == audit_log_id


def test_decode_audit_log_cursor_rejects_invalid_value() -> None:
    with pytest.raises(InvalidAuditLogCursorError):
        decode_audit_log_cursor("not-a-valid-cursor")


def test_decode_audit_log_cursor_rejects_naive_datetime() -> None:
    cursor = encode_audit_log_cursor(
        created_at=datetime(2026, 7, 24, 8, 30),
        audit_log_id=uuid4(),
    )

    with pytest.raises(InvalidAuditLogCursorError):
        decode_audit_log_cursor(cursor)


@pytest.mark.asyncio
async def test_list_audit_logs_returns_next_cursor_when_more_rows_exist() -> None:
    first = build_audit_log(datetime(2026, 7, 24, 8, 0, tzinfo=UTC))
    second = build_audit_log(datetime(2026, 7, 24, 7, 0, tzinfo=UTC))
    session = FakeAsyncSession(rows=[first, second], total=2)
    service = AuditLogAdminService(session)  # type: ignore[arg-type]

    result = await service.list_audit_logs(AuditLogListQuery(limit=1))

    assert result.items == [first]
    assert result.total == 2
    assert result.next_cursor is not None
    decoded_created_at, decoded_id = decode_audit_log_cursor(result.next_cursor)
    assert decoded_created_at == first.created_at
    assert decoded_id == first.id


@pytest.mark.asyncio
async def test_list_audit_logs_applies_keyset_cursor() -> None:
    cursor_created_at = datetime(2026, 7, 24, 8, 0, tzinfo=UTC)
    cursor_id = uuid4()
    cursor = encode_audit_log_cursor(created_at=cursor_created_at, audit_log_id=cursor_id)
    session = FakeAsyncSession(
        rows=[build_audit_log(datetime(2026, 7, 24, 7, 0, tzinfo=UTC))],
        total=1,
    )
    service = AuditLogAdminService(session)  # type: ignore[arg-type]

    await service.list_audit_logs(AuditLogListQuery(limit=10, cursor=cursor))

    page_statement = session.statements[1]
    params = page_statement.compile().params  # type: ignore[attr-defined]
    compiled = str(page_statement)

    assert "audit_logs.created_at <" in compiled
    assert "audit_logs.created_at =" in compiled
    assert "audit_logs.id <" in compiled
    assert cursor_created_at in params.values()
    assert cursor_id in params.values()


@pytest.mark.asyncio
async def test_list_audit_logs_applies_exact_filters_and_date_bounds() -> None:
    actor_user_id = uuid4()
    session = FakeAsyncSession(
        rows=[build_audit_log(datetime(2026, 7, 24, 8, 0, tzinfo=UTC))],
        total=1,
    )
    service = AuditLogAdminService(session)  # type: ignore[arg-type]

    await service.list_audit_logs(
        AuditLogListQuery(
            actor_user_id=actor_user_id,
            action="users.user_updated",
            entity_type="user",
            entity_id="entity-123",
            request_id="req-123",
            created_from=datetime(2026, 7, 23, 17, 0, tzinfo=UTC),
            created_to=datetime(2026, 7, 24, 17, 0, tzinfo=UTC),
        )
    )

    count_statement = session.statements[0]
    params = count_statement.compile().params  # type: ignore[attr-defined]
    compiled = str(count_statement)

    assert "audit_logs.actor_user_id" in compiled
    assert "audit_logs.action" in compiled
    assert "audit_logs.entity_type" in compiled
    assert "audit_logs.entity_id" in compiled
    assert "audit_logs.request_id" in compiled
    assert "audit_logs.created_at >=" in compiled
    assert "audit_logs.created_at <" in compiled
    assert actor_user_id in params.values()
    assert "users.user_updated" in params.values()
    assert "entity-123" in params.values()
    assert "req-123" in params.values()
