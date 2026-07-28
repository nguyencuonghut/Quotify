from __future__ import annotations

from collections.abc import Generator
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.v1.exchange_rates import get_exchange_rate_service
from app.auth.dependencies import get_current_user
from app.models import Permission, Role, User, UserStatus
from app.services.exchange_rate_service import ExchangeRateResult


class MockExchangeRateService:
    async def get_usd_sell_today(self) -> ExchangeRateResult:
        return ExchangeRateResult(
            currency="USD",
            rate=Decimal("26100.00"),
            source="Vietcombank USD bán ra",
            retrieved_at=datetime(2026, 7, 28, 8, 6, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh")),
        )


@pytest.fixture
def override_dependencies(app: FastAPI) -> Generator[None, None, None]:
    permission = Permission(id=uuid4(), code="exchange_rates.read")
    role = Role(id=uuid4(), name="exchange-reader", is_system=False)
    role.permissions = [permission]
    user = User(id=uuid4(), email="reader@example.com", status=UserStatus.ACTIVE)
    user.roles = [role]

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_exchange_rate_service] = lambda: MockExchangeRateService()

    yield

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_usd_sell_today_returns_rate_contract(
    client: AsyncClient,
    override_dependencies: Any,
) -> None:
    response = await client.get("/api/v1/exchange-rates/usd-sell/today")

    assert response.status_code == 200
    assert response.json() == {
        "currency": "USD",
        "rate": "26100.00",
        "source": "Vietcombank USD bán ra",
        "retrieved_at": "2026-07-28T08:06:00+07:00",
    }
