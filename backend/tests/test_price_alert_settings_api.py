from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.v1.price_alerts import (
    get_audit_log_service,
    get_price_alert_settings_service,
)
from app.auth.dependencies import get_current_user
from app.db.session import get_db_session
from app.models import (
    Permission,
    PriceAlertScanState,
    PriceAlertSetting,
    Role,
    User,
    UserStatus,
)
from app.services.price_alert_settings_service import (
    SETTINGS_FIELD_LABELS,
    PriceAlertSettingsUpdate,
    PriceAlertSettingsValues,
    validate_threshold_order,
)

VALID_PAYLOAD: dict[str, Any] = {
    "is_enabled": True,
    "anomaly_enabled": False,
    "reference_working_days": 7,
    "light_from_percent": "2.50",
    "medium_from_percent": "5.00",
    "large_over_percent": "10.00",
    "anomaly_percent": "30.00",
    "anomaly_lookback_days": 30,
    "max_trigger_delay_working_days": 3,
    "staff_lookback_days": 90,
    "dedupe_window_days": 14,
    "immediate_cap_per_scan": 30,
    "digest_hour_local": 8,
    "reference_fallback_days": 30,
}


class MockSession:
    def __init__(self) -> None:
        self.committed = False

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, instance: object) -> None:
        pass


class MockAuditLogService:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def log_event(self, **kwargs: Any) -> None:
        self.events.append(kwargs)


class MockPriceAlertSettingsService:
    """Giữ đúng hợp đồng của service thật; hành vi trên DB được kiểm ở test tích hợp."""

    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.setting = PriceAlertSetting(
            id=uuid4(),
            singleton_key="default",
            reference_working_days=7,
            light_from_percent=Decimal("2.50"),
            medium_from_percent=Decimal("5.00"),
            large_over_percent=Decimal("10.00"),
            anomaly_percent=Decimal("30.00"),
            anomaly_lookback_days=30,
            max_trigger_delay_working_days=3,
            staff_lookback_days=90,
            dedupe_window_days=14,
            immediate_cap_per_scan=30,
            digest_hour_local=8,
            reference_fallback_days=30,
            is_enabled=False,
            anomaly_enabled=False,
            created_at=now,
            updated_at=now,
        )
        self.scan_state = PriceAlertScanState(id=uuid4(), singleton_key="default", updated_at=now)

    async def get_or_create_settings(self) -> PriceAlertSetting:
        return self.setting

    async def get_or_create_scan_state(self) -> PriceAlertScanState:
        return self.scan_state

    async def update_settings(
        self,
        *,
        values: PriceAlertSettingsValues,
        updated_by_id: object,
    ) -> PriceAlertSettingsUpdate:
        validate_threshold_order(
            light=values.light_from_percent,
            medium=values.medium_from_percent,
            large=values.large_over_percent,
            anomaly=values.anomaly_percent,
        )
        changes: list[dict[str, str]] = []
        for field, label in SETTINGS_FIELD_LABELS:
            old_value = getattr(self.setting, field)
            new_value = getattr(values, field)
            if old_value == new_value:
                continue
            changes.append(
                {
                    "field": field,
                    "label": label,
                    "old_value": _render(old_value),
                    "new_value": _render(new_value),
                },
            )
            setattr(self.setting, field, new_value)
        if values.is_enabled:
            self.scan_state.enabled_since = datetime.now(UTC)
        return PriceAlertSettingsUpdate(
            setting=self.setting,
            scan_state=self.scan_state,
            changes=changes,
        )


def _render(value: object) -> str:
    return str(value).lower() if isinstance(value, bool) else str(value)


def _build_user(permission_codes: list[str]) -> User:
    role = Role(id=uuid4(), name="alert-role", is_system=False)
    role.permissions = [Permission(id=uuid4(), code=code) for code in permission_codes]
    user = User(id=uuid4(), email="manager@example.com", status=UserStatus.ACTIVE)
    user.roles = [role]
    return user


