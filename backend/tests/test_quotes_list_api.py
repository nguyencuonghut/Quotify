from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient

from app.api.v1.quotes import get_audit_log_service, get_quote_query_service
from app.auth.dependencies import get_current_user
from app.db.session import get_db_session
from app.models import Permission, Role, User, UserStatus


class MockSession:
    async def commit(self) -> None:
        pass


class MockAuditLogService:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def log_event(self, **kwargs: Any) -> None:
        self.events.append(kwargs)


class MockQuoteQueryService:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.items = [
            {
                "id": uuid4(),
                "quote_id": uuid4(),
                "quote_version_id": uuid4(),
                "supplier_id": uuid4(),
                "supplier_name": "Supplier ABC",
                "supplier_code": "S_ABC",
                "material_id": uuid4(),
                "material_name": "Corn",
                "material_code": "M_CORN",
                "material_type_name": "Nguyên liệu",
                "material_type_code": "NL",
                "received_date": date(2026, 7, 29),
                "delivery_month": date(2026, 8, 1),
                "price_original": 250.50,
                "currency": "USD",
                "unit": "MT",
                "exchange_rate": 25450.00,
                "exchange_rate_source": "Vietcombank",
                "import_tax_rate_percent": 0.00,
                "processing_cost_vnd_per_kg": 150.00,
                "price_converted_vnd_per_kg": 6525.23,
                "purchased": True,
                "version_number": 1,
                "version_status": "confirmed",
                "created_by_name": "Admin User",
                "created_at": datetime.now(UTC),
            }
        ]

    async def query_flattened_quotes(self, **kwargs: Any) -> tuple[list[dict[str, Any]], int]:
        self.calls.append(kwargs)
        return self.items, len(self.items)


@pytest.fixture
def override_dependencies(
    app: FastAPI,
) -> Generator[tuple[MockQuoteQueryService, MockAuditLogService], None, None]:
    permissions = [
        Permission(id=uuid4(), code="quotes.read"),
    ]
    role = Role(id=uuid4(), name="quote-reader", is_system=False)
    role.permissions = permissions
    user = User(
        id=uuid4(),
        email="reader@example.com",
        status=UserStatus.ACTIVE,
        full_name="Reader User",
    )
    user.roles = [role]

    query_service = MockQuoteQueryService()
    audit_service = MockAuditLogService()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_quote_query_service] = lambda: query_service
    app.dependency_overrides[get_audit_log_service] = lambda: audit_service
    app.dependency_overrides[get_db_session] = lambda: MockSession()

    yield query_service, audit_service

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_quotes_api_success_and_audit(
    client: AsyncClient,
    override_dependencies: tuple[MockQuoteQueryService, MockAuditLogService],
) -> None:
    _, audit_service = override_dependencies

    response = await client.get("/api/v1/quotes")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["supplier_name"] == "Supplier ABC"
    assert data["items"][0]["material_name"] == "Corn"
    assert data["items"][0]["purchased"] is True

    # Check audit log
    assert len(audit_service.events) == 1
    assert audit_service.events[0]["action"] == "quotes.list_viewed"


@pytest.mark.asyncio
async def test_list_quotes_api_rejects_oversized_limit(
    client: AsyncClient,
    override_dependencies: tuple[MockQuoteQueryService, MockAuditLogService],
) -> None:
    query_service, audit_service = override_dependencies

    response = await client.get("/api/v1/quotes?limit=500")

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert query_service.calls == []
    assert audit_service.events == []
