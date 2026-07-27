from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.observability import install_observability
from app.core.rate_limit import InMemoryRateLimiter
from app.core.request_id import RequestIDMiddleware
from app.core.security_headers import apply_security_headers


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(
        settings.log_level,
        log_format=settings.log_format,
        app_env=settings.app_env,
    )
    app.state.settings = settings
    app.state.rate_limiter = InMemoryRateLimiter()

    try:
        from app.storage.minio import build_minio_client

        minio_client = build_minio_client(settings)
        bucket = settings.minio_bucket
        if not minio_client.bucket_exists(bucket):
            minio_client.make_bucket(bucket)
    except Exception as e:
        import logging

        logging.getLogger("app").warning(
            f"Could not connect or initialize MinIO bucket '{settings.minio_bucket}': {e}"
        )

    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    app = FastAPI(
        title=app_settings.app_name,
        debug=app_settings.app_debug,
        version=app_settings.app_version,
        lifespan=lifespan,
    )
    app.state.settings = app_settings
    app.state.rate_limiter = InMemoryRateLimiter()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_build_cors_origins(app_settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIDMiddleware)
    install_observability(app, app_settings)

    @app.middleware("http")
    async def security_headers_middleware(request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        apply_security_headers(
            request=request,
            response=response,
            settings=app_settings,
        )
        return response

    app.include_router(api_router, prefix=app_settings.api_v1_prefix)

    @app.get("/health", tags=["health"])
    async def healthcheck() -> dict[str, str]:
        return {
            "status": "ok",
            "service": app_settings.app_name,
            "environment": app_settings.app_env,
        }

    return app


def _build_cors_origins(raw_origins: str) -> list[str]:
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
