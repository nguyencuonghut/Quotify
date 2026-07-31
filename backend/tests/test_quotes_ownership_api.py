from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient

from app.api.v1.quotes import get_quote_service
from app.api.v1.quotify_settings import get_audit_log_service
from app.auth.dependencies import get_current_user
from app.db.session import get_db_session
from app.models import Permission, Quote, QuoteVersion, Role, Supplier, User, UserStatus


class MockSession:
    def __init__(self, quote: Quote) -> None:
        self.quote = quote
        self.committed = False

    async def get(self, model_class: type[Any], id: UUID) -> Any:
        if model_class is Quote and id == self.quote.id:
            return self.quote
        return None

    async def commit(self) -> None:
        self.committed = True


class MockAuditLogService:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def log_event(self, **kwargs: Any) -> None:
        self.events.append(kwargs)


class MockQuoteService:
    def __init__(self, quote_id: UUID) -> None:
        self.quote_id = quote_id
        self.create_version_calls: list[dict[str, Any]] = []

    async def create_version(self, **kwargs: Any) -> QuoteVersion:
        self.create_version_calls.append(kwargs)
        version = QuoteVersion(
            id=uuid4(),
            quote_id=self.quote_id,
            version_number=2,
            received_date=kwargs["received_date"],
            status="draft",
            is_backfilled=kwargs["is_backfilled"],
            backfill_reason=kwargs["backfill_reason"],
            correction_reason=kwargs["correction_reason"],
            created_by_id=kwargs["created_by_id"],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        version.lines = []
        return version


def make_user(*, role_name: str, user_id: UUID | None = None) -> User:
    permissions = [Permission(id=uuid4(), code="quotes.update")]
    role = Role(id=uuid4(), name=role_name, is_system=role_name in {"admin", "user"})
    role.permissions = permissions
    user = User(
        id=user_id or uuid4(),
        email=f"{role_name}-{uuid4()}@example.com",
        status=UserStatus.ACTIVE,
        full_name=f"{role_name.title()} User",
    )
    user.roles = [role]
    return user


@pytest.fixture
def quote_version_payload() -> dict[str, Any]:
    return {
        "received_date": "2026-07-31",
        "is_backfilled": False,
        "backfill_reason": None,
        "correction_reason": "Sửa giá nhập nhầm.",
        "lines": [
            {
                "material_id": str(uuid4()),
                "price_original": "12000.00",
                "currency": "VND",
                "unit": "KG",
                "delivery_month": "2026-08-01",
            }
        ],
    }


@pytest.fixture
def ownership_dependencies(
    app: FastAPI,
) -> Generator[tuple[Quote, MockQuoteService, MockSession, MockAuditLogService, User], None, None]:
    owner_id = uuid4()
    quote = Quote(
        id=uuid4(),
        supplier_id=uuid4(),
        created_by_id=owner_id,
    )
    quote.supplier = Supplier(id=quote.supplier_id, code="SUP-A", name="Supplier A", status="active")

    current_user = make_user(role_name="user")
    quote_service = MockQuoteService(quote.id)
    session = MockSession(quote)
    audit_service = MockAuditLogService()

    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_quote_service] = lambda: quote_service
    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_audit_log_service] = lambda: audit_service

    yield quote, quote_service, session, audit_service, current_user

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_user_cannot_create_correction_version_for_another_users_quote(
    client: AsyncClient,
    ownership_dependencies: tuple[Quote, MockQuoteService, MockSession, MockAuditLogService, User],
    quote_version_payload: dict[str, Any],
) -> None:
    quote, quote_service, session, audit_service, _ = ownership_dependencies

    response = await client.post(f"/api/v1/quotes/{quote.id}/versions", json=quote_version_payload)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"] == "Bạn chỉ được thao tác trên phiếu báo giá do mình tạo."
    assert quote_service.create_version_calls == []
    assert session.committed is False
    assert audit_service.events == []


@pytest.mark.asyncio
async def test_admin_can_create_correction_version_for_any_quote(
    app: FastAPI,
    client: AsyncClient,
    ownership_dependencies: tuple[Quote, MockQuoteService, MockSession, MockAuditLogService, User],
    quote_version_payload: dict[str, Any],
) -> None:
    quote, quote_service, session, audit_service, _ = ownership_dependencies
    admin_user = make_user(role_name="admin")
    app.dependency_overrides[get_current_user] = lambda: admin_user

    response = await client.post(f"/api/v1/quotes/{quote.id}/versions", json=quote_version_payload)

    assert response.status_code == status.HTTP_200_OK
    assert quote_service.create_version_calls[0]["created_by_id"] == admin_user.id
    assert session.committed is True
    assert len(audit_service.events) == 1


@pytest.mark.asyncio
async def test_user_can_create_correction_version_for_owned_quote(
    app: FastAPI,
    client: AsyncClient,
    ownership_dependencies: tuple[Quote, MockQuoteService, MockSession, MockAuditLogService, User],
    quote_version_payload: dict[str, Any],
) -> None:
    quote, quote_service, session, audit_service, _ = ownership_dependencies
    owner_user = make_user(role_name="user", user_id=quote.created_by_id)
    app.dependency_overrides[get_current_user] = lambda: owner_user

    response = await client.post(f"/api/v1/quotes/{quote.id}/versions", json=quote_version_payload)

    assert response.status_code == status.HTTP_200_OK
    assert quote_service.create_version_calls[0]["created_by_id"] == owner_user.id
    assert session.committed is True
    assert len(audit_service.events) == 1
