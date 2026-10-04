from __future__ import annotations

import math
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from hashlib import sha256
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.telegram_account import TELEGRAM_ACCOUNT_HOLDING_STATUSES, TelegramAccount
from app.models.telegram_link_token import TelegramLinkToken
from app.models.user import User, UserStatus

LINK_TOKEN_TTL = timedelta(minutes=10)

UQ_HOLDING_TELEGRAM_USER = "uq_telegram_accounts_holding_telegram_user"
UQ_HOLDING_USER = "uq_telegram_accounts_holding_user"


def hash_link_token(token: str) -> str:
    """Băm mã liên kết để tra cứu. Mã gốc không bao giờ được lưu hay ghi log."""
    return sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class IssuedLinkToken:
    token: str
    token_id: UUID
    expires_at: datetime
    expires_in_seconds: int


@dataclass(frozen=True, slots=True)
class TelegramLinkStatus:
    account: TelegramAccount | None
    pending_expires_at: datetime | None
    pending_expires_in_seconds: int | None


class RedeemOutcome(StrEnum):
    LINKED = "linked"
    REACTIVATED = "reactivated"
    ALREADY_LINKED = "already_linked"
    INVALID_LINK = "invalid_link"
    TELEGRAM_IN_USE = "telegram_in_use"
    USER_INACTIVE = "user_inactive"


@dataclass(frozen=True, slots=True)
class RedeemResult:
    outcome: RedeemOutcome
    user_id: UUID | None = None
    user_full_name: str | None = None
    token_id: UUID | None = None
    account_id: UUID | None = None
    replaced_account_id: UUID | None = None
    replaced_chat_id: int | None = None
    # Liên kết của chủ cũ không còn hoạt động đã bị thu hồi để nhường chỗ.
    released_account_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class LinkedIdentity:
    account: TelegramAccount
    full_name: str
    user_status: UserStatus


@dataclass(frozen=True, slots=True)
class AttachResult:
    """`account` là liên kết mới; nếu `None` thì `violated_constraint` nói unique nào bị vi phạm."""

    account: TelegramAccount | None
    violated_constraint: str | None = None


def _violated_constraint(exc: IntegrityError) -> str | None:
    """Tên constraint bị vi phạm, để chọn đúng thông điệp thay vì đoán theo nội dung lỗi."""
    original = exc.orig
    for candidate in (original, getattr(original, "__cause__", None)):
        name = getattr(candidate, "constraint_name", None)
        if isinstance(name, str):
            return name
    message = str(original)
    for known in (UQ_HOLDING_TELEGRAM_USER, UQ_HOLDING_USER):
        if known in message:
            return known
    return None


