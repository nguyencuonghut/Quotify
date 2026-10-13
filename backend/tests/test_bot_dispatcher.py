"""Bên đánh chuông của chatbot (kế hoạch 5.1): không bao giờ làm hỏng hay treo webhook.

Redis/arq là ranh giới hệ thống nên được giả; hành vi cần giữ: job theo update, pool dùng lại,
và mọi lỗi hay treo đều bị cắt (S0(b): `create_pool` treo vô hạn khi Redis nửa chết).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from app.services.bot_dispatcher import ArqBotDispatcher


class _Pool:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self.closed = False

    async def enqueue_job(self, function: str, *args: Any, **kwargs: Any) -> None:
        self.calls.append((function, args, kwargs))

    async def aclose(self) -> None:
        self.closed = True


def _dispatcher(factory: Any, *, timeout: float = 2.0) -> ArqBotDispatcher:
    return ArqBotDispatcher(
        host="redis",
        port=6379,
        queue_name="quotify:bot",
        timeout_seconds=timeout,
        pool_factory=factory,
    )


async def test_notify_enqueues_one_job_per_update_on_the_bot_queue_and_reuses_the_pool() -> None:
    pool = _Pool()
    created: list[int] = []

    async def factory() -> _Pool:
        created.append(1)
        return pool

    dispatcher = _dispatcher(factory)

    await dispatcher.notify(77, 1001)
    await dispatcher.notify(77, 1002)

    assert pool.calls == [
        ("drain_chat", (77,), {"_job_id": "bot:1001", "_queue_name": "quotify:bot"}),
        ("drain_chat", (77,), {"_job_id": "bot:1002", "_queue_name": "quotify:bot"}),
    ]
    assert created == [1]


async def test_notify_gives_up_quickly_when_creating_the_pool_hangs() -> None:
    async def factory() -> Any:
        await asyncio.sleep(3600)

    dispatcher = _dispatcher(factory, timeout=0.05)

    started = time.monotonic()
    await dispatcher.notify(1, 2)  # không ném, không treo

    assert time.monotonic() - started < 1.0


async def test_notify_swallows_an_error_and_tries_to_create_the_pool_again_next_time() -> None:
    pool = _Pool()
    attempts: list[int] = []

    async def factory() -> _Pool:
        attempts.append(1)
        if len(attempts) == 1:
            raise ConnectionError("redis down")
        return pool

    dispatcher = _dispatcher(factory)

    await dispatcher.notify(1, 2)  # lỗi bị nuốt
    await dispatcher.notify(1, 3)

    assert [call[2]["_job_id"] for call in pool.calls] == ["bot:3"]


async def test_notify_gives_up_when_enqueue_hangs_but_keeps_the_pool_for_later() -> None:
    class _HangingOnceEnqueue(_Pool):
        async def enqueue_job(self, function: str, *args: Any, **kwargs: Any) -> None:
            if not self.calls and not hasattr(self, "hung"):
                self.hung = True
                await asyncio.sleep(3600)
            await super().enqueue_job(function, *args, **kwargs)

    pool = _HangingOnceEnqueue()
    created: list[int] = []

    async def factory() -> _Pool:
        created.append(1)
        return pool

    dispatcher = _dispatcher(factory, timeout=0.05)

    await dispatcher.notify(1, 2)  # enqueue treo: bị cắt
    await dispatcher.notify(1, 3)  # lần sau vẫn dùng pool cũ

    assert created == [1]
    assert [call[2]["_job_id"] for call in pool.calls] == ["bot:3"]


async def test_aclose_closes_the_pool_and_is_safe_without_one() -> None:
    pool = _Pool()

    async def factory() -> _Pool:
        return pool

    dispatcher = _dispatcher(factory)
    await dispatcher.aclose()  # chưa có pool
    await dispatcher.notify(1, 2)
    await dispatcher.aclose()

    assert pool.closed


async def test_many_concurrent_notifies_create_a_single_pool() -> None:
    pool = _Pool()
    created: list[int] = []

    async def factory() -> _Pool:
        created.append(1)
        await asyncio.sleep(0.05)  # đủ lâu để các lời gọi khác chen vào
        return pool

    dispatcher = _dispatcher(factory)

    await asyncio.gather(*(dispatcher.notify(1, 1000 + i) for i in range(10)))

    assert created == [1]
    assert len(pool.calls) == 10
