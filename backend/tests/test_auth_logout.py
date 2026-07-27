from __future__ import annotations

from starlette.responses import Response

from app.api.v1.auth import _clear_refresh_cookie
from app.core.config import Settings


def test_clear_refresh_cookie_sets_deletion_headers() -> None:
    response = Response()
    settings = Settings.model_validate(
        {
            "auth_refresh_cookie_name": "fastapivue_refresh_token",
            "auth_logged_in_cookie_name": "fastapivue_logged_in",
            "auth_refresh_cookie_path": "/api/v1/auth",
            "auth_refresh_cookie_samesite": "lax",
            "auth_refresh_cookie_secure": False,
            "otel_enabled": False,
            "otel_exporter_otlp_endpoint": None,
        }
    )

    _clear_refresh_cookie(response=response, settings=settings)

    set_cookie_headers = response.headers.getlist("set-cookie")

    assert any("fastapivue_refresh_token=" in header for header in set_cookie_headers)
    assert any("fastapivue_logged_in=" in header for header in set_cookie_headers)
    assert all(
        "Max-Age=0" in header or "expires=" in header.lower() for header in set_cookie_headers
    )
