from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from httpx import AsyncClient

from app.api.v1.files import limit_files_upload
from app.api.v1.jobs import limit_users_export
from app.core.rate_limit import InMemoryRateLimiter


def get_route_dependency_calls(app: FastAPI, *, path: str, method: str) -> set[object]:
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path == path and method.upper() in route.methods:
            return {dependency.call for dependency in route.dependant.dependencies}
    raise AssertionError(f"Route {method} {path} not found.")


@pytest.mark.asyncio
async def test_health_response_has_security_headers(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["permissions-policy"] == "camera=(), microphone=(), geolocation=()"
    assert response.headers["cross-origin-opener-policy"] == "same-origin"


@pytest.mark.asyncio
async def test_login_is_rate_limited() -> None:
    limiter = InMemoryRateLimiter()

    first = await limiter.hit(key="auth.login:test", limit=2, window_seconds=60)
    second = await limiter.hit(key="auth.login:test", limit=2, window_seconds=60)
    third = await limiter.hit(key="auth.login:test", limit=2, window_seconds=60)

    assert first.allowed is True
    assert second.allowed is True
    assert third.allowed is False
    assert third.retry_after >= 1


def test_file_upload_route_has_rate_limit_dependency(app: FastAPI) -> None:
    dependency_calls = get_route_dependency_calls(
        app,
        path="/api/v1/files/upload",
        method="POST",
    )

    assert limit_files_upload in dependency_calls


def test_file_upload_route_has_permission_dependency(app: FastAPI) -> None:
    dependency_qualnames = {
        getattr(dependency, "__qualname__", "")
        for dependency in get_route_dependency_calls(
            app,
            path="/api/v1/files/upload",
            method="POST",
        )
    }

    assert "require_permission.<locals>.dependency" in dependency_qualnames


def test_user_export_route_has_rate_limit_dependency(app: FastAPI) -> None:
    dependency_calls = get_route_dependency_calls(
        app,
        path="/api/v1/users/export",
        method="POST",
    )

    assert limit_users_export in dependency_calls


def test_user_export_route_has_permission_dependency(app: FastAPI) -> None:
    dependency_qualnames = {
        getattr(dependency, "__qualname__", "")
        for dependency in get_route_dependency_calls(
            app,
            path="/api/v1/users/export",
            method="POST",
        )
    }

    assert "require_permission.<locals>.dependency" in dependency_qualnames


def test_users_list_route_caps_limit_at_100(app: FastAPI) -> None:
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path == "/api/v1/users" and "GET" in route.methods:
            limit_param = next(
                query for query in route.dependant.query_params if query.name == "limit"
            )
            assert any(
                getattr(metadata, "ge", None) == 1 for metadata in limit_param.field_info.metadata
            )
            assert any(
                getattr(metadata, "le", None) == 100 for metadata in limit_param.field_info.metadata
            )
            return

    raise AssertionError("GET /api/v1/users route not found.")
