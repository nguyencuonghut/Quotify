from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.v1.telegram_link import get_audit_log_service, get_telegram_link_service
from app.auth.dependencies import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.models import User, UserStatus
from app.models.telegram_account import TelegramAccount
from app.services.telegram_link_service import IssuedLinkToken, TelegramLinkStatus

BASE = "/api/v1/users/me/telegram"
TOKEN = "T0kenForTests_abcdefghijklmnopqrstuvwxyz0123456"


class MockSession:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, instance: object) -> None:
        return None


class MockAuditLogService:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def log_event(self, **kwargs: Any) -> None:
        self.events.append(kwargs)


@dataclass
class MockLinkService:
    status: TelegramLinkStatus = field(
        default_factory=lambda: TelegramLinkStatus(
            account=None,
            pending_expires_at=None,
            pending_expires_in_seconds=None,
        )
    )
    issued_for: list[UUID] = field(default_factory=list)
    cancelled_for: list[UUID] = field(default_factory=list)
    revoked: list[tuple[UUID, str]] = field(default_factory=list)
    revoke_result: TelegramAccount | None = None

    async def issue_link_token(self, user_id: UUID) -> IssuedLinkToken:
        self.issued_for.append(user_id)
        return IssuedLinkToken(
            token=TOKEN,
            token_id=uuid4(),
            expires_at=datetime(2026, 10, 4, 10, 10, tzinfo=UTC),
            expires_in_seconds=600,
        )

    async def cancel_pending(self, user_id: UUID) -> int:
        self.cancelled_for.append(user_id)
        return 1

    async def get_status(self, user_id: UUID) -> TelegramLinkStatus:
        return self.status

    async def revoke_user_link(self, user_id: UUID, *, reason: str) -> TelegramAccount | None:
        self.revoked.append((user_id, reason))
        return self.revoke_result


@dataclass
class Harness:
    app: FastAPI
    client: AsyncClient
    user: User
    service: MockLinkService
    audit: MockAuditLogService
    session: MockSession

    def use_settings(self, **overrides: Any) -> None:
        settings = build_settings(**overrides)
        self.app.dependency_overrides[get_settings] = lambda: settings


def build_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "app_env": "test",
        "telegram_enabled": True,
        "telegram_bot_username": "quotify_dev_bot",
        **overrides,
    }
    return Settings.model_validate(values)


@pytest.fixture
def harness(app: FastAPI, client: AsyncClient) -> Iterator[Harness]:
    user = User(id=uuid4(), email="nhanvien@example.com", status=UserStatus.ACTIVE)
    service, audit, session = MockLinkService(), MockAuditLogService(), MockSession()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_telegram_link_service] = lambda: service
    app.dependency_overrides[get_audit_log_service] = lambda: audit
    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_settings] = lambda: build_settings()
    yield Harness(app, client, user, service, audit, session)
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_issuing_a_link_token_returns_the_deep_link(harness: Harness) -> None:
    response = await harness.client.post(f"{BASE}/link-token")

    assert response.status_code == 201
    body = response.json()
    assert body["deep_link"] == f"https://t.me/quotify_dev_bot?start={TOKEN}"
    assert body["bot_username"] == "quotify_dev_bot"
    assert body["expires_in_seconds"] == 600
    assert body["expires_at"].startswith("2026-10-04T10:10:00")
    assert harness.service.issued_for == [harness.user.id]
    assert harness.session.commits == 1


@pytest.mark.asyncio
async def test_issuing_a_link_token_is_audited_without_the_token(harness: Harness) -> None:
    await harness.client.post(f"{BASE}/link-token")

    assert len(harness.audit.events) == 1
    event = harness.audit.events[0]
    assert event["action"] == "telegram.link_requested"
    assert event["entity_type"] == "telegram_link_token"
    context = event["context"]
    assert context.actor_user_id == harness.user.id
    assert context.metadata_json == {"channel": "web"}
    assert TOKEN not in repr(event)


@pytest.mark.asyncio
async def test_status_reports_pending_link_with_server_side_expiry(harness: Harness) -> None:
    harness.service.status = TelegramLinkStatus(
        account=None,
        pending_expires_at=datetime(2026, 10, 4, 10, 10, tzinfo=UTC),
        pending_expires_in_seconds=420,
    )

    response = await harness.client.get(BASE)

    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert body["bot_username"] == "quotify_dev_bot"
    assert body["account"] is None
    assert body["pending_link"]["expires_in_seconds"] == 420
    assert body["pending_link"]["expires_at"].startswith("2026-10-04T10:10:00")


@pytest.mark.asyncio
async def test_status_reports_the_linked_account(harness: Harness) -> None:
    account = TelegramAccount(
        id=uuid4(),
        user_id=harness.user.id,
        telegram_user_id=555,
        chat_id=555,
        username="an_nguyen",
        first_name="An",
        status="active",
        linked_at=datetime.now(UTC) - timedelta(days=1),
    )
    harness.service.status = TelegramLinkStatus(
        account=account,
        pending_expires_at=None,
        pending_expires_in_seconds=None,
    )

    body = (await harness.client.get(BASE)).json()

    assert body["account"]["status"] == "active"
    assert body["account"]["username"] == "an_nguyen"
    assert body["account"]["first_name"] == "An"
    assert "telegram_user_id" not in body["account"]
    assert "chat_id" not in body["account"]
    assert body["pending_link"] is None


