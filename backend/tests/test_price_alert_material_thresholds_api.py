from __future__ import annotations

from collections.abc import Generator
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.v1.alert_preferences import get_alert_preference_service
from app.api.v1.price_alert_material_thresholds import (
    get_audit_log_service,
    get_material_threshold_service,
)
from app.auth.dependencies import get_current_user
from app.db.session import get_db_session
from app.models import Permission, Role, User, UserAlertPreference, UserStatus
from app.services.price_alert_material_threshold_service import (
    EffectiveThresholds,
    FreshnessChange,
    FreshnessConfig,
    MaterialNotFoundError,
    MaterialThresholdChange,
    MaterialThresholdPage,
    MaterialThresholdView,
    ThresholdOverride,
    _diff,
    _freshness_diff,
    validate_override,
)
from app.services.user_alert_preference_service import AlertPreferences, build_preferences

DEFAULTS = EffectiveThresholds(
    light_from_percent=Decimal("2.50"),
    medium_from_percent=Decimal("5.00"),
    large_over_percent=Decimal("10.00"),
    anomaly_percent=Decimal("30.00"),
)
MATERIAL_ID = uuid4()
BASE = "/api/v1/price-alert-settings/materials"
VALID = {
    "light_from_percent": "1.00",
    "medium_from_percent": "3.00",
    "large_over_percent": "6.00",
    "anomaly_percent": None,
}


FRESHNESS_BODY = {"is_watched": True, "expected_interval_days": 14}


class MockSession:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


class MockAuditLogService:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def log_event(self, **kwargs: Any) -> None:
        self.events.append(kwargs)


class MockThresholdService:
    def __init__(self) -> None:
        self.override: ThresholdOverride | None = None
        self.freshness: FreshnessConfig | None = None
        self.calls: list[dict[str, Any]] = []

    async def list_materials(self, *, limit: int, offset: int, search: str | None) -> Any:
        self.calls.append({"limit": limit, "offset": offset, "search": search})
        view = MaterialThresholdView(
            material_id=MATERIAL_ID,
            code="NGO",
            name="Ngô hạt",
            override=self.override,
            effective=DEFAULTS,
            freshness=self.freshness,
        )
        return MaterialThresholdPage(items=[view], total=1)

    async def set_override(
        self,
        *,
        material_id: UUID,
        light: Decimal,
        medium: Decimal,
        large: Decimal,
        anomaly: Decimal | None,
        updated_by_id: UUID,
    ) -> MaterialThresholdChange:
        if material_id != MATERIAL_ID:
            raise MaterialNotFoundError(str(material_id))
        new = ThresholdOverride(light, medium, large, anomaly)
        validate_override(new, default_anomaly=DEFAULTS.anomaly_percent)
        changes = _diff(self.override, new)
        self.override = new
        view = MaterialThresholdView(
            material_id=material_id,
            code="NGO",
            name="Ngô hạt",
            override=new,
            effective=EffectiveThresholds(light, medium, large, anomaly or Decimal("30.00")),
        )
        return MaterialThresholdChange(view=view, changes=changes)

    async def clear_override(self, *, material_id: UUID) -> list[dict[str, str]]:
        old, self.override = self.override, None
        return _diff(old, None)

    async def set_freshness(
        self,
        *,
        material_id: UUID,
        is_watched: bool,
        expected_interval_days: int,
        updated_by_id: UUID,
    ) -> FreshnessChange:
        if material_id != MATERIAL_ID:
            raise MaterialNotFoundError(str(material_id))
        new = FreshnessConfig(is_watched, expected_interval_days)
        changes = _freshness_diff(self.freshness, new)
        self.freshness = new
        return FreshnessChange(material_id=material_id, code="NGO", config=new, changes=changes)

    async def clear_freshness(self, *, material_id: UUID) -> list[dict[str, str]]:
        old, self.freshness = self.freshness, None
        return _freshness_diff(old, None)