@pytest.fixture
def override_dependencies(
    app: FastAPI,
) -> Generator[
    tuple[MockPriceAlertSettingsService, MockAuditLogService, MockSession],
    None,
    None,
]:
    settings_service = MockPriceAlertSettingsService()
    audit_service = MockAuditLogService()
    session = MockSession()

    app.dependency_overrides[get_current_user] = lambda: _build_user(["price_alerts.manage"])
    app.dependency_overrides[get_price_alert_settings_service] = lambda: settings_service
    app.dependency_overrides[get_audit_log_service] = lambda: audit_service
    app.dependency_overrides[get_db_session] = lambda: session

    yield settings_service, audit_service, session

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_enabling_price_alerts_saves_logs_audit_and_get_returns_it(
    client: AsyncClient,
    override_dependencies: tuple[
        MockPriceAlertSettingsService,
        MockAuditLogService,
        MockSession,
    ],
) -> None:
    _, audit_service, session = override_dependencies

    response = await client.put("/api/v1/price-alert-settings", json=VALID_PAYLOAD)

    assert response.status_code == 200
    body = response.json()
    assert body["is_enabled"] is True
    assert body["light_from_percent"] == "2.50"
    assert body["large_over_percent"] == "10.00"
    assert body["enabled_since"] is not None
    assert session.committed is True

    assert len(audit_service.events) == 1
    event = audit_service.events[0]
    assert event["action"] == "price_alerts.settings_updated"
    assert event["entity_type"] == "price_alert_setting"
    changes = event["context"].metadata_json["changes"]
    assert changes == [
        {
            "field": "is_enabled",
            "label": "Bật thông báo biến động giá",
            "old_value": "false",
            "new_value": "true",
        },
    ]
    assert all(isinstance(value, str) for change in changes for value in change.values())

    read_back = await client.get("/api/v1/price-alert-settings")
    assert read_back.status_code == 200
    assert read_back.json()["is_enabled"] is True


@pytest.mark.asyncio
async def test_get_returns_every_contract_field_with_decimal_strings(
    client: AsyncClient,
    override_dependencies: tuple[
        MockPriceAlertSettingsService,
        MockAuditLogService,
        MockSession,
    ],
) -> None:
    response = await client.get("/api/v1/price-alert-settings")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "is_enabled",
        "anomaly_enabled",
        "reference_working_days",
        "light_from_percent",
        "medium_from_percent",
        "large_over_percent",
        "anomaly_percent",
        "anomaly_lookback_days",
        "max_trigger_delay_working_days",
        "staff_lookback_days",
        "dedupe_window_days",
        "immediate_cap_per_scan",
        "digest_hour_local",
        "reference_fallback_days",
        "enabled_since",
        "updated_at",
        "updated_by_id",
    }
    assert body["is_enabled"] is False
    assert body["light_from_percent"] == "2.50"
    assert body["medium_from_percent"] == "5.00"
    assert body["large_over_percent"] == "10.00"
    assert body["anomaly_percent"] == "30.00"
    assert body["enabled_since"] is None


@pytest.mark.asyncio
async def test_put_without_changes_does_not_write_an_audit_event(
    client: AsyncClient,
    override_dependencies: tuple[
        MockPriceAlertSettingsService,
        MockAuditLogService,
        MockSession,
    ],
) -> None:
    _, audit_service, session = override_dependencies

    response = await client.put(
        "/api/v1/price-alert-settings",
        json={**VALID_PAYLOAD, "is_enabled": False},
    )

    assert response.status_code == 200
    assert audit_service.events == []
    assert session.committed is True


@pytest.mark.asyncio
async def test_threshold_changes_are_audited_with_old_and_new_values(
    client: AsyncClient,
    override_dependencies: tuple[
        MockPriceAlertSettingsService,
        MockAuditLogService,
        MockSession,
    ],
) -> None:
    _, audit_service, _ = override_dependencies

    response = await client.put(
        "/api/v1/price-alert-settings",
        json={**VALID_PAYLOAD, "is_enabled": False, "medium_from_percent": "6.00"},
    )

    assert response.status_code == 200
    changes = audit_service.events[0]["context"].metadata_json["changes"]
    assert changes == [
        {
            "field": "medium_from_percent",
            "label": "Ngưỡng Trung bình từ (%)",
            "old_value": "5.00",
            "new_value": "6.00",
        },
    ]