@pytest.mark.asyncio
async def test_status_when_the_feature_is_off_is_200_with_enabled_false(harness: Harness) -> None:
    harness.use_settings(telegram_enabled=False)

    response = await harness.client.get(BASE)

    assert response.status_code == 200
    assert response.json() == {
        "enabled": False,
        "bot_username": None,
        "account": None,
        "pending_link": None,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("overrides", [{"telegram_enabled": False}, {"telegram_bot_username": ""}])
async def test_issuing_a_token_is_unavailable_when_the_feature_is_off(
    harness: Harness,
    overrides: dict[str, Any],
) -> None:
    harness.use_settings(**overrides)

    response = await harness.client.post(f"{BASE}/link-token")

    assert response.status_code == 503
    assert harness.service.issued_for == []


@pytest.mark.asyncio
async def test_link_token_requests_are_rate_limited_per_user(harness: Harness) -> None:
    harness.use_settings(rate_limit_telegram_link_token=2)

    codes = [(await harness.client.post(f"{BASE}/link-token")).status_code for _ in range(3)]

    assert codes == [201, 201, 429]
    assert len(harness.service.issued_for) == 2

    other_user = User(id=uuid4(), email="khac@example.com", status=UserStatus.ACTIVE)
    harness.app.dependency_overrides[get_current_user] = lambda: other_user

    assert (await harness.client.post(f"{BASE}/link-token")).status_code == 201


@pytest.mark.asyncio
async def test_rate_limited_response_carries_retry_after(harness: Harness) -> None:
    harness.use_settings(rate_limit_telegram_link_token=1)
    await harness.client.post(f"{BASE}/link-token")

    response = await harness.client.post(f"{BASE}/link-token")

    assert response.status_code == 429
    assert int(response.headers["retry-after"]) >= 1


@pytest.mark.asyncio
async def test_cancelling_a_pending_link_is_idempotent(harness: Harness) -> None:
    first = await harness.client.delete(f"{BASE}/link-token")
    second = await harness.client.delete(f"{BASE}/link-token")

    assert first.status_code == second.status_code == 204
    assert first.content == b""
    assert harness.service.cancelled_for == [harness.user.id, harness.user.id]


@pytest.mark.asyncio
async def test_responses_never_expose_token_hashes(harness: Harness) -> None:
    issued = (await harness.client.post(f"{BASE}/link-token")).text
    status = (await harness.client.get(BASE)).text

    assert "token_hash" not in issued + status


@pytest.mark.asyncio
async def test_unlinking_revokes_the_account_and_is_audited(harness: Harness) -> None:
    account = TelegramAccount(
        id=uuid4(),
        user_id=harness.user.id,
        telegram_user_id=555,
        chat_id=555,
        status="active",
        linked_at=datetime.now(UTC),
    )
    harness.service.revoke_result = account

    response = await harness.client.delete(BASE)

    assert response.status_code == 204
    assert response.content == b""
    assert harness.service.revoked == [(harness.user.id, "user_unlink")]
    assert harness.session.commits == 1
    [event] = harness.audit.events
    assert event["action"] == "telegram.unlinked"
    assert event["entity_type"] == "telegram_account"
    context = event["context"]
    assert context.entity_id == str(account.id)
    assert context.actor_user_id == harness.user.id
    assert context.metadata_json == {
        "channel": "web",
        "telegram_account_id": str(account.id),
        "reason": "user_unlink",
    }
    assert "555" not in repr(event)


@pytest.mark.asyncio
async def test_unlinking_when_nothing_is_linked_is_idempotent_and_not_audited(
    harness: Harness,
) -> None:
    harness.service.revoke_result = None

    first = await harness.client.delete(BASE)
    second = await harness.client.delete(BASE)

    assert first.status_code == second.status_code == 204
    assert harness.audit.events == []


@pytest.mark.asyncio
async def test_unlinking_still_works_when_the_feature_is_switched_off(harness: Harness) -> None:
    harness.use_settings(telegram_enabled=False)

    response = await harness.client.delete(BASE)

    assert response.status_code == 204
    assert harness.service.revoked == [(harness.user.id, "user_unlink")]


@pytest.mark.asyncio
async def test_endpoints_require_authentication(app: FastAPI, client: AsyncClient) -> None:
    app.dependency_overrides[get_settings] = lambda: build_settings()
    try:
        assert (await client.get(BASE)).status_code == 401
        assert (await client.post(f"{BASE}/link-token")).status_code == 401
        assert (await client.delete(f"{BASE}/link-token")).status_code == 401
        assert (await client.delete(BASE)).status_code == 401
    finally:
        app.dependency_overrides.clear()