class MockPreferenceService:
    def __init__(self) -> None:
        self.row: dict[str, Any] | None = None

    async def get(self, user: User) -> AlertPreferences:
        return self._build(user)

    async def upsert(
        self,
        user: User,
        *,
        is_enabled: bool,
        min_level: str | None,
        admin_receive_all: bool,
    ) -> AlertPreferences:
        if admin_receive_all and not any(r.name == "admin" for r in user.roles):
            raise PermissionError("no")
        self.row = {
            "is_enabled": is_enabled,
            "min_level": min_level,
            "admin_receive_all": admin_receive_all,
        }
        return self._build(user)

    def _build(self, user: User) -> AlertPreferences:
        row = UserAlertPreference(user_id=user.id, **self.row) if self.row else None
        return build_preferences(user, row)


def _build_user(role_names: list[str], permission_codes: list[str] | None = None) -> User:
    roles = []
    for name in role_names:
        role = Role(id=uuid4(), name=name, is_system=False)
        role.permissions = [Permission(id=uuid4(), code=c) for c in permission_codes or []]
        roles.append(role)
    user = User(id=uuid4(), email="u@example.com", status=UserStatus.ACTIVE)
    user.roles = roles
    return user


@pytest.fixture
def deps(
    app: FastAPI,
) -> Generator[tuple[MockThresholdService, MockAuditLogService, MockSession], None, None]:
    service = MockThresholdService()
    audit = MockAuditLogService()
    session = MockSession()
    pref = MockPreferenceService()
    app.dependency_overrides[get_current_user] = lambda: _build_user(
        ["alert-role"],
        ["price_alerts.manage"],
    )
    app.dependency_overrides[get_material_threshold_service] = lambda: service
    app.dependency_overrides[get_audit_log_service] = lambda: audit
    app.dependency_overrides[get_alert_preference_service] = lambda: pref
    app.dependency_overrides[get_db_session] = lambda: session
    yield service, audit, session
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_returns_contract_shape_and_forwards_paging(
    client: AsyncClient,
    deps: tuple[MockThresholdService, MockAuditLogService, MockSession],
) -> None:
    service, _, _ = deps
    response = await client.get(f"{BASE}?limit=50&offset=10&search=ng")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert set(item) == {"material_id", "code", "name", "override", "effective", "freshness"}
    assert item["override"] is None
    assert item["freshness"] is None
    assert item["effective"]["anomaly_percent"] == "30.00"
    assert service.calls == [{"limit": 50, "offset": 10, "search": "ng"}]


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["limit=101", "limit=0", "offset=-1"])
async def test_list_rejects_out_of_range_paging(
    client: AsyncClient,
    deps: tuple[MockThresholdService, MockAuditLogService, MockSession],
    query: str,
) -> None:
    assert (await client.get(f"{BASE}?{query}")).status_code == 422


@pytest.mark.asyncio
async def test_put_saves_override_and_audits_string_changes_with_material_id(
    client: AsyncClient,
    deps: tuple[MockThresholdService, MockAuditLogService, MockSession],
) -> None:
    _, audit, session = deps
    response = await client.put(f"{BASE}/{MATERIAL_ID}", json=VALID)

    assert response.status_code == 200
    body = response.json()
    assert body["material_id"] == str(MATERIAL_ID)
    assert body["override"]["light_from_percent"] == "1.00"
    assert body["override"]["anomaly_percent"] is None
    assert body["effective"]["anomaly_percent"] == "30.00"
    assert session.commits == 1

    assert len(audit.events) == 1
    event = audit.events[0]
    assert event["action"] == "price_alerts.threshold_updated"
    metadata = event["context"].metadata_json
    assert metadata["material_id"] == str(MATERIAL_ID)
    changes = metadata["changes"]
    assert [c["field"] for c in changes] == [
        "light_from_percent",
        "medium_from_percent",
        "large_over_percent",
    ]
    assert changes[0]["old_value"] == "mặc định"
    assert all(isinstance(v, str) for c in changes for v in c.values())


