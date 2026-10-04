from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.integrations.telegram import (
    TelegramApiError,
    TelegramClient,
    TelegramForbiddenError,
    TelegramMessageTooLongError,
    TelegramNetworkError,
    TelegramRateLimitError,
)
from app.models import (
    PriceAlertMessage,
    PriceAlertMessageEvent,
    PriceAlertSetting,
    TelegramAccount,
    User,
    UserStatus,
)
from app.services.price_alert_chart import render_price_chart
from app.services.price_alert_formatter import format_caption, format_details
from app.services.price_alert_message_view import load_chart_spec, load_message_view
from app.services.telegram_link_service import TelegramLinkService

logger = logging.getLogger(__name__)

LEASE_DURATION = timedelta(minutes=2)
BACKOFF_BASE = timedelta(seconds=30)
MAX_ATTEMPTS = 5
MAX_AGE = timedelta(hours=24)
MAX_RETRY_AFTER = timedelta(minutes=5)
CONFIG_ERROR_DELAY = timedelta(minutes=5)
DEFAULT_BATCH_LIMIT = 20
_PHOTO_SENT = "photo_sent"
_MAX_ERROR_LENGTH = 255


@dataclass(slots=True)
class SendOutcome:
    claimed: int = 0
    sent: int = 0
    retried: int = 0
    failed: int = 0
    skipped: int = 0


@dataclass(frozen=True, slots=True)
class _Claim:
    message_id: UUID
    attempts: int


@dataclass(frozen=True, slots=True)
class _Content:
    chat_id: int
    telegram_user_id: int
    png: bytes | None
    caption: str
    text: str
    photo_already_sent: bool


