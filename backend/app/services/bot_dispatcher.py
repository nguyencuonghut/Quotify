"""Bên đánh chuông: đánh thức worker bot sau khi một dòng hộp thư đã commit (kế hoạch 5.1).

Hàng đợi chỉ là cái chuông; trạng thái nằm ở Postgres. Mất Redis hay quá hạn đều không làm mất tin,
nên mọi lỗi ở đây chỉ được ghi log và không bao giờ làm hỏng webhook.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from app.core.config import Settings
from app.services.bot_policy import ChatbotPolicy

logger = logging.getLogger("app.bot")

# Tên hàm arq của worker bot (`app.bot_worker.drain_chat`).
DRAIN_FUNCTION = "drain_chat"


class BotDispatcher(Protocol):
    async def notify(self, chat_id: int, update_id: int) -> None: ...

    async def aclose(self) -> None: ...


class NullBotDispatcher:
    """Không làm gì: dùng khi chatbot tắt."""

    async def notify(self, chat_id: int, update_id: int) -> None:
        return None

    async def aclose(self) -> None:
        return None


class ArqBotDispatcher:
    """Đánh chuông qua arq. Pool tạo lười, và cả việc tạo pool lẫn việc enqueue nằm trong MỘT
    `wait_for`: `arq.create_pool` treo vô hạn khi Redis nửa chết (đo ở S0(b)).
    """

    def __init__(
        self,
        *,
        host: str,
        port: int,
        queue_name: str,
        timeout_seconds: float = 2.0,
        pool_factory: Callable[[], Awaitable[Any]] | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._queue_name = queue_name
        self._timeout = timeout_seconds
        self._pool_factory = pool_factory or self._create_pool
        self._pool: Any | None = None
        # Nhiều `notify` đồng thời không được tạo mỗi lần một pool (mỗi pool là các kết nối Redis).
        self._lock = asyncio.Lock()

    @classmethod
    def from_settings(cls, settings: Settings) -> ArqBotDispatcher:
        return cls(
            host=settings.redis_host,
            port=settings.redis_port,
            queue_name=settings.bot_queue_name,
        )

    async def _create_pool(self) -> Any:
        from arq import create_pool
        from arq.connections import RedisSettings

        return await create_pool(
            RedisSettings(host=self._host, port=self._port),
            default_queue_name=self._queue_name,
        )

    async def notify(self, chat_id: int, update_id: int) -> None:
        try:
            await asyncio.wait_for(self._enqueue(chat_id, update_id), timeout=self._timeout)
        except Exception as exc:  # gồm TimeoutError; ngoại lệ của redis không phải builtin
            logger.warning(
                "bot.notify_failed update_id=%s error=%s",
                update_id,
                type(exc).__name__,
            )

    async def _enqueue(self, chat_id: int, update_id: int) -> None:
        if self._pool is None:
            async with self._lock:
                if self._pool is None:
                    self._pool = await self._pool_factory()
        # `_job_id` theo update (không theo chat): job mồ côi sau SIGKILL chặn cùng id rất lâu.
        await self._pool.enqueue_job(
            DRAIN_FUNCTION,
            chat_id,
            _job_id=f"bot:{update_id}",
            _queue_name=self._queue_name,
        )

    async def aclose(self) -> None:
        pool, self._pool = self._pool, None
        if pool is not None:
            try:
                await pool.aclose()
            except Exception as exc:
                logger.warning("bot.dispatcher_close_failed error=%s", type(exc).__name__)


def build_chatbot_runtime(settings: Settings) -> tuple[ChatbotPolicy, BotDispatcher]:
    """Chính sách và bên đánh chuông cho runner (webhook và poller), dựng từ cấu hình."""
    policy = ChatbotPolicy.from_settings(settings)
    # Ghi lại chính sách hiệu lực để thấy ngay nếu cấu hình mở hơn ý định (không log email).
    logger.info(
        "bot.policy enabled=%s pilot=%s",
        policy.enabled,
        "all" if policy.pilot_emails is None else len(policy.pilot_emails),
    )
    dispatcher: BotDispatcher = (
        ArqBotDispatcher.from_settings(settings) if policy.enabled else NullBotDispatcher()
    )
    return policy, dispatcher
