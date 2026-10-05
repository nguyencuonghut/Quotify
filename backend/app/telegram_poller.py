"""Tiến trình polling Telegram DÙNG CHO DEV (production dùng webhook).

Chạy bằng `python -m app.telegram_poller`. Từ chối chạy khi `APP_ENV=production`, khi tính
năng tắt, hoặc khi `TELEGRAM_MODE != polling`, để không vô tình xóa webhook của bot thật.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
import sys
from collections.abc import Awaitable, Callable
from typing import Any

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.session import get_sessionmaker
from app.integrations.telegram import (
    ALLOWED_UPDATES,
    TelegramApiError,
    TelegramClient,
    TelegramConfigurationError,
    TelegramError,
    TelegramNetworkError,
    TelegramRateLimitError,
)
from app.services.telegram_update_runner import TelegramTemporaryError, TelegramUpdateRunner

logger = logging.getLogger("app.telegram")

POLL_TIMEOUT_SECONDS = 25
INITIAL_BACKOFF_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 30.0


def check_poller_preconditions(settings: Settings) -> str | None:
    """Trả thông báo lỗi nếu không được phép chạy poller, ngược lại trả None."""
    if settings.app_env.lower() == "production":
        return "Từ chối chạy poller khi APP_ENV=production (production dùng webhook)."
    if not settings.telegram_enabled:
        return "TELEGRAM_ENABLED=false, poller không chạy."
    if settings.telegram_mode != "polling":
        return "TELEGRAM_MODE phải là 'polling' để chạy poller."
    if not settings.telegram_bot_token:
        return "Chưa cấu hình TELEGRAM_BOT_TOKEN."
    return None


async def _fetch_updates(
    client: TelegramClient,
    offset: int | None,
    stop: asyncio.Event,
) -> list[dict[str, Any]] | None:
    """Long-poll `getUpdates` nhưng hủy ngay khi có yêu cầu dừng (trả None)."""
    poll = asyncio.ensure_future(
        client.get_updates(
            offset=offset,
            timeout_seconds=POLL_TIMEOUT_SECONDS,
            allowed_updates=ALLOWED_UPDATES,
        )
    )
    stopper = asyncio.ensure_future(stop.wait())
    try:
        await asyncio.wait({poll, stopper}, return_when=asyncio.FIRST_COMPLETED)
        if not poll.done():
            poll.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await poll
            return None
        return poll.result()
    finally:
        stopper.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await stopper


async def _wait(
    seconds: float,
    stop: asyncio.Event,
    sleep: Callable[[float], Awaitable[None]] | None,
) -> None:
    if sleep is not None:
        await sleep(seconds)
        return
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(stop.wait(), timeout=seconds)


async def run_poller(
    client: TelegramClient,
    runner: Any,
    stop: asyncio.Event,
    *,
    sleep: Callable[[float], Awaitable[None]] | None = None,
) -> None:
    # getUpdates và webhook loại trừ nhau: xóa webhook trước khi polling.
    await client.delete_webhook()

    offset: int | None = None
    backoff = INITIAL_BACKOFF_SECONDS
    while not stop.is_set():
        try:
            updates = await _fetch_updates(client, offset, stop)
        except TelegramRateLimitError as exc:
            await _wait(max(backoff, float(exc.retry_after or 0)), stop, sleep)
            backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)
            continue
        except (TelegramNetworkError, TelegramApiError) as exc:
            logger.warning("telegram.poll_failed error=%s", type(exc).__name__)
            await _wait(backoff, stop, sleep)
            backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)
            continue

        if updates is None:
            break

        backoff = INITIAL_BACKOFF_SECONDS
        for update in updates:
            try:
                await runner.process(update)
            except TelegramTemporaryError:
                # Chưa xác nhận update này: không tăng offset, thử lại lần sau.
                await _wait(backoff, stop, sleep)
                backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)
                break
            update_id = update.get("update_id")
            if isinstance(update_id, int):
                offset = update_id + 1


async def amain() -> int:
    settings = get_settings()
    configure_logging(
        settings.log_level,
        log_format=settings.log_format,
        app_env=settings.app_env,
    )
    problem = check_poller_preconditions(settings)
    if problem:
        print(problem, file=sys.stderr)
        return 1

    try:
        client = TelegramClient.from_settings(settings)
    except TelegramConfigurationError as exc:
        print(f"Lỗi cấu hình: {exc}", file=sys.stderr)
        return 1

    runner = TelegramUpdateRunner(session_factory=get_sessionmaker(), client=client)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    try:
        bot = await client.get_me()
        logger.info("telegram.poller_started username=%s", bot.username)
        await run_poller(client, runner, stop)
    except TelegramError as exc:
        print(f"Lỗi Telegram: {exc}", file=sys.stderr)
        return 1
    finally:
        await runner.aclose()
    logger.info("telegram.poller_stopped")
    return 0


def main() -> int:
    return asyncio.run(amain())


if __name__ == "__main__":
    raise SystemExit(main())
