from __future__ import annotations

import asyncio
import math
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response, status

from app.core.client_ip import resolve_client_ip
from app.core.config import Settings, get_settings


@dataclass(slots=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    reset_at: int
    retry_after: int


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._buckets: dict[str, tuple[int, int]] = {}

    async def hit(
        self,
        *,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimitDecision:
        now = int(time.time())
        window_start = now - (now % window_seconds)
        window_end = window_start + window_seconds

        async with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None or bucket[0] != window_start:
                count = 0
            else:
                count = bucket[1]

            next_count = count + 1
            allowed = next_count <= limit
            stored_count = next_count if allowed else count
            self._buckets[key] = (window_start, stored_count)

        remaining = max(0, limit - stored_count)
        retry_after = max(1, math.ceil(window_end - time.time()))
        return RateLimitDecision(
            allowed=allowed,
            limit=limit,
            remaining=remaining,
            reset_at=window_end,
            retry_after=retry_after,
        )


def build_rate_limit_dependency(
    *,
    scope: str,
    limit_setting: str,
) -> Callable[[Request, Response, Settings], Awaitable[None]]:
    async def dependency(
        request: Request,
        response: Response,
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> None:
        limit = getattr(settings, limit_setting)
        window_seconds = settings.rate_limit_window_seconds
        if limit <= 0 or window_seconds <= 0:
            return

        limiter: InMemoryRateLimiter = request.app.state.rate_limiter
        client_key = _build_client_key(request, settings=settings)
        decision = await limiter.hit(
            key=f"{scope}:{client_key}",
            limit=limit,
            window_seconds=window_seconds,
        )

        response.headers["X-RateLimit-Limit"] = str(decision.limit)
        response.headers["X-RateLimit-Remaining"] = str(decision.remaining)
        response.headers["X-RateLimit-Reset"] = str(decision.reset_at)

        if not decision.allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded.",
                headers={
                    "Retry-After": str(decision.retry_after),
                    "X-RateLimit-Limit": str(decision.limit),
                    "X-RateLimit-Remaining": str(decision.remaining),
                    "X-RateLimit-Reset": str(decision.reset_at),
                },
            )

    return dependency


def _build_client_key(request: Request, *, settings: Settings) -> str:
    return (
        resolve_client_ip(
            request,
            trusted_proxy_cidrs=settings.trusted_proxy_cidrs,
        )
        or "unknown"
    )