class PriceAlertSender:
    """Gửi tin `pending` tới Telegram (L25): at-least-once, `lease_until` chống gửi trùng.

    Không giữ giao dịch DB trong lúc gọi mạng: nhận tin (commit), dựng nội dung (đọc), gửi,
    rồi ghi kết quả (commit). Lỗi gửi không bao giờ đổi sự kiện hay tin nghiệp vụ đã commit.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        client: TelegramClient,
        *,
        base_url: str,
        batch_limit: int = DEFAULT_BATCH_LIMIT,
        pilot_emails: frozenset[str] = frozenset(),
    ) -> None:
        self.session_factory = session_factory
        self.client = client
        self.base_url = base_url
        self.batch_limit = batch_limit
        self.pilot_emails = pilot_emails

    async def run_once(self, now: datetime) -> SendOutcome:
        outcome = SendOutcome()
        async with self.session_factory() as session:
            settings = (await session.execute(select(PriceAlertSetting))).scalar_one_or_none()
        if settings is None or not settings.is_enabled:
            return outcome

        started = time.monotonic()
        for _ in range(self.batch_limit):
            # Nhận từng tin ngay trước khi gửi: lease chỉ bắt đầu chạy khi tới lượt tin đó, nên
            # một lô chậm không làm các tin phía sau hết lease giữa chừng.
            moment = now + timedelta(seconds=time.monotonic() - started)
            claim = await self._claim_one(moment, outcome)
            if claim is None:
                break
            outcome.claimed += 1
            try:
                result = await self._deliver(claim, settings, moment)
            except Exception as exc:
                # Một tin "độc" (lỗi dựng nội dung, lỗi DB...) không được làm sập cả lô.
                logger.exception("price_alert.deliver_failed message_id=%s", claim.message_id)
                result = await self._retry(
                    claim, moment, f"internal:{type(exc).__name__}", self._backoff(claim)
                )
            setattr(outcome, result, getattr(outcome, result) + 1)
        return outcome

    async def _claim_one(self, now: datetime, outcome: SendOutcome) -> _Claim | None:
        """Nhận một tin đến hạn: `pending` hết backoff, hoặc `sending` đã hết `lease_until`.

        Tin quá tuổi hoặc đã dùng hết số lần thử thì chuyển `failed` thay vì gửi.
        """
        while True:
            async with self.session_factory() as session:
                row = (
                    await session.execute(
                        select(
                            PriceAlertMessage.id,
                            PriceAlertMessage.attempts,
                            PriceAlertMessage.created_at,
                        )
                        .where(
                            PriceAlertMessage.kind.in_(("change", "digest")),
                            or_(
                                (PriceAlertMessage.status == "pending")
                                & (
                                    PriceAlertMessage.lease_until.is_(None)
                                    | (PriceAlertMessage.lease_until <= now)
                                ),
                                (PriceAlertMessage.status == "sending")
                                & (PriceAlertMessage.lease_until <= now),
                            ),
                        )
                        .order_by(PriceAlertMessage.sequence_number)
                        .limit(1)
                        .with_for_update(skip_locked=True),
                    )
                ).first()
                if row is None:
                    return None
                message_id, attempts, created_at = row
                if created_at < now - MAX_AGE or attempts >= MAX_ATTEMPTS:
                    reason = "expired" if created_at < now - MAX_AGE else "max_attempts"
                    await session.execute(
                        update(PriceAlertMessage)
                        .where(PriceAlertMessage.id == message_id)
                        .values(
                            status="failed",
                            status_reason=reason,
                            lease_until=None,
                            last_error=reason,
                        ),
                    )
                    await session.commit()
                    outcome.failed += 1
                    continue
                await session.execute(
                    update(PriceAlertMessage)
                    .where(PriceAlertMessage.id == message_id)
                    .values(
                        status="sending", lease_until=now + LEASE_DURATION, attempts=attempts + 1
                    ),
                )
                await session.commit()
                return _Claim(message_id, attempts + 1)

    async def _deliver(self, claim: _Claim, settings: PriceAlertSetting, now: datetime) -> str:
        try:
            content = await self._build(claim.message_id, settings)
        except _SkipError as skip:
            await self._finish(claim, "skipped", reason=skip.reason, now=now)
            return "skipped"
        except _FailError as fail:
            await self._finish(claim, "failed", reason=fail.reason, now=now)
            return "failed"

        try:
            if content.png is not None and not content.photo_already_sent:
                photo_id = await self.client.send_photo(
                    content.chat_id,
                    content.png,
                    content.caption,
                )
                await self._remember_photo(claim.message_id, photo_id)
            # Tin chi tiết gửi im lặng: ảnh kèm caption đã đủ để báo, tránh rung điện thoại hai lần.
            text_id = await self.client.send_message(
                content.chat_id,
                content.text,
                disable_notification=content.png is not None or content.photo_already_sent,
            )
        except TelegramForbiddenError:
            await self._block(content.telegram_user_id)
            await self._finish(claim, "skipped", reason="blocked", now=now)
            return "skipped"
        except TelegramRateLimitError as exc:
            delay = min(timedelta(seconds=(exc.retry_after or 5) + 1), MAX_RETRY_AFTER)
            return await self._retry(claim, now, "rate_limit", delay)
        except (TelegramMessageTooLongError, TelegramApiError) as exc:
            code = exc.error_code if isinstance(exc, TelegramApiError) else 400
            if code in (401, 404):
                # Token bị thu hồi hoặc sai cấu hình: giữ tin, không đốt số lần thử, chờ sửa.
                return await self._hold(claim, now, f"config_{code}")
            if code is None or code >= 500:  # None: phản hồi không đọc được (lỗi gateway)
                return await self._retry(claim, now, f"http_{code}", self._backoff(claim))
            # 400 (HTML sai, tin quá dài...): lỗi cuối cùng, thử lại không giúp ích.
            await self._finish(
                claim,
                "failed",
                reason="telegram_rejected",
                now=now,
                error=_describe(exc),
            )
            return "failed"
        except TelegramNetworkError:
            return await self._retry(claim, now, "network", self._backoff(claim))

        await self._finish(claim, "sent", reason=None, now=now, telegram_message_id=text_id)
        return "sent"

    async def _build(self, message_id: UUID, settings: PriceAlertSetting) -> _Content:
        async with self.session_factory() as session:
            message = await session.get(PriceAlertMessage, message_id)
            if message is None:
                raise _FailError("message_missing")
            account = (
                await session.get(TelegramAccount, message.telegram_account_id)
                if message.telegram_account_id
                else None
            )
            user = await session.get(User, message.user_id)
            if (
                account is None
                or account.status != "active"
                or user is None
                or user.status != UserStatus.ACTIVE
            ):
                raise _SkipError("ineligible")
            if self.pilot_emails and user.email.lower() not in self.pilot_emails:
                raise _SkipError("pilot")

            if message.kind == "digest":
                count = (
                    await session.execute(
                        select(func.count()).where(PriceAlertMessageEvent.message_id == message.id),
                    )
                ).scalar_one()
                text = (
                    f"📋 Còn {count} thay đổi giá khác vượt ngưỡng trong thời gian ngắn.\n"
                    f"Xem trên web: {self.base_url.rstrip('/')}/quotes"
                )
                return _Content(account.chat_id, account.telegram_user_id, None, text, text, False)

            view = await load_message_view(session, message.id, settings)
            if view is None:
                raise _FailError("no_content")
            spec = await load_chart_spec(session, message.id, view)
            photo_done = message.status_reason == _PHOTO_SENT
        png = await render_price_chart(spec) if spec is not None else None
        return _Content(
            account.chat_id,
            account.telegram_user_id,
            png,
            format_caption(view),
            format_details(view, base_url=self.base_url),
            photo_done,
        )

    async def _remember_photo(self, message_id: UUID, photo_id: int) -> None:
        """Nhớ ảnh đã gửi để lần thử lại sau lỗi ở tin chi tiết không gửi ảnh lần hai."""
        async with self.session_factory() as session:
            await session.execute(
                update(PriceAlertMessage)
                .where(PriceAlertMessage.id == message_id)
                .values(status_reason=_PHOTO_SENT, telegram_message_id=photo_id),
            )
            await session.commit()

    async def _finish(
        self,
        claim: _Claim,
        status: str,
        *,
        reason: str | None,
        now: datetime,
        telegram_message_id: int | None = None,
        error: str | None = None,
    ) -> None:
        message_id, attempts = claim.message_id, claim.attempts
        values: dict[str, object] = {
            "status": status,
            "status_reason": reason,
            "lease_until": None,
            "last_error": error or (reason if status == "failed" else None),
        }
        if status == "sent":
            values["sent_at"] = now
            values["telegram_message_id"] = telegram_message_id
            values["last_error"] = None
        async with self.session_factory() as session:
            result = await session.execute(
                update(PriceAlertMessage)
                .where(
                    PriceAlertMessage.id == message_id,
                    PriceAlertMessage.status == "sending",
                    PriceAlertMessage.attempts == attempts,
                )
                .values(**values),
            )
            await session.commit()
        if not getattr(result, "rowcount", 0):
            # Tin đã bị worker khác nhận lại (lease hết hạn): không ghi đè kết quả của họ.
            logger.warning("price_alert.finish_skipped message_id=%s status=%s", message_id, status)
        elif status in ("failed", "skipped"):
            logger.warning(
                "price_alert.message_%s message_id=%s reason=%s", status, message_id, reason
            )

    async def _retry(self, claim: _Claim, now: datetime, reason: str, delay: timedelta) -> str:
        if claim.attempts >= MAX_ATTEMPTS:
            await self._finish(claim, "failed", reason="max_attempts", now=now, error=reason)
            return "failed"
        logger.warning("price_alert.retry message_id=%s reason=%s", claim.message_id, reason)
        async with self.session_factory() as session:
            message = await session.get(PriceAlertMessage, claim.message_id)
            keep_photo = message is not None and message.status_reason == _PHOTO_SENT
            await session.execute(
                update(PriceAlertMessage)
                .where(
                    PriceAlertMessage.id == claim.message_id,
                    PriceAlertMessage.status == "sending",
                    PriceAlertMessage.attempts == claim.attempts,
                )
                .values(
                    status="pending",
                    status_reason=_PHOTO_SENT if keep_photo else reason,
                    lease_until=now + delay,
                    last_error=reason,
                ),
            )
            await session.commit()
        return "retried"

    async def _hold(self, claim: _Claim, now: datetime, reason: str) -> str:
        """Lỗi cấu hình (token): giữ tin `pending`, hoàn lại lượt thử, thử lại sau ít phút."""
        logger.error("price_alert.config_error message_id=%s reason=%s", claim.message_id, reason)
        async with self.session_factory() as session:
            await session.execute(
                update(PriceAlertMessage)
                .where(
                    PriceAlertMessage.id == claim.message_id,
                    PriceAlertMessage.status == "sending",
                    PriceAlertMessage.attempts == claim.attempts,
                )
                .values(
                    status="pending",
                    lease_until=now + CONFIG_ERROR_DELAY,
                    attempts=claim.attempts - 1,
                    last_error=reason,
                ),
            )
            await session.commit()
        return "retried"

    async def _block(self, telegram_user_id: int) -> None:
        async with self.session_factory() as session:
            await TelegramLinkService(session).mark_blocked(telegram_user_id)
            await session.commit()

    @staticmethod
    def _backoff(claim: _Claim) -> timedelta:
        return timedelta(seconds=BACKOFF_BASE.total_seconds() * 2 ** (claim.attempts - 1))


class _SkipError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class _FailError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _describe(exc: Exception) -> str:
    """Mô tả lỗi để lưu: tên lớp và mô tả của Telegram (không có token, không có URL)."""
    return f"{type(exc).__name__}: {exc}"[:_MAX_ERROR_LENGTH]
