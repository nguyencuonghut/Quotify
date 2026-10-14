"""Worker của chatbot (kế hoạch 5.1): chạy bằng `arq app.bot_worker.BotWorkerSettings`.

Tách khỏi `app/worker.py` để cuộc gọi LLM dài không chiếm slot của worker backup và import.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from arq import cron
from arq.connections import RedisSettings

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.session import get_sessionmaker
from app.integrations.telegram import TelegramClient
from app.services.bot_dispatcher import ArqBotDispatcher
from app.services.bot_inbox import BotInbox, ClaimedRow
from app.services.bot_policy import ChatbotPolicy
from app.services.bot_principal import BotPrincipal, load_bot_principal
from app.services.chat_engine import ChatEngineError, ChatTurn, StubChatEngine
from app.services.telegram_bot_messages import EXPIRED_MESSAGE_TEXT, LOST_MESSAGE_TEXT

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
    # Lùi dần khi thử lại: `retry_backoff_seconds × số lần đã thử`.
    retry_backoff_seconds: float = 5.0
    # Tin cũ hơn mức này (sau sự cố dài) bị loại thay vì trả lời câu hỏi đã cũ.
    message_ttl_seconds: float = 1200.0
    # Cron quét chỉ đánh chuông cho dòng đã chờ ít nhất từng này giây.
    sweep_stale_seconds: float = 30.0
    terminal_retention_days: int = 30

    @classmethod
    def from_settings(cls, settings: Settings) -> BotWorkerConfig:
        return cls(
            enabled=ChatbotPolicy.from_settings(settings).enabled,
            lease_seconds=settings.bot_lease_seconds,
            max_attempts=settings.bot_max_attempts,
            row_timeout_seconds=settings.bot_row_timeout_seconds,
            drain_budget_seconds=settings.bot_drain_budget_seconds,
            retry_backoff_seconds=settings.bot_retry_backoff_seconds,
            message_ttl_seconds=settings.bot_message_ttl_seconds,
            sweep_stale_seconds=settings.bot_sweep_stale_seconds,
            terminal_retention_days=settings.bot_terminal_retention_days,
        )


@dataclass(slots=True)
class _Run:
    """Trạng thái trong MỘT lần chạy `drain_chat` (không lưu DB)."""

    expired_notified: bool = False


async def drain_chat(ctx: dict[str, Any], chat_id: int) -> int:
    """Xử lý lần lượt các dòng của một chat cho đến khi hết hàng hoặc hết ngân sách thời gian.

    Trả số dòng đã xử lý. Không giữ kết nối DB trong lúc gọi engine: mỗi bước là một giao dịch ngắn.
    Bị hủy (arq nhận SIGTERM khi deploy) thì nhả lease của dòng đang xử lý để claim lại được ngay.
    """
    config: BotWorkerConfig = ctx["bot_config"]
    if not config.enabled:
        return 0
    session_factory = ctx["session_factory"]
    run = _Run()
    started = time.monotonic()
    handled = 0
    while time.monotonic() - started < config.drain_budget_seconds:
        # Dòng của mình, chỉ gán SAU commit của claim: claim chưa commit thì dòng chưa thuộc về ta
        # (nhả lease theo `attempts` của một claim bị rollback có thể trùng token của worker khác).
        owned: ClaimedRow | None = None
        try:
            async with session_factory() as session:
                claim = await BotInbox(session).claim(
                    chat_id,
                    now=datetime.now(UTC),
                    lease_seconds=config.lease_seconds,
                    max_attempts=config.max_attempts,
                )
                await session.commit()
                owned = claim.row
            if claim.exhausted:
                # Gửi SAU commit: người dùng chỉ được báo khi dòng đã thật sự `failed`.
                await _notify(ctx, chat_id, LOST_MESSAGE_TEXT, "apology")
            if claim.row is None:
                break
            await _process_row(ctx, claim.row, run)
        except BaseException:  # bị hủy (SIGTERM) hay lỗi bất ngờ: nhả lease rồi ném lại nguyên vẹn
            if owned is not None:
                await asyncio.shield(_release_lease(ctx, owned))
            raise
        handled += 1
    return handled


async def _notify(ctx: dict[str, Any], chat_id: int, message: str, kind: str) -> None:
    """Gửi một thông báo cố định (xin lỗi, tin đã quá cũ). Lỗi gửi không làm hỏng vòng xử lý."""
    try:
        await ctx["telegram_client"].send_message(chat_id, message)
    except Exception as exc:
        logger.warning("bot.notice_failed kind=%s error=%s", kind, type(exc).__name__)


async def _release_lease(ctx: dict[str, Any], row: ClaimedRow) -> None:
    """Nhả lease khi bị hủy. Chạy trong `shield` nên không được ném lỗi che mất việc hủy."""
    try:
        async with ctx["session_factory"]() as session:
            await BotInbox(session).release_lease(
                row.update_id,
                row.attempts,
                now=datetime.now(UTC),
            )
            await session.commit()
    except Exception as exc:
        logger.warning(
            "bot.release_failed update_id=%s error=%s", row.update_id, type(exc).__name__
        )


async def _end_row(ctx: dict[str, Any], row: ClaimedRow, status: str, category: str) -> bool:
    async with ctx["session_factory"]() as session:
        ended = await BotInbox(session).end(
            row.update_id,
            row.attempts,
            status=status,
            category=category,
            now=datetime.now(UTC),
        )
        await session.commit()
    return ended


async def _retry_or_fail(
    ctx: dict[str, Any],
    row: ClaimedRow,
    *,
    category: str,
    retry: bool,
    apologise: bool,
) -> None:
    """Đưa dòng về hàng đợi (backoff) nếu còn lần thử, ngược lại `failed` kèm danh mục cố định."""
    config: BotWorkerConfig = ctx["bot_config"]
    now = datetime.now(UTC)
    will_retry = retry and row.attempts < config.max_attempts
    async with ctx["session_factory"]() as session:
        inbox = BotInbox(session)
        if will_retry:
            backoff = timedelta(seconds=config.retry_backoff_seconds * row.attempts)
            changed = await inbox.requeue(
                row.update_id,
                row.attempts,
                retry_at=now + backoff,
                now=now,
            )
        else:
            changed = await inbox.end(
                row.update_id,
                row.attempts,
                status="failed",
                category=category,
                now=now,
            )
        await session.commit()
    logger.info(
        "bot.row_%s update_id=%s category=%s attempts=%d",
        "requeued" if will_retry else "failed",
        row.update_id,
        category,
        row.attempts,
    )
    if changed and not will_retry and apologise:
        await _notify(ctx, row.chat_id, LOST_MESSAGE_TEXT, "apology")


async def _ask_engine(
    ctx: dict[str, Any],
    row: ClaimedRow,
    principal: BotPrincipal,
) -> str | None:
    """Gọi engine. Trả câu trả lời, hoặc `None` nếu dòng đã được đưa về hàng đợi hay đã thất bại."""
    config: BotWorkerConfig = ctx["bot_config"]
    turn = ChatTurn(
        update_id=row.update_id,
        chat_id=row.chat_id,
        telegram_user_id=row.telegram_user_id,
        principal=principal,
        text=row.payload_text or "",
        received_at=row.received_at,
    )
    # Chỉ ghi nhận kết quả trong `except`, xử lý SAU khi đã thoát khối: lỗi DB xảy ra lúc xử lý sẽ
    # không mang `__context__` là lỗi của engine (arq in cả chuỗi này mà thông điệp có thể chứa
    # nội dung tin).
    category = "engine_error"
    retry = True
    try:
        reply = await asyncio.wait_for(
            ctx["chat_engine"].reply(turn),
            timeout=config.row_timeout_seconds,
        )
        return str(reply.text)
    except ChatEngineError as exc:  # lỗi cuối: cấu hình, chính sách; không thử lại
        logger.warning("bot.engine_failed update_id=%s error=%s", row.update_id, type(exc).__name__)
        retry = False
    except TimeoutError:
        logger.warning("bot.engine_timeout update_id=%s", row.update_id)
        category = "engine_timeout"
    except Exception as exc:  # `ChatEngineTemporaryError` và mọi lỗi bất ngờ: coi là thử lại được
        # Chỉ log tên lớp ngoại lệ: thông điệp có thể chứa nội dung tin hay dữ liệu cá nhân.
        logger.warning("bot.engine_failed update_id=%s error=%s", row.update_id, type(exc).__name__)
    await _retry_or_fail(ctx, row, category=category, retry=retry, apologise=True)
    return None


async def _process_row(ctx: dict[str, Any], row: ClaimedRow, run: _Run) -> None:
    config: BotWorkerConfig = ctx["bot_config"]
    session_factory = ctx["session_factory"]
    began = time.monotonic()

    # Tin quá cũ (sau sự cố dài): loại thay vì trả lời một câu hỏi đã cũ; báo một lần mỗi lần chạy.
    if datetime.now(UTC) - row.received_at > timedelta(seconds=config.message_ttl_seconds):
        if await _end_row(ctx, row, "dropped", "expired") and not run.expired_notified:
            run.expired_notified = True
            await _notify(ctx, row.chat_id, EXPIRED_MESSAGE_TEXT, "expired")
        logger.info("bot.row_dropped update_id=%s category=expired", row.update_id)
        return

    async with session_factory() as session:
        principal = await load_bot_principal(session, row.user_id)
    if principal is None:
        # Người dùng không còn hoạt động: S4 chuyển dòng sang `dropped`. Hiện dòng ở `processing`
        # đến hết lease rồi được claim lại, và cuối cùng `failed` (`lease_exhausted`).
        logger.warning("bot.row_skipped update_id=%s reason=no_active_user", row.update_id)
        return

    reply_text = row.reply_text
    if reply_text is None:
        reply_text = await _ask_engine(ctx, row, principal)
        if reply_text is None:
            return
        async with session_factory() as session:
            saved = await BotInbox(session).save_reply(
                row.update_id,
                row.attempts,
                reply_text,
                now=datetime.now(UTC),
            )
            await session.commit()
        if not saved:  # dòng đã bị worker khác tiếp quản hoặc đã bị xóa: không gửi
            logger.info("bot.row_lost update_id=%s", row.update_id)
            return
    # Nếu `reply_text` đã có sẵn (lần claim trước chết sau bước lưu) thì bỏ qua engine: không tốn
    # thêm token và câu trả lời không đổi giữa các lần thử.

    # Kiểm lần cuối ngay trước khi gửi: worker cũ tỉnh dậy sau khi bị tiếp quản không được gửi lại.
    async with session_factory() as session:
        still_mine = await BotInbox(session).owns(row.update_id, row.attempts)
    if not still_mine:
        logger.info("bot.row_lost update_id=%s", row.update_id)
        return

    try:
        # Văn bản thuần: nội dung do engine sinh không được diễn giải như HTML.
        await ctx["telegram_client"].send_message(row.chat_id, reply_text, parse_mode=None)
    except Exception as exc:
        logger.warning("bot.send_failed update_id=%s error=%s", row.update_id, type(exc).__name__)
        sent = False
    else:
        sent = True
    if not sent:
        # Xử lý ngoài khối `except` (cùng lý do với `_ask_engine`). Câu trả lời đã được lưu: thử lại
        # sau backoff chỉ gửi lại câu đó. S4 phân loại 429, 403, 400.
        await _retry_or_fail(ctx, row, category="send_failed", retry=True, apologise=False)
        return

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


async def sweep_bot_updates(ctx: dict[str, Any]) -> int:
    """Cron (mỗi 30 giây): đánh chuông lại cho mọi chat có dòng bị bỏ sót. Trả số chat đã rung.

    Không tự đổi trạng thái dòng nào (việc tiếp quản lease do claim làm), nên chạy ở hai tiến trình
    cùng lúc vẫn an toàn: `_job_id="bot:<update_id>"` gộp các chuông trùng thành một job.
    """
    config: BotWorkerConfig = ctx["bot_config"]
    if not config.enabled:
        return 0
    async with ctx["session_factory"]() as session:
        pending = await BotInbox(session).pending_chats(
            now=datetime.now(UTC),
            stale_seconds=config.sweep_stale_seconds,
        )
    for item in pending:
        await ctx["dispatcher"].notify(item.chat_id, item.update_id)
    if pending:
        logger.info("bot.sweep rang=%d", len(pending))
    return len(pending)


async def cleanup_bot_updates(ctx: dict[str, Any]) -> int:
    """Cron (mỗi ngày): xóa dòng đã kết thúc quá hạn lưu trữ. Dòng còn mở không bao giờ bị xóa."""
    config: BotWorkerConfig = ctx["bot_config"]
    cutoff = datetime.now(UTC) - timedelta(days=config.terminal_retention_days)
    async with ctx["session_factory"]() as session:
        deleted = await BotInbox(session).delete_finished_before(cutoff)
        await session.commit()
    if deleted:
        logger.info("bot.cleanup deleted=%d", deleted)
    return deleted


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
    # Độ trễ giả chỉ để thử trên dev: một giá trị lỡ lọt vào `.env` production bị bỏ qua.
    is_production = settings.app_env.lower() == "production"
    stub_delay = 0.0 if is_production else settings.bot_stub_delay_seconds
    ctx["chat_engine"] = StubChatEngine(delay_seconds=stub_delay)
    ctx["bot_config"] = BotWorkerConfig.from_settings(settings)
    # Bên đánh chuông riêng cho cron quét (pool lười, có giới hạn thời gian như phía webhook).
    ctx["dispatcher"] = ArqBotDispatcher.from_settings(settings)
    logger.info("Bot worker started up successfully.")


async def shutdown(ctx: dict[str, Any]) -> None:
    dispatcher = ctx.get("dispatcher")
    if dispatcher is not None:
        await dispatcher.aclose()
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
    # Quét lại mỗi 30 giây (lệch giây với các cron khác); dọn mỗi ngày lúc 03:40 giờ Việt Nam.
    cron_jobs = [
        cron(sweep_bot_updates, second={10, 40}),
        cron(cleanup_bot_updates, hour=3, minute=40, second=0),
    ]
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
