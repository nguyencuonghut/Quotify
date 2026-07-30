from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient

from app.api.v1.quotify_dashboard import get_quotify_dashboard_service
from app.auth.dependencies import get_current_user
from app.models import Permission, Role, User, UserStatus


class MockQuotifyDashboardService:
    def __init__(self) -> None:
        self.entry_kpi_kwargs: dict[str, Any] | None = None
        self.price_trend_kwargs: dict[str, Any] | None = None
        self.weekly_entry_activity_kwargs: dict[str, Any] | None = None

    async def get_entry_kpis(self, **kwargs: Any) -> dict[str, Any]:
        self.entry_kpi_kwargs = kwargs
        return {
            "total_quote_count": 2,
            "user_kpis": [
                {
                    "user_id": uuid4(),
                    "user_email": "buyer@example.com",
                    "user_full_name": "Buyer One",
                    "user_label": "Buyer One",
                    "quote_count": 2,
                }
            ],
        }

    async def get_price_trends(self, **kwargs: Any) -> dict[str, Any]:
        self.price_trend_kwargs = kwargs
        now = datetime(2026, 7, 21, 9, 0, tzinfo=UTC)
        material_id = uuid4()
        delivery_month = date(2026, 8, 1)
        line_id = uuid4()
        point = {
            "received_date": date(2026, 7, 20),
            "delivery_month": delivery_month,
            "converted_price_vnd_per_kg": Decimal("6500.00"),
            "supplier_id": uuid4(),
            "supplier_name": "Supplier ABC",
            "supplier_code": "ABC",
            "supplier_type": "domestic",
            "supplier_label": "Supplier ABC (ABC)",
            "material_id": material_id,
            "material_name": "Bắp hạt",
            "material_code": "CORN",
            "quote_id": uuid4(),
            "quote_version_id": uuid4(),
            "line_id": line_id,
            "purchased": True,
            "purchase_marked_at": now,
            "confirmed_at": now,
        }
        summary = {
            "min_price": Decimal("6500.00"),
            "max_price": Decimal("6500.00"),
            "avg_price": Decimal("6500.00"),
            "total_lines": 1,
            "total_quotes": 1,
            "purchased_lines": 1,
        }
        return {
            "summary": summary,
            "points": [point],
            "purchase_contexts": [
                {
                    "purchased_line_id": line_id,
                    "quote_id": point["quote_id"],
                    "material_id": material_id,
                    "delivery_month": delivery_month,
                    "purchase_marked_at": now,
                    "at_purchase": summary,
                    "after_purchase": {
                        "min_price": None,
                        "max_price": None,
                        "avg_price": None,
                        "total_lines": 0,
                        "total_quotes": 0,
                        "purchased_lines": 0,
                    },
                }
            ],
        }

    async def get_weekly_entry_activity(self, **kwargs: Any) -> dict[str, Any]:
        self.weekly_entry_activity_kwargs = kwargs
        user_with_quotes_id = uuid4()
        user_without_quotes_id = uuid4()
        return {
            "week_start": date(2026, 7, 27),
            "week_end": date(2026, 8, 2),
            "total_quote_count": 3,
            "active_user_count": 2,
            "users_with_quotes": 1,
            "users_without_quotes": 1,
            "user_activities": [
                {
                    "user_id": user_with_quotes_id,
                    "user_email": "buyer@example.com",
                    "user_full_name": "Buyer One",
                    "user_label": "Buyer One",
                    "quote_count": 3,
                    "last_quote_created_at": datetime(2026, 7, 28, 9, 0, tzinfo=UTC),
                    "has_warning": False,
                },
                {
                    "user_id": user_without_quotes_id,
                    "user_email": "quiet@example.com",
                    "user_full_name": "Quiet User",
                    "user_label": "Quiet User",
                    "quote_count": 0,
                    "last_quote_created_at": None,
                    "has_warning": True,
                },
            ],
        }


@pytest.fixture
def override_dependencies(app: FastAPI) -> Generator[MockQuotifyDashboardService, None, None]:
    permission = Permission(id=uuid4(), code="dashboard.read")
    role = Role(id=uuid4(), name="dashboard-reader", is_system=False)
    role.permissions = [permission]
    user = User(
        id=uuid4(),
        email="reader@example.com",
        status=UserStatus.ACTIVE,
        full_name="Reader User",
    )
    user.roles = [role]

    dashboard_service = MockQuotifyDashboardService()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_quotify_dashboard_service] = lambda: dashboard_service

    yield dashboard_service

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_entry_kpis_endpoint_requires_dashboard_permission_and_passes_filters(
    client: AsyncClient,
    override_dependencies: MockQuotifyDashboardService,
) -> None:
    material_id = uuid4()

    response = await client.get(
        "/api/v1/dashboard/quotify/entry-kpis",
        params={
            "material_id": str(material_id),
            "delivery_month": "2026-08-01",
            "received_date_start": "2026-07-01",
            "received_date_end": "2026-07-31",
            "supplier_type": "domestic",
        },
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total_quote_count"] == 2
    assert data["user_kpis"][0]["user_label"] == "Buyer One"
    assert override_dependencies.entry_kpi_kwargs == {
        "material_id": material_id,
        "delivery_month": date(2026, 8, 1),
        "received_date_start": date(2026, 7, 1),
        "received_date_end": date(2026, 7, 31),
        "supplier_type": "domestic",
    }


@pytest.mark.asyncio
async def test_price_trends_endpoint_returns_summary_points_and_purchase_contexts(
    client: AsyncClient,
    override_dependencies: MockQuotifyDashboardService,
) -> None:
    response = await client.get("/api/v1/dashboard/quotify/price-trends")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["summary"]["min_price"] == "6500.00"
    assert data["points"][0]["purchased"] is True
    assert data["points"][0]["supplier_type"] == "domestic"
    assert data["points"][0]["supplier_label"] == "Supplier ABC (ABC)"
    assert data["purchase_contexts"][0]["at_purchase"]["total_lines"] == 1


@pytest.mark.asyncio
async def test_weekly_entry_activity_endpoint_passes_week_and_user_filters(
    client: AsyncClient,
    override_dependencies: MockQuotifyDashboardService,
) -> None:
    user_id = uuid4()

    response = await client.get(
        "/api/v1/dashboard/quotify/weekly-entry-activity",
        params={
            "week_start": "2026-07-29",
            "user_id": str(user_id),
        },
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["week_start"] == "2026-07-27"
    assert data["week_end"] == "2026-08-02"
    assert data["total_quote_count"] == 3
    assert data["users_without_quotes"] == 1
    assert data["user_activities"][1]["has_warning"] is True
    assert override_dependencies.weekly_entry_activity_kwargs == {
        "week_start": date(2026, 7, 29),
        "user_id": user_id,
    }
