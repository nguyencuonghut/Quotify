"""Worker của chatbot (kế hoạch 5.1): chạy bằng `arq app.bot_worker.BotWorkerSettings`.

Tách khỏi `app/worker.py` để cuộc gọi LLM dài không chiếm slot của worker backup và import.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from arq import cron
from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.readonly import ReadonlySessionFactory
from app.db.session import create_bot_engine
from app.integrations.telegram import (
    TelegramApiError,
    TelegramClient,
    TelegramForbiddenError,
)
from app.services.bot_dispatcher import ArqBotDispatcher
from app.services.bot_inbox import BotInbox, ClaimedRow
from app.services.bot_policy import ChatbotPolicy
from app.services.bot_principal import BotPrincipal, delivery_block_reason, load_bot_principal
from app.services.bot_reply_sender import (
    SendBudgetExceededError,
    append_footer,
    send_parts,
    split_reply,
)
from app.services.chat_engine import ChatEngineError, ChatTurn, StubChatEngine
from app.services.telegram_bot_messages import (
    EXPIRED_MESSAGE_TEXT,
    LOST_MESSAGE_TEXT,
    quota_denied_text,
    quota_reminder_text,
)
from app.services.telegram_link_service import TelegramLinkService
from app.services.usage_gate import QuotaDecision, TurnLimitGate, UsageGate

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
    reply_max_parts: int = 4
    # Trần TỔNG cho nhánh gửi một dòng (kể cả chờ 429 và gửi nhiều phần).
    send_budget_seconds: float = 60.0
    # Chỉ báo "đang gõ" của Telegram kéo dài khoảng 5 giây nên lặp lại trước khi hết.
    typing_interval_seconds: float = 4.0
    # Còn từng này phần trăm hạn mức mỗi ngày thì thêm dòng nhắc cuối câu trả lời (0 là tắt).
    quota_warn_remaining_percent: int = 20

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
            reply_max_parts=settings.bot_reply_max_parts,
            send_budget_seconds=settings.bot_send_budget_seconds,
            typing_interval_seconds=settings.bot_typing_interval_seconds,
            quota_warn_remaining_percent=settings.bot_quota_warn_remaining_percent,
        )


@dataclass(slots=True)
class _Run:
    """Trạng thái trong MỘT lần chạy `drain_chat` (không lưu DB)."""

    expired_notified: bool = False
    # Nhiều tin của cùng một người bị từ chối trong một lần chạy chỉ cần một câu từ chối.
    quota_notified: bool = False


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
    """Gửi một thông báo cố định (xin lỗi, tin đã quá cũ). Lỗi gửi không làm hỏng vòng xử lý.

    Không gửi cho chat đã hủy liên kết hay đã chặn bot (chat riêng nên `telegram_user_id` bằng
    `chat_id`); Telegram trả 403 thì đánh dấu liên kết `blocked`.
    """
    try:
        async with ctx["session_factory"]() as session:
            reason = await delivery_block_reason(session, telegram_user_id=chat_id)
        if reason is not None:
            logger.info("bot.notice_skipped kind=%s reason=%s", kind, reason)
            return
        await ctx["telegram_client"].send_message(chat_id, message)
    except TelegramForbiddenError:
        logger.warning("bot.notice_failed kind=%s error=TelegramForbiddenError", kind)
        await _mark_blocked(ctx, chat_id)
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
    min_delay_seconds: float = 0.0,
) -> None:
    """Đưa dòng về hàng đợi (backoff) nếu còn lần thử, ngược lại `failed` kèm danh mục cố định.

    `min_delay_seconds`: lần thử sau không đến sớm hơn mức này (vd Telegram bảo chờ lâu hơn).
    """
    config: BotWorkerConfig = ctx["bot_config"]
    now = datetime.now(UTC)
    will_retry = retry and row.attempts < config.max_attempts
    async with ctx["session_factory"]() as session:
        inbox = BotInbox(session)
        if will_retry:
            backoff = timedelta(
                seconds=max(config.retry_backoff_seconds * row.attempts, min_delay_seconds)
            )
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


async def _typing_loop(client: Any, chat_id: int, interval_seconds: float) -> None:
    while True:
        try:
            await client.send_chat_action(chat_id, "typing")
        except Exception as exc:
            # Chỉ báo là phần phụ: lỗi của nó không được ảnh hưởng việc trả lời.
            logger.debug("bot.typing_failed error=%s", type(exc).__name__)
        await asyncio.sleep(interval_seconds)


@asynccontextmanager
async def _typing(ctx: dict[str, Any], chat_id: int) -> AsyncIterator[None]:
    """Báo "đang gõ" ngay và lặp lại theo chu kỳ bằng một tác vụ nền trong lúc engine chạy."""
    config: BotWorkerConfig = ctx["bot_config"]
    task = asyncio.create_task(
        _typing_loop(ctx["telegram_client"], chat_id, config.typing_interval_seconds)
    )
    try:
        yield
    finally:
        task.cancel()
        # `wait` thay cho `await task`: không nuốt việc hủy của chính worker nếu đang bị hủy.
        await asyncio.wait({task})


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
        readonly_session_factory=ctx.get("readonly_session_factory"),
    )
    # Chỉ ghi nhận kết quả trong `except`, xử lý SAU khi đã thoát khối: lỗi DB xảy ra lúc xử lý sẽ
    # không mang `__context__` là lỗi của engine (arq in cả chuỗi này mà thông điệp có thể chứa
    # nội dung tin).
    category = "engine_error"
    retry = True
    try:
        async with _typing(ctx, row.chat_id):
            reply = await asyncio.wait_for(
                ctx["chat_engine"].reply(turn),
                timeout=config.row_timeout_seconds,
            )
        text = str(reply.text)
        if text.strip():
            return text
        # Câu trả lời rỗng thì Telegram từ chối gửi (400): coi như lỗi engine thử lại được.
        logger.warning("bot.engine_empty_reply update_id=%s", row.update_id)
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


def _send_failure_kind(exc: Exception) -> str:
    """Phân loại lỗi gửi: `blocked` (403), `rejected` (lỗi cuối 4xx), `timeout`, hay `failed`."""
    if isinstance(exc, TelegramForbiddenError):
        return "blocked"
    if isinstance(exc, TelegramApiError):
        code = exc.error_code
        if code is not None and 400 <= code < 500 and code != 429:
            return "rejected"
    if isinstance(exc, TimeoutError | SendBudgetExceededError):
        return "timeout"
    return "failed"


async def _mark_blocked(ctx: dict[str, Any], telegram_user_id: int) -> None:
    """Người dùng đã chặn bot (Telegram trả 403): liên kết `active` thành `blocked`."""
    try:
        async with ctx["session_factory"]() as session:
            await TelegramLinkService(session).mark_blocked(telegram_user_id)
            await session.commit()
    except Exception as exc:
        logger.warning("bot.mark_blocked_failed error=%s", type(exc).__name__)


async def _send_reply(ctx: dict[str, Any], row: ClaimedRow, reply_text: str) -> bool:
    """Gửi các phần chưa gửi của câu trả lời. `True` nếu đã gửi xong và dòng cần được hoàn tất.

    `False` nghĩa là dòng đã được xử lý ở đây (thử lại, thất bại hay loại bỏ).
    """
    config: BotWorkerConfig = ctx["bot_config"]
    parts = split_reply(reply_text, max_parts=config.reply_max_parts)
    failure: str | None = None
    lost = False
    retry_after = 0.0

    async def part_sent(count: int) -> bool:
        async with ctx["session_factory"]() as session:
            owned = await BotInbox(session).save_sent_parts(row.update_id, row.attempts, count)
            await session.commit()
        return owned

    try:
        delivered = await asyncio.wait_for(
            send_parts(
                ctx["telegram_client"],
                row.chat_id,
                parts,
                start=row.sent_parts,
                budget_seconds=config.send_budget_seconds,
                on_part_sent=part_sent,
            ),
            timeout=config.send_budget_seconds,
        )
        lost = not delivered
    except Exception as exc:
        logger.warning("bot.send_failed update_id=%s error=%s", row.update_id, type(exc).__name__)
        failure = _send_failure_kind(exc)
        if isinstance(exc, SendBudgetExceededError):
            retry_after = exc.retry_after
    if lost:  # dòng đã bị worker khác tiếp quản giữa các phần: không làm gì thêm
        logger.info("bot.row_lost update_id=%s", row.update_id)
        return False
    if failure is None:
        return True
    # Xử lý ngoài khối `except` (cùng lý do với `_ask_engine`): lỗi DB lúc xử lý không được mang
    # `__context__` là lỗi gửi.
    if failure == "blocked":
        await _mark_blocked(ctx, row.telegram_user_id)
        await _drop(ctx, row, "forbidden")
    elif failure == "rejected":  # Telegram từ chối nội dung: thử lại cũng vẫn thế
        await _retry_or_fail(ctx, row, category="send_rejected", retry=False, apologise=True)
    else:
        category = "send_timeout" if failure == "timeout" else "send_failed"
        await _retry_or_fail(
            ctx,
            row,
            category=category,
            retry=True,
            apologise=True,
            min_delay_seconds=retry_after,
        )
    return False


async def _drop(ctx: dict[str, Any], row: ClaimedRow, reason: str) -> None:
    """Loại dòng (`dropped`) với danh mục cố định; nội dung bị xóa, người dùng không nhận gì."""
    await _end_row(ctx, row, "dropped", reason)
    logger.info("bot.row_dropped update_id=%s category=%s", row.update_id, reason)


async def _refuse_over_quota(
    ctx: dict[str, Any], row: ClaimedRow, decision: QuotaDecision, run: _Run
) -> None:
    """Hết hạn mức: loại dòng (không gọi engine, không tính lượt) rồi báo người dùng một lần."""
    ended = await _end_row(ctx, row, "dropped", "quota_exceeded")
    logger.info("bot.row_dropped update_id=%s category=quota_exceeded", row.update_id)
    if ended and not run.quota_notified:
        run.quota_notified = True
        await _notify(ctx, row.chat_id, quota_denied_text(decision), "quota")


async def _process_row(ctx: dict[str, Any], row: ClaimedRow, run: _Run) -> None:
    config: BotWorkerConfig = ctx["bot_config"]
    session_factory = ctx["session_factory"]
    began = time.monotonic()

    # Tin quá cũ (sau sự cố dài): loại thay vì trả lời một câu hỏi đã cũ; báo một lần mỗi lần chạy.
    # Câu trả lời đã gửi dở thì gửi nốt, không bắt người dùng hỏi lại.
    expired = datetime.now(UTC) - row.received_at > timedelta(seconds=config.message_ttl_seconds)
    if expired and row.sent_parts == 0:
        if await _end_row(ctx, row, "dropped", "expired") and not run.expired_notified:
            run.expired_notified = True
            await _notify(ctx, row.chat_id, EXPIRED_MESSAGE_TEXT, "expired")
        logger.info("bot.row_dropped update_id=%s category=expired", row.update_id)
        return

    async with session_factory() as session:
        reason = await delivery_block_reason(
            session, telegram_user_id=row.telegram_user_id, user_id=row.user_id
        )
        principal = None if reason else await load_bot_principal(session, row.user_id)
    if (
        principal is None
    ):  # liên kết bị hủy hay bị chặn, hoặc người dùng bị khóa: bỏ, không tốn engine
        await _drop(ctx, row, reason or "user_inactive")
        return

    reply_text = row.reply_text
    decision: QuotaDecision | None = None  # chỉ có khi dòng đi qua cổng (chưa có câu trả lời lưu)
    if reply_text is None:
        # Cổng hạn mức đứng trước engine; dòng đã có câu trả lời (gửi lại sau sự cố) bỏ qua cổng và
        # không bị tính thêm lượt. Cổng chỉ nhìn `row.user_id`, không nhìn vai trò (không miễn ai).
        # Bắt buộc có cổng (KeyError nếu thiếu): thiếu mà bỏ qua thì giới hạn chi phí âm thầm tắt.
        gate: UsageGate = ctx["usage_gate"]
        async with session_factory() as session:
            decision = await gate.check(session, row.user_id, row.kind, now=datetime.now(UTC))
        if not decision.allowed:
            await _refuse_over_quota(ctx, row, decision, run)
            return
        reply_text = await _ask_engine(ctx, row, principal)
        if reply_text is None:
            return
        if decision is not None:
            # Dòng nhắc do cổng thêm (không phải engine sinh) và nằm trong câu được lưu: lần gửi lại
            # sau sự cố chia tin giống hệt và không nhắc thêm lần nữa.
            reminder = quota_reminder_text(
                decision, row.kind, warn_percent=config.quota_warn_remaining_percent
            )
            if reminder:
                reply_text = append_footer(reply_text, reminder, max_parts=config.reply_max_parts)
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
        reason = None
        if still_mine:
            reason = await delivery_block_reason(
                session, telegram_user_id=row.telegram_user_id, user_id=row.user_id
            )
            if reason is None and await load_bot_principal(session, row.user_id) is None:
                reason = "user_inactive"
    if not still_mine:
        logger.info("bot.row_lost update_id=%s", row.update_id)
        return
    if reason is not None:  # đổi ý giữa lúc engine chạy: không gửi
        await _drop(ctx, row, reason)
        return

    if not await _send_reply(ctx, row, reply_text):
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
    # Engine riêng với pool nhỏ tường minh; engine chỉ đọc cho công cụ tạo lười (chưa gọi thì chưa
    # có kết nối nào, và chatbot tắt thì không bao giờ có).
    engine = create_bot_engine(settings)
    ctx["db_engine"] = engine
    ctx["session_factory"] = async_sessionmaker(bind=engine, expire_on_commit=False)
    ctx["readonly_session_factory"] = ReadonlySessionFactory.from_settings(settings)
    ctx["telegram_client"] = TelegramClient.from_settings(settings)
    # Độ trễ giả chỉ để thử trên dev: một giá trị lỡ lọt vào `.env` production bị bỏ qua.
    is_production = settings.app_env.lower() == "production"
    stub_delay = 0.0 if is_production else settings.bot_stub_delay_seconds
    ctx["chat_engine"] = StubChatEngine(delay_seconds=stub_delay)
    ctx["bot_config"] = BotWorkerConfig.from_settings(settings)
    ctx["usage_gate"] = TurnLimitGate.from_settings(settings)
    # Bên đánh chuông riêng cho cron quét (pool lười, có giới hạn thời gian như phía webhook).
    ctx["dispatcher"] = ArqBotDispatcher.from_settings(settings)
    logger.info("Bot worker started up successfully.")


async def _close_quietly(ctx: dict[str, Any], key: str, method: str) -> None:
    """Đóng một thành phần của ngữ cảnh worker; lỗi chỉ được ghi lại để bước sau vẫn chạy."""
    target = ctx.get(key)
    if target is None:
        return
    try:
        await getattr(target, method)()
    except Exception as exc:
        logger.warning("bot.shutdown_failed target=%s error=%s", key, type(exc).__name__)


async def shutdown(ctx: dict[str, Any]) -> None:
    # Mỗi bước độc lập: một bước lỗi không được làm các bước sau (và tiến trình) kẹt lại.
    await _close_quietly(ctx, "readonly_session_factory", "aclose")
    await _close_quietly(ctx, "db_engine", "dispose")
    await _close_quietly(ctx, "dispatcher", "aclose")
    await _close_quietly(ctx, "telegram_client", "aclose")
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