class TelegramLinkService:
    """Cấp, hủy, tra cứu và đổi mã liên kết. Chỉ `flush()`, việc `commit()` thuộc về người gọi."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def issue_link_token(self, user_id: UUID) -> IssuedLinkToken:
        # Khóa dòng người dùng để hai tab cùng bấm "Liên kết" nối tiếp nhau thay vì song song:
        # tab sau vô hiệu mã của tab trước, nên luôn chỉ còn đúng một mã hợp lệ.
        await self.session.execute(select(User.id).where(User.id == user_id).with_for_update())

        now = datetime.now(UTC)
        await self._expire_pending(user_id, now)

        token = secrets.token_urlsafe(32)
        record = TelegramLinkToken(
            user_id=user_id,
            token_hash=hash_link_token(token),
            expires_at=now + LINK_TOKEN_TTL,
        )
        self.session.add(record)
        await self.session.flush()
        return IssuedLinkToken(
            token=token,
            token_id=record.id,
            expires_at=record.expires_at,
            expires_in_seconds=int(LINK_TOKEN_TTL.total_seconds()),
        )

    async def cancel_pending(self, user_id: UUID) -> int:
        return await self._expire_pending(user_id, datetime.now(UTC))

    async def get_status(self, user_id: UUID) -> TelegramLinkStatus:
        now = datetime.now(UTC)
        account = await self.session.scalar(
            select(TelegramAccount).where(
                TelegramAccount.user_id == user_id,
                TelegramAccount.status.in_(TELEGRAM_ACCOUNT_HOLDING_STATUSES),
            ),
        )
        pending_expires_at = await self.session.scalar(
            select(TelegramLinkToken.expires_at)
            .where(
                TelegramLinkToken.user_id == user_id,
                TelegramLinkToken.used_at.is_(None),
                TelegramLinkToken.expires_at > now,
            )
            .order_by(TelegramLinkToken.expires_at.desc())
            .limit(1),
        )
        return TelegramLinkStatus(
            account=account,
            pending_expires_at=pending_expires_at,
            pending_expires_in_seconds=(
                None
                if pending_expires_at is None
                else max(0, math.ceil((pending_expires_at - now).total_seconds()))
            ),
        )

    async def _expire_pending(self, user_id: UUID, now: datetime) -> int:
        result = await self.session.execute(
            update(TelegramLinkToken)
            .where(
                TelegramLinkToken.user_id == user_id,
                TelegramLinkToken.used_at.is_(None),
                TelegramLinkToken.expires_at > now,
            )
            .values(expires_at=now),
        )
        return int(getattr(result, "rowcount", 0) or 0)

    async def find_holding_account(self, user_id: UUID) -> TelegramAccount | None:
        """Liên kết đang giữ (`active`/`blocked`) của người dùng, khóa dòng để thao tác tiếp."""
        return (
            await self.session.execute(
                select(TelegramAccount)
                .where(
                    TelegramAccount.user_id == user_id,
                    TelegramAccount.status.in_(TELEGRAM_ACCOUNT_HOLDING_STATUSES),
                )
                .with_for_update(),
            )
        ).scalar_one_or_none()

    async def touch_linked_identity(
        self,
        telegram_user_id: int,
        *,
        chat_id: int,
        username: str | None,
        first_name: str | None,
    ) -> LinkedIdentity | None:
        """Ghi nhận một tin nhận từ tài khoản Telegram đã liên kết và trả người dùng Quotify.

        Cập nhật `last_seen_at`, `chat_id`, `username`, `first_name`. Nhận được tin từ một liên
        kết đang `blocked` nghĩa là người dùng đã bỏ chặn bot (có thể ta lỡ mất update
        `my_chat_member`), nên đưa về `active`.
        """
        row = (
            await self.session.execute(
                select(TelegramAccount, User.full_name, User.status)
                .join(User, User.id == TelegramAccount.user_id)
                .where(
                    TelegramAccount.telegram_user_id == telegram_user_id,
                    TelegramAccount.status.in_(TELEGRAM_ACCOUNT_HOLDING_STATUSES),
                ),
            )
        ).first()
        if row is None:
            return None
        account, full_name, user_status = row
        account.last_seen_at = datetime.now(UTC)
        account.chat_id = chat_id
        account.username = username
        account.first_name = first_name
        if account.status == "blocked":
            account.status = "active"
        await self.session.flush()
        return LinkedIdentity(account=account, full_name=full_name, user_status=user_status)

    async def revoke_user_link(self, user_id: UUID, *, reason: str) -> TelegramAccount | None:
        """Thu hồi liên kết đang giữ của người dùng; không có thì trả `None` (idempotent)."""
        account = await self.find_holding_account(user_id)
        if account is not None:
            self._revoke(account, reason)
            await self.session.flush()
        return account

    async def revoke_telegram_link(
        self,
        telegram_user_id: int,
        *,
        reason: str,
    ) -> TelegramAccount | None:
        """Như `revoke_user_link` nhưng tìm theo tài khoản Telegram (lệnh `/stop`)."""
        account = (
            await self.session.execute(
                select(TelegramAccount)
                .where(
                    TelegramAccount.telegram_user_id == telegram_user_id,
                    TelegramAccount.status.in_(TELEGRAM_ACCOUNT_HOLDING_STATUSES),
                )
                .with_for_update(),
            )
        ).scalar_one_or_none()
        if account is not None:
            self._revoke(account, reason)
            await self.session.flush()
        return account

    async def mark_blocked(self, telegram_user_id: int) -> bool:
        """Người dùng đã chặn bot: `active` → `blocked`. Chỉ đổi liên kết đang `active`."""
        return await self._set_status(telegram_user_id, from_status="active", to_status="blocked")

    async def mark_unblocked(self, telegram_user_id: int) -> bool:
        """Người dùng bỏ chặn bot: `blocked` → `active`. Không đụng tới liên kết đã thu hồi."""
        return await self._set_status(telegram_user_id, from_status="blocked", to_status="active")

    async def _set_status(self, telegram_user_id: int, *, from_status: str, to_status: str) -> bool:
        result = await self.session.execute(
            update(TelegramAccount)
            .where(
                TelegramAccount.telegram_user_id == telegram_user_id,
                TelegramAccount.status == from_status,
            )
            .values(status=to_status),
        )
        return bool(getattr(result, "rowcount", 0))

    @staticmethod
    def _revoke(account: TelegramAccount, reason: str) -> None:
        account.status = "revoked"
        account.revoked_at = datetime.now(UTC)
        account.revoked_reason = reason

    async def redeem(
        self,
        token: str,
        *,
        telegram_user_id: int,
        chat_id: int,
        username: str | None,
        first_name: str | None,
    ) -> RedeemResult:
        """Đổi mã lấy liên kết Telegram. Mã sai, hết hạn hoặc đã dùng đều là `INVALID_LINK`."""
        now = datetime.now(UTC)
        # Khóa dòng mã: hai người cùng mở một đường dẫn sẽ nối tiếp nhau, người sau thấy mã đã dùng.
        link_token = (
            await self.session.execute(
                select(TelegramLinkToken)
                .where(TelegramLinkToken.token_hash == hash_link_token(token))
                .with_for_update(),
            )
        ).scalar_one_or_none()
        if link_token is None or link_token.used_at is not None or link_token.expires_at <= now:
            return RedeemResult(RedeemOutcome.INVALID_LINK)

        token_id, user_id = link_token.id, link_token.user_id
        user = (
            await self.session.execute(select(User).where(User.id == user_id))
        ).scalar_one_or_none()
        if user is None:
            return RedeemResult(RedeemOutcome.INVALID_LINK)
        full_name = user.full_name

        def result(
            outcome: RedeemOutcome,
            *,
            account_id: UUID | None = None,
            replaced_account_id: UUID | None = None,
            replaced_chat_id: int | None = None,
            released_account_id: UUID | None = None,
        ) -> RedeemResult:
            return RedeemResult(
                outcome,
                user_id=user_id,
                user_full_name=full_name,
                token_id=token_id,
                account_id=account_id,
                replaced_account_id=replaced_account_id,
                replaced_chat_id=replaced_chat_id,
                released_account_id=released_account_id,
            )

        if user.status != UserStatus.ACTIVE:
            return result(RedeemOutcome.USER_INACTIVE)

        holder = (
            await self.session.execute(
                select(TelegramAccount)
                .where(
                    TelegramAccount.telegram_user_id == telegram_user_id,
                    TelegramAccount.status.in_(TELEGRAM_ACCOUNT_HOLDING_STATUSES),
                )
                .with_for_update(),
            )
        ).scalar_one_or_none()
        released_account_id: UUID | None = None
        if holder is not None and holder.user_id != user_id:
            owner_status = (
                await self.session.execute(select(User.status).where(User.id == holder.user_id))
            ).scalar_one_or_none()
            if owner_status is not None and owner_status == UserStatus.ACTIVE:
                return result(RedeemOutcome.TELEGRAM_IN_USE)
            # Chủ cũ đã nghỉ hoặc bị khóa: nhường chỗ, kẻo Telegram này bị giữ vĩnh viễn.
            released_account_id = holder.id
            self._revoke(holder, "owner_inactive")
            await self.session.flush()
            holder = None

        if holder is not None:
            # Cùng người, cùng Telegram: không tạo bản ghi mới.
            reactivated = holder.status == "blocked"
            holder.status = "active"
            holder.chat_id = chat_id
            holder.username = username
            holder.first_name = first_name
            holder.last_seen_at = now
            link_token.used_at = now
            await self.session.flush()
            return result(
                RedeemOutcome.REACTIVATED if reactivated else RedeemOutcome.ALREADY_LINKED,
                account_id=holder.id,
            )

        existing = await self.find_holding_account(user_id)
        replaced_account_id = existing.id if existing is not None else None
        replaced_chat_id = existing.chat_id if existing is not None else None
        attached = await self.attach_account(
            user_id=user_id,
            existing=existing,
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
            username=username,
            first_name=first_name,
        )
        if attached.account is None:
            if attached.violated_constraint == UQ_HOLDING_TELEGRAM_USER:
                # Thua cuộc đua: người khác vừa giữ Telegram này giữa lúc kiểm tra và chèn.
                return result(
                    RedeemOutcome.TELEGRAM_IN_USE,
                    released_account_id=released_account_id,
                )
            raise RuntimeError(
                "Không thể gắn tài khoản Telegram: vi phạm ràng buộc không lường trước."
            )

        link_token.used_at = now
        await self.session.flush()
        return result(
            RedeemOutcome.LINKED,
            account_id=attached.account.id,
            replaced_account_id=replaced_account_id,
            replaced_chat_id=replaced_chat_id,
            released_account_id=released_account_id,
        )

    async def attach_account(
        self,
        *,
        user_id: UUID,
        existing: TelegramAccount | None,
        telegram_user_id: int,
        chat_id: int,
        username: str | None,
        first_name: str | None,
    ) -> AttachResult:
        """Thu hồi liên kết cũ (nếu có) và chèn liên kết mới trong MỘT savepoint.

        Chèn thất bại thì savepoint hoàn tác luôn việc thu hồi, người dùng không bao giờ mất
        liên kết cũ mà không có liên kết mới. `flush()` tường minh giữa hai bước để thứ tự
        UPDATE rồi INSERT không phụ thuộc vào nội bộ của ORM: nếu INSERT chạy trước thì sẽ vi
        phạm `uq_telegram_accounts_holding_user` vì liên kết cũ vẫn còn `active`.
        """
        now = datetime.now(UTC)
        account = TelegramAccount(
            user_id=user_id,
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
            username=username,
            first_name=first_name,
            status="active",
            linked_at=now,
            last_seen_at=now,
        )
        try:
            async with self.session.begin_nested():
                if existing is not None:
                    existing.status = "revoked"
                    existing.revoked_at = now
                    existing.revoked_reason = "replaced"
                    await self.session.flush()
                self.session.add(account)
                await self.session.flush()
        except IntegrityError as exc:
            return AttachResult(account=None, violated_constraint=_violated_constraint(exc))
        return AttachResult(account=account)