@pytest.mark.asyncio
async def test_put_same_values_twice_does_not_audit_again(
    client: AsyncClient,
    deps: tuple[MockThresholdService, MockAuditLogService, MockSession],
) -> None:
    _, audit, _ = deps
    await client.put(f"{BASE}/{MATERIAL_ID}", json=VALID)
    await client.put(f"{BASE}/{MATERIAL_ID}", json=VALID)

    assert len(audit.events) == 1


@pytest.mark.asyncio
async def test_put_unknown_material_is_404(
    client: AsyncClient,
    deps: tuple[MockThresholdService, MockAuditLogService, MockSession],
) -> None:
    _, audit, session = deps
    response = await client.put(f"{BASE}/{uuid4()}", json=VALID)

    assert response.status_code == 404
    assert audit.events == []
    assert session.commits == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"light_from_percent": "3.00"},
        {"medium_from_percent": "1.00"},
        {"large_over_percent": "3.00"},
        {"anomaly_percent": "6.00"},
        {"large_over_percent": "30.00"},  # anomaly mặc định 30 không lớn hơn Lớn
        {"anomaly_percent": "5.00"},
    ],
)
async def test_put_rejects_unordered_or_anomaly_not_above_large(
    client: AsyncClient,
    deps: tuple[MockThresholdService, MockAuditLogService, MockSession],
    overrides: dict[str, str],
) -> None:
    _, audit, session = deps
    response = await client.put(f"{BASE}/{MATERIAL_ID}", json={**VALID, **overrides})

    assert response.status_code == 422
    assert audit.events == []
    assert session.commits == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"light_from_percent": "0"},
        {"large_over_percent": "100.01"},
        {"light_from_percent": "1.005"},
        {"anomaly_percent": "0"},
    ],
)
async def test_put_rejects_out_of_range_values(
    client: AsyncClient,
    deps: tuple[MockThresholdService, MockAuditLogService, MockSession],
    overrides: dict[str, str],
) -> None:
    response = await client.put(f"{BASE}/{MATERIAL_ID}", json={**VALID, **overrides})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_put_requires_the_three_thresholds(
    client: AsyncClient,
    deps: tuple[MockThresholdService, MockAuditLogService, MockSession],
) -> None:
    payload = {k: v for k, v in VALID.items() if k != "medium_from_percent"}
    assert (await client.put(f"{BASE}/{MATERIAL_ID}", json=payload)).status_code == 422


@pytest.mark.asyncio
async def test_delete_is_idempotent_204_with_empty_body_and_audits_only_once(
    client: AsyncClient,
    deps: tuple[MockThresholdService, MockAuditLogService, MockSession],
) -> None:
    _, audit, _ = deps
    await client.put(f"{BASE}/{MATERIAL_ID}", json=VALID)
    audit.events.clear()

    first = await client.delete(f"{BASE}/{MATERIAL_ID}")
    second = await client.delete(f"{BASE}/{MATERIAL_ID}")
    unknown = await client.delete(f"{BASE}/{uuid4()}")

    assert (first.status_code, second.status_code, unknown.status_code) == (204, 204, 204)
    assert first.content == b""
    assert len(audit.events) == 1
    assert audit.events[0]["context"].metadata_json["changes"][0]["new_value"] == "mặc định"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", ""),
        ("put", f"/{MATERIAL_ID}"),
        ("delete", f"/{MATERIAL_ID}"),
        ("put", f"/{MATERIAL_ID}/freshness"),
        ("delete", f"/{MATERIAL_ID}/freshness"),
    ],
)
async def test_without_manage_permission_is_403_and_without_login_is_401(
    app: FastAPI,
    client: AsyncClient,
    deps: tuple[MockThresholdService, MockAuditLogService, MockSession],
    method: str,
    path: str,
) -> None:
    kwargs: dict[str, Any] = {}
    if method == "put":
        kwargs["json"] = FRESHNESS_BODY if path.endswith("/freshness") else VALID
    app.dependency_overrides[get_current_user] = lambda: _build_user(
        ["alert-role"],
        ["price_alerts.receive_all"],
    )
    assert (await client.request(method, BASE + path, **kwargs)).status_code == 403

    app.dependency_overrides.pop(get_current_user)
    assert (await client.request(method, BASE + path, **kwargs)).status_code == 401


