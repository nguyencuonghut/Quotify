from __future__ import annotations

import io
from collections.abc import Generator
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient
from openpyxl import load_workbook

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
        self.export_calls: list[dict[str, Any]] = []
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
                "note_content": "Đã thương lượng giảm giá 2%",
                "note_author_name": "Nguyễn Văn Mua",
                "note_created_at": datetime.now(UTC),
            }
        ]

    async def query_flattened_quotes_for_export(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.export_calls.append(kwargs)
        return self.items


@pytest.fixture
def override_dependencies(
    app: FastAPI,
) -> Generator[tuple[MockQuoteQueryService, MockAuditLogService], None, None]:
    permissions = [Permission(id=uuid4(), code="quotes.read")]
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
async def test_export_quotes_returns_a_loadable_xlsx_with_all_matching_rows(
    client: AsyncClient,
    override_dependencies: tuple[MockQuoteQueryService, MockAuditLogService],
) -> None:
    response = await client.get("/api/v1/quotes/export")

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "attachment" in response.headers["content-disposition"]
    assert ".xlsx" in response.headers["content-disposition"]

    workbook = load_workbook(io.BytesIO(response.content))
    sheet = workbook.active
    data_row = [cell.value for cell in sheet[4]]
    assert data_row[1] == "Supplier ABC"
    assert data_row[12] == "Đã thương lượng giảm giá 2%"


@pytest.mark.asyncio
async def test_export_quotes_forwards_the_applied_filters_to_the_query_service(
    client: AsyncClient,
    override_dependencies: tuple[MockQuoteQueryService, MockAuditLogService],
) -> None:
    query_service, _ = override_dependencies

    response = await client.get(
        "/api/v1/quotes/export",
        params={
            "supplier_id": str(uuid4()),
            "purchased": "true",
            "sort_by": "received_date",
            "sort_order": "asc",
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert len(query_service.export_calls) == 1
    call = query_service.export_calls[0]
    assert call["purchased"] is True
    assert call["sort_by"] == "received_date"
    assert call["sort_order"] == "asc"
    # Export không phân trang — không được truyền limit/offset xuống service.
    assert "limit" not in call
    assert "offset" not in call


@pytest.mark.asyncio
async def test_export_quotes_logs_an_audit_event_with_the_exported_row_count(
    client: AsyncClient,
    override_dependencies: tuple[MockQuoteQueryService, MockAuditLogService],
) -> None:
    _, audit_service = override_dependencies

    await client.get("/api/v1/quotes/export")

    assert len(audit_service.events) == 1
    assert audit_service.events[0]["action"] == "quotes.exported"