@pytest.mark.parametrize(
    "overrides",
    [
        {"light_from_percent": "5.00"},
        {"medium_from_percent": "2.50"},
        {"large_over_percent": "5.00"},
        {"anomaly_percent": "10.00"},
        {"anomaly_percent": "9.00"},
    ],
)
@pytest.mark.asyncio
async def test_unordered_thresholds_are_rejected_with_422(
    client: AsyncClient,
    override_dependencies: tuple[
        MockPriceAlertSettingsService,
        MockAuditLogService,
        MockSession,
    ],
    overrides: dict[str, str],
) -> None:
    _, audit_service, session = override_dependencies

    response = await client.put("/api/v1/price-alert-settings", json={**VALID_PAYLOAD, **overrides})

    assert response.status_code == 422
    assert audit_service.events == []
    assert session.committed is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"light_from_percent": "0"},
        {"light_from_percent": "-1"},
        {"large_over_percent": "100.01"},
        {"anomaly_percent": "1000.00"},
        {"light_from_percent": "2.555"},
        {"reference_working_days": 0},
        {"reference_working_days": 31},
        {"anomaly_lookback_days": 366},
        {"max_trigger_delay_working_days": -1},
        {"staff_lookback_days": 0},
        {"dedupe_window_days": 91},
        {"immediate_cap_per_scan": 0},
        {"immediate_cap_per_scan": 501},
        {"digest_hour_local": 24},
        {"digest_hour_local": -1},
        {"reference_fallback_days": -1},
        {"reference_fallback_days": 366},
        {"is_enabled": "maybe"},
    ],
)
@pytest.mark.asyncio
async def test_out_of_range_values_are_rejected_with_422(
    client: AsyncClient,
    override_dependencies: tuple[
        MockPriceAlertSettingsService,
        MockAuditLogService,
        MockSession,
    ],
    overrides: dict[str, Any],
) -> None:
    response = await client.put("/api/v1/price-alert-settings", json={**VALID_PAYLOAD, **overrides})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_put_requires_every_field_because_it_replaces_the_configuration(
    client: AsyncClient,
    override_dependencies: tuple[
        MockPriceAlertSettingsService,
        MockAuditLogService,
        MockSession,
    ],
) -> None:
    partial = {key: value for key, value in VALID_PAYLOAD.items() if key != "digest_hour_local"}
    no_fallback = {k: v for k, v in VALID_PAYLOAD.items() if k != "reference_fallback_days"}

    response = await client.put("/api/v1/price-alert-settings", json=partial)
    without_fallback = await client.put("/api/v1/price-alert-settings", json=no_fallback)

    assert response.status_code == 422
    assert without_fallback.status_code == 422  # không âm thầm đặt lại gốc dự phòng về 30


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["get", "put"])
async def test_user_without_manage_permission_gets_403(
    app: FastAPI,
    client: AsyncClient,
    override_dependencies: tuple[
        MockPriceAlertSettingsService,
        MockAuditLogService,
        MockSession,
    ],
    method: str,
) -> None:
    _, audit_service, session = override_dependencies
    app.dependency_overrides[get_current_user] = lambda: _build_user(
        ["price_alerts.receive_all", "quotify_settings.update"],
    )

    if method == "get":
        response = await client.get("/api/v1/price-alert-settings")
    else:
        response = await client.put("/api/v1/price-alert-settings", json=VALID_PAYLOAD)

    assert response.status_code == 403
    assert audit_service.events == []
    assert session.committed is False


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["get", "put"])
async def test_unauthenticated_request_gets_401(client: AsyncClient, method: str) -> None:
    if method == "get":
        response = await client.get("/api/v1/price-alert-settings")
    else:
        response = await client.put("/api/v1/price-alert-settings", json=VALID_PAYLOAD)

    assert response.status_code == 401