# --- theo dõi độ mới của giá theo vật tư --------------------------------------


@pytest.mark.asyncio
async def test_list_shows_the_freshness_config_after_it_is_saved(
    client: AsyncClient,
    deps: tuple[MockThresholdService, MockAuditLogService, MockSession],
) -> None:
    await client.put(f"{BASE}/{MATERIAL_ID}/freshness", json=FRESHNESS_BODY)

    item = (await client.get(BASE)).json()["items"][0]

    assert item["freshness"] == {"is_watched": True, "expected_interval_days": 14}


@pytest.mark.asyncio
async def test_put_freshness_saves_audits_and_does_not_audit_an_unchanged_save(
    client: AsyncClient,
    deps: tuple[MockThresholdService, MockAuditLogService, MockSession],
) -> None:
    _, audit, session = deps

    response = await client.put(f"{BASE}/{MATERIAL_ID}/freshness", json=FRESHNESS_BODY)

    assert response.status_code == 200
    assert response.json() == {
        "material_id": str(MATERIAL_ID),
        "freshness": {"is_watched": True, "expected_interval_days": 14},
    }
    assert len(audit.events) == 1
    event = audit.events[0]
    assert event["action"] == "price_alerts.freshness_updated"
    assert event["entity_type"] == "price_freshness_material"
    metadata = event["context"].metadata_json
    assert metadata["material_code"] == "NGO"
    assert [c["field"] for c in metadata["changes"]] == ["is_watched", "expected_interval_days"]
    assert session.commits == 1

    await client.put(f"{BASE}/{MATERIAL_ID}/freshness", json=FRESHNESS_BODY)
    assert len(audit.events) == 1


@pytest.mark.asyncio
async def test_put_freshness_unknown_material_is_404(
    client: AsyncClient,
    deps: tuple[MockThresholdService, MockAuditLogService, MockSession],
) -> None:
    response = await client.put(f"{BASE}/{uuid4()}/freshness", json=FRESHNESS_BODY)

    assert response.status_code == 404
    assert response.json()["detail"] == "Material not found"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        {"is_watched": True, "expected_interval_days": 0},
        {"is_watched": True, "expected_interval_days": 366},
        {"is_watched": True, "expected_interval_days": 7.5},
        {"is_watched": True},
        {"expected_interval_days": 7},
    ],
)
async def test_put_freshness_rejects_bad_bodies(
    client: AsyncClient,
    deps: tuple[MockThresholdService, MockAuditLogService, MockSession],
    body: dict[str, Any],
) -> None:
    assert (await client.put(f"{BASE}/{MATERIAL_ID}/freshness", json=body)).status_code == 422


@pytest.mark.asyncio
async def test_delete_freshness_is_idempotent_204_and_audits_only_once(
    client: AsyncClient,
    deps: tuple[MockThresholdService, MockAuditLogService, MockSession],
) -> None:
    _, audit, _ = deps
    await client.put(f"{BASE}/{MATERIAL_ID}/freshness", json=FRESHNESS_BODY)
    audit.events.clear()

    first = await client.delete(f"{BASE}/{MATERIAL_ID}/freshness")
    second = await client.delete(f"{BASE}/{MATERIAL_ID}/freshness")

    assert first.status_code == second.status_code == 204
    assert first.content == b""
    assert len(audit.events) == 1
    assert audit.events[0]["action"] == "price_alerts.freshness_updated"


