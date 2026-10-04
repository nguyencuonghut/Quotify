from __future__ import annotations

import logging
import time
from collections import deque
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from sqlalchemy import delete, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.telegram import TelegramClient, TelegramForbiddenError
from app.models.telegram_link_token import TelegramLinkToken
from app.models.telegram_processed_update import TelegramProcessedUpdate
from app.services.telegram_bot_messages import SYSTEM_ERROR_TEXT
from app.services.telegram_link_service import TelegramLinkService
from app.services.telegram_update_service import (
    OutboundMessage,
    TelegramUpdate,
    TelegramUpdateService,
    parse_update,
)

logger = logging.getLogger("app.telegram")

# Lỗi hạ tầng tạm thời: trả 5xx để Telegram thử lại, KHÔNG ghi `update_id` đã xử lý.
_TRANSIENT_ERRORS = (OperationalError, InterfaceError, TimeoutError, ConnectionError)


class TelegramTemporaryError(Exception):
    """Lỗi hạ tầng tạm thời khi xử lý update. Webhook trả 503, poller thử lại với backoff."""


class TelegramUserRateLimiter:
    """Hạn mức theo người dùng Telegram, in-memory, cửa sổ trượt, tự dọn khóa cũ."""

    def __init__(
        self,
        *,
        limit: int = 10,
        window_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._hits: dict[int, deque[float]] = {}
        self._last_purge = clock()

    def allow(self, key: int) -> bool:
        now = self._clock()
        self._purge(now)
        hits = self._hits.setdefault(key, deque())
        while hits and now - hits[0] >= self._window:
            hits.popleft()
        if len(hits) >= self._limit:
            return False
        hits.append(now)
        return True

    def _purge(self, now: float) -> None:
        if now - self._last_purge < self._window:
            return
        self._last_purge = now
        stale = [k for k, hits in self._hits.items() if not hits or now - hits[-1] >= self._window]
        for key in stale:
            del self._hits[key]


class TelegramUpdateRunner:
    """Chạy một update Telegram từ đầu tới cuối. Dùng chung cho webhook và poller.

    Thứ tự: hạn mức → (một giao dịch: chống trùng + xử lý + commit) → gửi tin SAU commit.
    Lỗi gửi tin không đổi kết quả nghiệp vụ. Tuyệt đối không log nội dung update (tin
    `/start <mã>` chứa mã liên kết), chỉ log `update_id` và loại lỗi.
    """

    def __init__(
        self,
        *,
        session_factory: Callable[[], Any],
        client: TelegramClient,
        rate_limiter: TelegramUserRateLimiter | None = None,
        clock: Callable[[], float] = time.monotonic,
        cleanup_interval_seconds: float = 3600.0,
        processed_retention_days: int = 3,
        link_token_retention_days: int = 7,
    ) -> None:
        self._session_factory = session_factory
        self._client = client
        self._rate_limiter = rate_limiter or TelegramUserRateLimiter()
        self._clock = clock
        self._cleanup_interval = cleanup_interval_seconds
        self._retention = timedelta(days=processed_retention_days)
        self._link_token_retention = timedelta(days=link_token_retention_days)
        self._last_cleanup: float | None = None

    async def aclose(self) -> None:
        await self._client.aclose()

    async def process(self, payload: Any) -> None:
        update = parse_update(payload)
        if update is None:
            return

        message = update.message
        if message is not None and message.from_user_id is not None:
            if not self._rate_limiter.allow(message.from_user_id):
                logger.info("telegram.rate_limited update_id=%s", update.update_id)
                return

        try:
            outbound = await self._handle_in_transaction(update)
        except _TRANSIENT_ERRORS as exc:
            logger.warning(
                "telegram.update_transient_failure update_id=%s error=%s",
                update.update_id,
                type(exc).__name__,
            )
            raise TelegramTemporaryError from exc
        except Exception as exc:
            logger.error(
                "telegram.update_failed update_id=%s error=%s",
                update.update_id,
                type(exc).__name__,
                exc_info=True,
            )
            outbound = await self._record_poison_update(update)

        await self._send(update.update_id, outbound)
        await self._maybe_cleanup()

    async def _handle_in_transaction(self, update: TelegramUpdate) -> list[OutboundMessage]:
        async with self._session_factory() as session:
            try:
                outbound = await TelegramUpdateService(session).handle(update)
                await session.commit()
            except Exception:
                await session.rollback()
                raise
        return outbound

    async def _record_poison_update(self, update: TelegramUpdate) -> list[OutboundMessage]:
        """Update "độc": ghi nhận đã xử lý (tránh vòng thử lại vô hạn) và báo lỗi hệ thống."""
        try:
            async with self._session_factory() as session:
                try:
                    await session.execute(
                        pg_insert(TelegramProcessedUpdate)
                        .values(update_id=update.update_id)
                        .on_conflict_do_nothing(index_elements=["update_id"])
                    )
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise
        except Exception as exc:
            # Không ghi được cả dedupe: coi là lỗi hạ tầng tạm thời, để Telegram thử lại.
            raise TelegramTemporaryError from exc

        message = update.message
        if message is None or message.chat_type != "private":
            return []
        return [OutboundMessage(message.chat_id, SYSTEM_ERROR_TEXT)]

    async def _send(self, update_id: int, outbound: list[OutboundMessage]) -> None:
        for item in outbound:
            try:
                await self._client.send_message(
                    item.chat_id,
                    item.text,
                    reply_markup=item.reply_markup,
                )
            except Exception as exc:
                # Tin trả lời là "at-most-once": commit xong rồi mới gửi, lỗi chỉ được ghi nhận.
                logger.warning(
                    "telegram.send_failed update_id=%s error=%s",
                    update_id,
                    type(exc).__name__,
                )
                if isinstance(exc, TelegramForbiddenError):
                    await self._mark_blocked(update_id, item.chat_id)

    async def _mark_blocked(self, update_id: int, chat_id: int) -> None:
        """Telegram trả 403: người dùng đã chặn bot. Chat riêng có `chat_id` = id người dùng."""
        try:
            async with self._session_factory() as session:
                try:
                    await TelegramLinkService(session).mark_blocked(chat_id)
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise
        except Exception as exc:
            logger.warning(
                "telegram.mark_blocked_failed update_id=%s error=%s",
                update_id,
                type(exc).__name__,
            )

    async def _maybe_cleanup(self) -> None:
        now = self._clock()
        if self._last_cleanup is not None and now - self._last_cleanup < self._cleanup_interval:
            return
        self._last_cleanup = now
        try:
            session: AsyncSession
            async with self._session_factory() as session:
                await session.execute(
                    delete(TelegramProcessedUpdate).where(
                        TelegramProcessedUpdate.received_at < func.now() - self._retention
                    )
                )
                # Mã liên kết đã dùng hoặc đã hết hạn quá lâu (mốc là lúc dùng, nếu có).
                await session.execute(
                    delete(TelegramLinkToken).where(
                        func.coalesce(TelegramLinkToken.used_at, TelegramLinkToken.expires_at)
                        < func.now() - self._link_token_retention
                    )
                )
                await session.commit()
        except Exception as exc:
            logger.warning("telegram.cleanup_failed error=%s", type(exc).__name__)
