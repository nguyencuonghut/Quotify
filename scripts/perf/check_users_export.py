#!/usr/bin/env python3
from __future__ import annotations

import os
import statistics
import sys
import time
from typing import Any

import httpx


API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api/v1")
ADMIN_EMAIL = os.getenv("AUTH_SEED_ADMIN_EMAIL", "admin@fastapivue.local")
ADMIN_PASSWORD = os.getenv("AUTH_SEED_ADMIN_PASSWORD", "FastApiVue@2026")
REQUESTS = int(os.getenv("PERF_REQUESTS", "10"))
P95_THRESHOLD_MS = float(os.getenv("PERF_USERS_EXPORT_P95_MS", "500"))


def main() -> int:
    with httpx.Client(timeout=30.0) as client:
        token = login(client)
        durations_ms: list[float] = []

        for index in range(REQUESTS):
            started = time.perf_counter()
            response = client.post(
                f"{API_BASE_URL}/users/export",
                json={
                    "search": f"perf-{index}",
                    "status": "active",
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            elapsed_ms = (time.perf_counter() - started) * 1000
            response.raise_for_status()
            durations_ms.append(elapsed_ms)

        p95_ms = percentile_95(durations_ms)
        average_ms = statistics.fmean(durations_ms)

    print(
        f"users.export: requests={REQUESTS} avg_ms={average_ms:.2f} p95_ms={p95_ms:.2f} "
        f"threshold_ms={P95_THRESHOLD_MS:.2f}"
    )

    if p95_ms > P95_THRESHOLD_MS:
        print("Users export job creation latency exceeded threshold.", file=sys.stderr)
        return 1

    return 0


def login(client: httpx.Client) -> str:
    response = client.post(
        f"{API_BASE_URL}/auth/login",
        json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
        },
    )
    response.raise_for_status()
    payload: dict[str, Any] = response.json()
    return str(payload["access_token"])


def percentile_95(samples_ms: list[float]) -> float:
    if len(samples_ms) == 1:
        return samples_ms[0]

    ordered = sorted(samples_ms)
    index = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * 0.95)))
    return ordered[index]


if __name__ == "__main__":
    raise SystemExit(main())
