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
    assert "quotify_http_requests_total" in response.text


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


def test_telegram_settings_are_disabled_and_need_no_secrets_by_default() -> None:
    settings = Settings.model_validate({})

    assert settings.telegram_enabled is False
    assert settings.telegram_bot_token == ""
    assert settings.telegram_webhook_secret == ""
    assert settings.telegram_mode == "webhook"
    assert settings.telegram_api_base_url == "https://api.telegram.org"
    assert settings.telegram_http_timeout_seconds == 10.0
    assert settings.rate_limit_telegram_link_token == 5


def test_telegram_secrets_can_be_read_from_files(tmp_path: Path) -> None:
    token_file = tmp_path / "telegram_token.txt"
    secret_file = tmp_path / "telegram_secret.txt"
    token_file.write_text("123456789:AAFileTokenFileTokenFileTokenFile1\n", encoding="utf-8")
    secret_file.write_text("webhook_secret-from_file\n", encoding="utf-8")

    settings = Settings.model_validate(
        {
            "telegram_bot_token": "ignored",
            "telegram_bot_token_file": str(token_file),
            "telegram_webhook_secret": "ignored",
            "telegram_webhook_secret_file": str(secret_file),
        }
    )

    assert settings.telegram_bot_token == "123456789:AAFileTokenFileTokenFileTokenFile1"
    assert settings.telegram_webhook_secret == "webhook_secret-from_file"


def test_telegram_empty_secret_file_is_rejected(tmp_path: Path) -> None:
    empty_file = tmp_path / "empty.txt"
    empty_file.write_text("\n", encoding="utf-8")

    with pytest.raises(ValueError, match="telegram_bot_token"):
        Settings.model_validate({"telegram_bot_token_file": str(empty_file)})


def test_telegram_bot_username_is_normalized_without_at_sign() -> None:
    settings = Settings.model_validate({"telegram_bot_username": "@quotify_dev_bot"})

    assert settings.telegram_bot_username == "quotify_dev_bot"


def test_telegram_client_requires_a_configured_token() -> None:
    from app.integrations.telegram import TelegramClient, TelegramConfigurationError

    with pytest.raises(TelegramConfigurationError):
        TelegramClient.from_settings(Settings.model_validate({}))

    client = TelegramClient.from_settings(
        Settings.model_validate(
            {
                "telegram_bot_token": "123456789:AAFakeTokenFakeTokenFakeTokenFake12",
                "telegram_api_base_url": "http://fake-telegram.test",
                "telegram_http_timeout_seconds": 3,
            }
        )
    )

    assert "AAFakeToken" not in repr(client)
