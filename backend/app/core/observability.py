from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any, cast

from fastapi import FastAPI, Request, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.responses import PlainTextResponse

from app.core.config import Settings

REQUEST_COUNTER = Counter(
    "fastapivue_http_requests_total",
    "Total HTTP requests processed by the FastApiVue backend.",
    ["method", "path", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "fastapivue_http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ["method", "path"],
)
READINESS_GAUGE = Gauge(
    "fastapivue_readiness_dependency_status",
    "Dependency readiness status where 1 means healthy and 0 means unhealthy.",
    ["dependency"],
)

_otel_configured = False


class ReadinessService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def check(self) -> dict[str, Any]:
        checks = await asyncio.gather(
            self._check_database(),
            self._check_redis(),
            self._check_minio(),
        )
        dependencies = {name: payload for name, payload in checks}
        all_dependencies_ok = all(item["status"] == "ok" for item in dependencies.values())
        overall_status = "ok" if all_dependencies_ok else "degraded"
        status_code = (
            status.HTTP_200_OK if overall_status == "ok" else status.HTTP_503_SERVICE_UNAVAILABLE
        )

        return {
            "status": overall_status,
            "status_code": status_code,
            "dependencies": dependencies,
        }

    async def _check_database(self) -> tuple[str, dict[str, str]]:
        from sqlalchemy import text

        from app.db.session import get_engine

        try:
            engine = get_engine()
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            READINESS_GAUGE.labels("database").set(1)
            return "database", {"status": "ok"}
        except Exception as exc:  # pragma: no cover - exercised by runtime env
            READINESS_GAUGE.labels("database").set(0)
            return "database", {"status": "error", "detail": str(exc)}

    async def _check_redis(self) -> tuple[str, dict[str, str]]:
        import redis.asyncio as redis_async

        client = cast(Any, redis_async.from_url(self.settings.redis_url))  # type: ignore[no-untyped-call]
        try:
            await client.ping()
            READINESS_GAUGE.labels("redis").set(1)
            return "redis", {"status": "ok"}
        except Exception as exc:  # pragma: no cover - exercised by runtime env
            READINESS_GAUGE.labels("redis").set(0)
            return "redis", {"status": "error", "detail": str(exc)}
        finally:
            await client.aclose()

    async def _check_minio(self) -> tuple[str, dict[str, str]]:
        from app.storage.minio import build_minio_client

        def ping_minio() -> None:
            client = build_minio_client(self.settings)
            client.bucket_exists(self.settings.minio_bucket)

        try:
            await asyncio.to_thread(ping_minio)
            READINESS_GAUGE.labels("minio").set(1)
            return "minio", {"status": "ok"}
        except Exception as exc:  # pragma: no cover - exercised by runtime env
            READINESS_GAUGE.labels("minio").set(0)
            return "minio", {"status": "error", "detail": str(exc)}


def install_observability(app: FastAPI, settings: Settings) -> None:
    app.state.readiness_service = ReadinessService(settings)

    if settings.metrics_enabled:
        _install_metrics_route(app, settings)
        _install_metrics_middleware(app)

    if settings.otel_enabled:
        configure_open_telemetry(app, settings)


def _install_metrics_route(app: FastAPI, settings: Settings) -> None:
    @app.get(settings.metrics_path, include_in_schema=False)
    async def metrics() -> PlainTextResponse:
        return PlainTextResponse(
            generate_latest().decode("utf-8"),
            media_type=CONTENT_TYPE_LATEST,
        )

    @app.get(settings.readiness_path, include_in_schema=False)
    async def readiness(request: Request) -> Response:
        readiness_service: ReadinessService = request.app.state.readiness_service
        payload = await readiness_service.check()
        return Response(
            content=_to_json_bytes(payload),
            media_type="application/json",
            status_code=int(payload["status_code"]),
        )


def _install_metrics_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def metrics_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        started_at = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - started_at
        route_path = _resolve_route_path(request)
        status_code = str(response.status_code)

        REQUEST_COUNTER.labels(request.method, route_path, status_code).inc()
        REQUEST_LATENCY.labels(request.method, route_path).observe(duration)
        return response


def configure_open_telemetry(app: FastAPI, settings: Settings) -> None:
    global _otel_configured
    if _otel_configured:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        return

    if not settings.otel_exporter_otlp_endpoint:
        return

    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "service.version": settings.app_version,
            "deployment.environment": settings.app_env,
        }
    )
    tracer_provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(
        endpoint=settings.otel_exporter_otlp_endpoint,
        headers=_parse_otel_headers(settings.otel_exporter_otlp_headers),
    )
    tracer_provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(tracer_provider)

    FastAPIInstrumentor.instrument_app(app, excluded_urls="health,metrics,ready")
    HTTPXClientInstrumentor().instrument()
    _otel_configured = True


def instrument_sqlalchemy_engine(engine: Any) -> None:
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    except ImportError:
        return

    try:
        SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
    except Exception:
        return


def _parse_otel_headers(raw_headers: str | None) -> dict[str, str] | None:
    if not raw_headers:
        return None

    headers: dict[str, str] = {}
    for item in raw_headers.split(","):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        headers[key.strip()] = value.strip()
    return headers or None


def _resolve_route_path(request: Request) -> str:
    route = request.scope.get("route")
    if route is not None and hasattr(route, "path"):
        return str(route.path)
    return request.url.path


def _to_json_bytes(payload: dict[str, Any]) -> bytes:
    import json

    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
