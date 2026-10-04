from __future__ import annotations

import re

from app.core.observability import exclude_telegram_from_httpx_instrumentation

ENV_NAME = "OTEL_PYTHON_HTTPX_EXCLUDED_URLS"


def test_default_telegram_host_is_excluded() -> None:
    env: dict[str, str] = {}

    value = exclude_telegram_from_httpx_instrumentation("https://api.telegram.org", env)

    assert r"api\.telegram\.org" in value.split(",")
    assert env[ENV_NAME] == value


def test_existing_exclusions_are_kept_not_overwritten() -> None:
    env = {ENV_NAME: "health,metrics"}

    exclude_telegram_from_httpx_instrumentation("https://api.telegram.org", env)

    assert env[ENV_NAME].split(",")[:2] == ["health", "metrics"]
    assert r"api\.telegram\.org" in env[ENV_NAME].split(",")


def test_host_is_derived_from_the_configured_base_url() -> None:
    env: dict[str, str] = {}

    exclude_telegram_from_httpx_instrumentation("http://fake-telegram.internal:8081", env)

    patterns = env[ENV_NAME].split(",")
    assert re.escape("fake-telegram.internal") in patterns
    assert r"api\.telegram\.org" in patterns


def test_calling_twice_does_not_duplicate_patterns() -> None:
    env: dict[str, str] = {}

    exclude_telegram_from_httpx_instrumentation("https://api.telegram.org", env)
    exclude_telegram_from_httpx_instrumentation("https://api.telegram.org", env)

    assert env[ENV_NAME].split(",").count(r"api\.telegram\.org") == 1
