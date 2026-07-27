from __future__ import annotations

from fastapi import Request, Response

from app.core.config import Settings


def apply_security_headers(
    *,
    request: Request,
    response: Response,
    settings: Settings,
) -> None:
    if not settings.security_headers_enabled:
        return

    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")

    if settings.security_hsts_enabled and _is_https_request(request):
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=63072000; includeSubDomains; preload",
        )


def _is_https_request(request: Request) -> bool:
    proto = request.headers.get("X-Forwarded-Proto")
    if proto:
        return proto.lower() == "https"

    return request.url.scheme == "https"