# --- /users/me/alert-preferences ---------------------------------------------

PREFS = "/api/v1/users/me/alert-preferences"


@pytest.mark.asyncio
async def test_preferences_route_is_not_swallowed_by_users_id_route(
    app: FastAPI,
    client: AsyncClient,
    deps: tuple[MockThresholdService, MockAuditLogService, MockSession],
) -> None:
    app.dependency_overrides[get_current_user] = lambda: _build_user(["user"])

    response = await client.get(PREFS)

    assert response.status_code == 200
    assert set(response.json()) == {
        "is_enabled",
        "min_level",
        "effective_min_level",
        "admin_receive_all",
    }
    paths = [getattr(route, "path", "") for route in app.routes]
    assert paths.index("/api/v1/users/me/alert-preferences") < paths.index(
        "/api/v1/users/{user_id}",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role_names", "codes", "expected"),
    [
        (["user"], [], "light"),
        (["manager"], [], "medium"),
        (["staff"], ["price_alerts.receive_all"], "medium"),
    ],
)
async def test_default_effective_level_depends_on_role(
    app: FastAPI,
    client: AsyncClient,
    deps: tuple[MockThresholdService, MockAuditLogService, MockSession],
    role_names: list[str],
    codes: list[str],
    expected: str,
) -> None:
    app.dependency_overrides[get_current_user] = lambda: _build_user(role_names, codes)

    body = (await client.get(PREFS)).json()

    assert body == {
        "is_enabled": True,
        "min_level": None,
        "effective_min_level": expected,
        "admin_receive_all": False,
    }


@pytest.mark.asyncio
async def test_put_sets_min_level_and_get_reflects_it(
    app: FastAPI,
    client: AsyncClient,
    deps: tuple[MockThresholdService, MockAuditLogService, MockSession],
) -> None:
    _, _, session = deps
    app.dependency_overrides[get_current_user] = lambda: _build_user(["manager"])

    response = await client.put(PREFS, json={"is_enabled": False, "min_level": "large"})

    assert response.status_code == 200
    assert response.json() == {
        "is_enabled": False,
        "min_level": "large",
        "effective_min_level": "large",
        "admin_receive_all": False,
    }
    assert session.commits == 1
    assert (await client.get(PREFS)).json()["min_level"] == "large"


@pytest.mark.asyncio
@pytest.mark.parametrize("level", ["huge", "", "LIGHT"])
async def test_put_rejects_invalid_level_with_422(
    client: AsyncClient,
    deps: tuple[MockThresholdService, MockAuditLogService, MockSession],
    app: FastAPI,
    level: str,
) -> None:
    app.dependency_overrides[get_current_user] = lambda: _build_user(["user"])
    response = await client.put(PREFS, json={"is_enabled": True, "min_level": level})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_non_admin_cannot_set_admin_receive_all_but_admin_can(
    app: FastAPI,
    client: AsyncClient,
    deps: tuple[MockThresholdService, MockAuditLogService, MockSession],
) -> None:
    _, _, session = deps
    payload = {"is_enabled": True, "min_level": None, "admin_receive_all": True}

    app.dependency_overrides[get_current_user] = lambda: _build_user(["manager"])
    denied = await client.put(PREFS, json=payload)
    assert denied.status_code == 403
    assert session.commits == 0

    app.dependency_overrides[get_current_user] = lambda: _build_user(["admin"])
    allowed = await client.put(PREFS, json=payload)
    assert allowed.status_code == 200
    assert allowed.json()["admin_receive_all"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["get", "put"])
async def test_preferences_need_login(client: AsyncClient, method: str) -> None:
    kwargs: dict[str, Any] = {"json": {"is_enabled": True}} if method == "put" else {}
    assert (await client.request(method, PREFS, **kwargs)).status_code == 401
