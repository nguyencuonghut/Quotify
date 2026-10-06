from __future__ import annotations

from collections.abc import Callable, Generator
from datetime import date
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient

from app.api.v1.quotify_dashboard import get_quotify_material_freshness_service
from app.auth.dependencies import get_current_user
from app.models import Permission, Role, User, UserStatus


class MockMaterialFreshnessService:
    def __init__(self) -> None:
        self.kwargs: dict[str, Any] | None = None

    async def get_material_freshness(self, **kwargs: Any) -> dict[str, Any]:
        self.kwargs = kwargs
        material_id = uuid4()
        return {
            "week_start": date(2026, 10, 5),
            "week_end": date(2026, 10, 11),
            "as_of_date": date(2026, 10, 6),
            "summary": {
                "watched_count": 1,
                "updated_count": 0,
                "on_time_count": 0,
                "overdue_count": 1,
                "unwatched_updated_count": 0,
            },
            "items": [
                {
                    "material_id": material_id,
                    "material_code": "NGO",
                    "material_name": "Ngô hạt",
                    "material_type_id": uuid4(),
                    "material_type_name": "Nguyên liệu",
                    "is_watched": True,
                    "expected_interval_days": 7,
                    "update_count": 0,
                    "supplier_count": 0,
                    "last_received_date": date(2026, 9, 20),
                    "age_days": 16,
                    "status": "overdue",
                    "last_enterer_id": None,
                    "last_enterer_label": None,
                },
            ],
        }


@pytest.fixture
def make_user_with(
    app: FastAPI,
) -> Generator[Callable[[str], MockMaterialFreshnessService], None, None]:
    service = MockMaterialFreshnessService()

    def make(permission_code: str) -> MockMaterialFreshnessService:
        role = Role(id=uuid4(), name=f"role-{permission_code}", is_system=False)
        role.permissions = [Permission(id=uuid4(), code=permission_code)]
        user = User(
            id=uuid4(),
            email="reader@example.com",
            status=UserStatus.ACTIVE,
            full_name="Reader User",
        )
        user.roles = [role]
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_quotify_material_freshness_service] = lambda: service
        return service

    yield make
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_material_freshness_endpoint_is_open_to_price_alert_managers(
    client: AsyncClient,
    make_user_with: Callable[[str], MockMaterialFreshnessService],
) -> None:
    service = make_user_with("price_alerts.manage")

    response = await client.get(
        "/api/v1/dashboard/quotify/material-freshness",
        params={"week_start": "2026-10-07"},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["week_start"] == "2026-10-05"
    assert data["as_of_date"] == "2026-10-06"
    assert data["summary"]["overdue_count"] == 1
    assert data["items"][0]["status"] == "overdue"
    assert data["items"][0]["last_received_date"] == "2026-09-20"
    assert service.kwargs == {"week_start": date(2026, 10, 7)}


@pytest.mark.asyncio
async def test_material_freshness_endpoint_without_week_uses_the_service_default(
    client: AsyncClient,
    make_user_with: Callable[[str], MockMaterialFreshnessService],
) -> None:
    service = make_user_with("price_alerts.manage")

    response = await client.get("/api/v1/dashboard/quotify/material-freshness")

    assert response.status_code == status.HTTP_200_OK
    assert service.kwargs == {"week_start": None}


@pytest.mark.asyncio
async def test_material_freshness_endpoint_is_forbidden_with_dashboard_read_only(
    client: AsyncClient,
    make_user_with: Callable[[str], MockMaterialFreshnessService],
) -> None:
    service = make_user_with("dashboard.read")

    response = await client.get("/api/v1/dashboard/quotify/material-freshness")

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert service.kwargs is None


@pytest.mark.asyncio
async def test_material_freshness_endpoint_rejects_an_invalid_week(
    client: AsyncClient,
    make_user_with: Callable[[str], MockMaterialFreshnessService],
) -> None:
    make_user_with("price_alerts.manage")

    response = await client.get(
        "/api/v1/dashboard/quotify/material-freshness",
        params={"week_start": "khong-phai-ngay"},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
@pytest.mark.parametrize("week_start", ["9999-12-31", "1900-01-01"])
async def test_material_freshness_endpoint_rejects_a_week_outside_the_supported_range(
    client: AsyncClient,
    make_user_with: Callable[[str], MockMaterialFreshnessService],
    week_start: str,
) -> None:
    service = make_user_with("price_alerts.manage")

    response = await client.get(
        "/api/v1/dashboard/quotify/material-freshness",
        params={"week_start": week_start},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert service.kwargs is None
