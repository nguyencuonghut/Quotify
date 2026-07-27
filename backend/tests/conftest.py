from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.application import create_app
from app.core.config import Settings


@pytest.fixture
def app() -> FastAPI:
    settings = Settings.model_validate(
        {
            "app_env": "test",
            "otel_enabled": False,
            "otel_exporter_otlp_endpoint": None,
        }
    )
    return create_app(settings=settings)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client
