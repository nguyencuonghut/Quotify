from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.core.config import Settings


class HealthyReadinessService:
    async def check(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "status_code": 200,
            "dependencies": {
                "database": {"status": "ok"},
                "redis": {"status": "ok"},
                "minio": {"status": "ok"},
            },
        }


@pytest.mark.asyncio
async def test_metrics_endpoint_exposes_prometheus_payload(client: AsyncClient) -> None:
    response = await client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "fastapivue_http_requests_total" in response.text


@pytest.mark.asyncio
async def test_ready_endpoint_uses_readiness_service(app: FastAPI, client: AsyncClient) -> None:
    app.state.readiness_service = HealthyReadinessService()

    response = await client.get("/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["dependencies"]["database"]["status"] == "ok"


def test_settings_can_read_secret_values_from_files(tmp_path: Path) -> None:
    jwt_file = tmp_path / "jwt_secret.txt"
    db_file = tmp_path / "database_url.txt"
    jwt_file.write_text("super-secret-value\n", encoding="utf-8")
    db_file.write_text(
        "postgresql+asyncpg://readonly:secret@db.internal:5432/app\n",
        encoding="utf-8",
    )

    settings = Settings.model_validate(
        {
            "jwt_secret_key": "ignored",
            "jwt_secret_key_file": str(jwt_file),
            "database_url": "ignored",
            "database_url_file": str(db_file),
        }
    )

    assert settings.jwt_secret_key == "super-secret-value"
    assert settings.database_url == "postgresql+asyncpg://readonly:secret@db.internal:5432/app"
