"""Worker của chatbot (kế hoạch 5.1): chạy bằng `arq app.bot_worker.BotWorkerSettings`.

Tách khỏi `app/worker.py` để cuộc gọi LLM dài không chiếm slot của worker backup và import.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from arq.connections import RedisSettings

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.session import get_sessionmaker
from app.integrations.telegram import TelegramClient
from app.services.bot_inbox import BotInbox, ClaimedRow
from app.services.bot_policy import ChatbotPolicy
from app.services.bot_principal import load_bot_principal
from app.services.chat_engine import ChatTurn, StubChatEngine

logger = logging.getLogger("app.bot")


@dataclass(frozen=True, slots=True)
class BotWorkerConfig:
    """Tham số của vòng xử lý; mặc định là giá trị khởi điểm của kế hoạch (mục 4.8)."""

    # Công tắc tắt khẩn cấp: tắt thì worker không nhận dòng mới (dòng đang chờ không mất).
    enabled: bool = True
    lease_seconds: float = 240.0
    max_attempts: int = 3
    row_timeout_seconds: float = 120.0
    drain_budget_seconds: float = 90.0

    @classmethod
    def from_settings(cls, settings: Settings) -> BotWorkerConfig:
        return cls(
            enabled=ChatbotPolicy.from_settings(settings).enabled,
            lease_seconds=settings.bot_lease_seconds,
            max_attempts=settings.bot_max_attempts,
            row_timeout_seconds=settings.bot_row_timeout_seconds,
            drain_budget_seconds=settings.bot_drain_budget_seconds,
        )


async def drain_chat(ctx: dict[str, Any], chat_id: int) -> int:
    """Xử lý lần lượt các dòng của một chat cho đến khi hết hàng hoặc hết ngân sách thời gian.

    Trả số dòng đã xử lý. Không giữ kết nối DB trong lúc gọi engine: mỗi bước là một giao dịch ngắn.
    """
    config: BotWorkerConfig = ctx["bot_config"]
    if not config.enabled:
        return 0
    session_factory = ctx["session_factory"]
    started = time.monotonic()
    handled = 0
    while time.monotonic() - started < config.drain_budget_seconds:
        async with session_factory() as session:
            claim = await BotInbox(session).claim(
                chat_id,
                now=datetime.now(UTC),
                lease_seconds=config.lease_seconds,
                max_attempts=config.max_attempts,
            )
            await session.commit()
        if claim.row is None:
            break
        await _process_row(ctx, claim.row)
        handled += 1
    return handled


async def _process_row(ctx: dict[str, Any], row: ClaimedRow) -> None:
    config: BotWorkerConfig = ctx["bot_config"]
    session_factory = ctx["session_factory"]
    began = time.monotonic()

    async with session_factory() as session:
        principal = await load_bot_principal(session, row.user_id)
    # Mọi lỗi dưới đây (engine, gửi tin, hủy, người dùng không hoạt động) hiện để dòng ở
    # `processing` đến hết lease rồi được claim lại; S3 và S4 thêm thử lại có backoff, `failed`
    # và `dropped`, và giữ nguyên rằng nội dung chỉ bị xóa khi dòng kết thúc.
    if principal is None:
        # Người dùng không còn hoạt động: S4 chuyển dòng sang `dropped`.
        logger.warning("bot.row_skipped update_id=%s reason=no_active_user", row.update_id)
        return

    turn = ChatTurn(
        update_id=row.update_id,
        chat_id=row.chat_id,
        telegram_user_id=row.telegram_user_id,
        principal=principal,
        text=row.payload_text or "",
        received_at=row.received_at,
    )
    reply = await asyncio.wait_for(
        ctx["chat_engine"].reply(turn),
        timeout=config.row_timeout_seconds,
    )

    async with session_factory() as session:
        saved = await BotInbox(session).save_reply(
            row.update_id,
            row.attempts,
            reply.text,
            now=datetime.now(UTC),
        )
        await session.commit()
    if not saved:  # dòng đã bị worker khác tiếp quản: không gửi
        logger.info("bot.row_lost update_id=%s", row.update_id)
        return

    # Văn bản thuần: nội dung do engine sinh không được diễn giải như HTML.
    await ctx["telegram_client"].send_message(row.chat_id, reply.text, parse_mode=None)

    async with session_factory() as session:
        completed = await BotInbox(session).complete(
            row.update_id,
            row.attempts,
            now=datetime.now(UTC),
        )
        await session.commit()
    # Chỉ log định danh và thời gian, không bao giờ log nội dung tin hay câu trả lời.
    logger.info(
        "bot.row_done update_id=%s status=%s duration_ms=%d",
        row.update_id,
        "replied" if completed else "lost",
        int((time.monotonic() - began) * 1000),
    )


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    # Worker không chạy qua `create_app` nên phải tự cấu hình log (INFO và bộ che token Telegram).
    configure_logging(
        settings.log_level,
        log_format=settings.log_format,
        app_env=settings.app_env,
    )
    ctx["session_factory"] = get_sessionmaker()
    ctx["telegram_client"] = TelegramClient.from_settings(settings)
    ctx["chat_engine"] = StubChatEngine()
    ctx["bot_config"] = BotWorkerConfig.from_settings(settings)
    logger.info("Bot worker started up successfully.")


async def shutdown(ctx: dict[str, Any]) -> None:
    client = ctx.get("telegram_client")
    if client is not None:
        await client.aclose()
    logger.info("Bot worker shutting down.")


_settings = get_settings()


class BotWorkerSettings:
    """Lớp độc lập, khai báo đủ mọi thuộc tính trong thân lớp: arq đọc `cls.__dict__` nên một lớp
    con của `WorkerSettings` sẽ không thừa hưởng gì (đo ở S0(b))."""

    redis_settings = RedisSettings(host=_settings.redis_host, port=_settings.redis_port)
    queue_name = _settings.bot_queue_name
    functions = [drain_chat]
    max_jobs = _settings.bot_worker_max_jobs
    job_timeout = _settings.bot_job_timeout_seconds
    # Thử lại do claim và lease quyết định, không để arq tự thử lại chồng lên.
    max_tries = 1
    # Không để lại job mồ côi khi bị hủy lúc SIGTERM.
    retry_jobs = False
    # Bắt buộc 0: mặc định 3600 giây chặn `_job_id` của job lỗi hay mồ côi 1 giờ.
    keep_result = 0
    # Mặc định 3600 giây làm worker chết trông khỏe một giờ.
    health_check_interval = _settings.bot_health_check_interval_seconds
    timezone = ZoneInfo(_settings.app_timezone)
    on_startup = startup
    on_shutdown = shutdown
