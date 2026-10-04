from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.telegram_processed_update import TelegramProcessedUpdate
from app.models.user import UserStatus
from app.services.audit_log import AuditLogContext, AuditLogService
from app.services.telegram_bot_messages import (
    HELP_TEXT,
    INVALID_LINK_TEXT,
    NOT_LINKED_TEXT,
    REPLACED_TEXT,
    START_TEXT,
    STOPPED_TEXT,
    TELEGRAM_IN_USE_TEXT,
    UNKNOWN_TEXT,
    USER_INACTIVE_TEXT,
    already_linked_text,
    linked_text,
    reactivated_text,
)
from app.services.telegram_link_service import RedeemOutcome, RedeemResult, TelegramLinkService

# Độ dài tối đa của cột `username`, `first_name` trong `telegram_accounts`.
_USERNAME_MAX = 64
_FIRST_NAME_MAX = 150


@dataclass(frozen=True, slots=True)
class OutboundMessage:
    chat_id: int
    text: str
    reply_markup: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class TelegramMessage:
    chat_id: int
    chat_type: str
    from_user_id: int | None
    text: str | None
    from_username: str | None = None
    from_first_name: str | None = None


@dataclass(frozen=True, slots=True)
class TelegramChatMemberChange:
    """Thay đổi trạng thái của bot trong một chat (`my_chat_member`), vd người dùng chặn bot."""

    chat_id: int
    chat_type: str
    from_user_id: int | None
    new_status: str


@dataclass(frozen=True, slots=True)
class TelegramUpdate:
    update_id: int
    message: TelegramMessage | None
    chat_member: TelegramChatMemberChange | None = None


def _as_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _truncate(value: str | None, limit: int) -> str | None:
    return value[:limit] if value else None


def _as_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def parse_update(payload: Any) -> TelegramUpdate | None:
    """Đọc update Telegram một cách khoan dung. Trả `None` nếu không có `update_id` hợp lệ."""
    if not isinstance(payload, dict):
        return None
    update_id = _as_int(payload.get("update_id"))
    if update_id is None:
        return None

    message: TelegramMessage | None = None
    raw_message = payload.get("message")
    if isinstance(raw_message, dict):
        chat = raw_message.get("chat")
        sender = raw_message.get("from")
        chat_id = _as_int(chat.get("id")) if isinstance(chat, dict) else None
        chat_type = chat.get("type") if isinstance(chat, dict) else None
        if chat_id is not None and isinstance(chat_type, str):
            text = raw_message.get("text")
            sender_data = sender if isinstance(sender, dict) else {}
            message = TelegramMessage(
                chat_id=chat_id,
                chat_type=chat_type,
                from_user_id=_as_int(sender_data.get("id")),
                text=text if isinstance(text, str) else None,
                from_username=_as_str(sender_data.get("username")),
                from_first_name=_as_str(sender_data.get("first_name")),
            )

    chat_member: TelegramChatMemberChange | None = None
    raw_member = payload.get("my_chat_member")
    if isinstance(raw_member, dict):
        chat = raw_member.get("chat")
        sender = raw_member.get("from")
        new_member = raw_member.get("new_chat_member")
        chat_id = _as_int(chat.get("id")) if isinstance(chat, dict) else None
        chat_type = chat.get("type") if isinstance(chat, dict) else None
        new_status = new_member.get("status") if isinstance(new_member, dict) else None
        if chat_id is not None and isinstance(chat_type, str) and isinstance(new_status, str):
            chat_member = TelegramChatMemberChange(
                chat_id=chat_id,
                chat_type=chat_type,
                from_user_id=_as_int(sender.get("id")) if isinstance(sender, dict) else None,
                new_status=new_status,
            )
    return TelegramUpdate(update_id=update_id, message=message, chat_member=chat_member)


def parse_command(text: str | None) -> tuple[str | None, str]:
    """Tách `/lệnh@tên_bot tham_số` thành (`/lệnh`, `tham_số`); không phải lệnh thì (None, '')."""
    if not text:
        return None, ""
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None, ""
    head, _, argument = stripped.partition(" ")
    command = head.split("@", 1)[0].lower()
    return command, argument.strip()


class TelegramUpdateService:
    """Xử lý một update Telegram. Chỉ `flush`, không `commit`; gửi tin do runner làm sau commit."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def handle(self, update: TelegramUpdate) -> list[OutboundMessage]:
        if not await self._record_update(update.update_id):
            return []

        if update.chat_member is not None:
            await self._handle_chat_member(update.chat_member)
            return []

        message = update.message
        if message is None or message.chat_type != "private" or message.from_user_id is None:
            return []

        telegram_user_id = message.from_user_id
        command, argument = parse_command(message.text)
        if command == "/start" and argument:
            # Đổi mã liên kết phải đi trước kiểm tra "người dùng không còn hoạt động", nếu không
            # người chủ cũ đã bị khóa sẽ không bao giờ liên kết được Telegram này cho tài khoản mới.
            return await self._handle_start(
                update.update_id,
                message,
                telegram_user_id=telegram_user_id,
                argument=argument,
            )

        link_service = TelegramLinkService(self.session)
        identity = await link_service.touch_linked_identity(
            telegram_user_id,
            chat_id=message.chat_id,
            username=_truncate(message.from_username, _USERNAME_MAX),
            first_name=_truncate(message.from_first_name, _FIRST_NAME_MAX),
        )
        if identity is not None and identity.user_status != UserStatus.ACTIVE:
            return [OutboundMessage(message.chat_id, USER_INACTIVE_TEXT)]

        if command == "/start":
            if identity is None:
                return [OutboundMessage(message.chat_id, START_TEXT)]
            return [OutboundMessage(message.chat_id, already_linked_text(identity.full_name))]
        if command == "/stop":
            return await self._handle_stop(update.update_id, message, telegram_user_id)
        if command == "/help":
            return [OutboundMessage(message.chat_id, HELP_TEXT)]
        return [OutboundMessage(message.chat_id, UNKNOWN_TEXT)]

    async def _handle_chat_member(self, change: TelegramChatMemberChange) -> None:
        """Người dùng chặn (`kicked`) hoặc bỏ chặn (`member`) bot trong chat riêng."""
        if change.chat_type != "private" or change.from_user_id is None:
            return
        link_service = TelegramLinkService(self.session)
        if change.new_status == "kicked":
            await link_service.mark_blocked(change.from_user_id)
        elif change.new_status == "member":
            await link_service.mark_unblocked(change.from_user_id)

    async def _handle_stop(
        self,
        update_id: int,
        message: TelegramMessage,
        telegram_user_id: int,
    ) -> list[OutboundMessage]:
        account = await TelegramLinkService(self.session).revoke_telegram_link(
            telegram_user_id,
            reason="stop_command",
        )
        if account is None:
            return [OutboundMessage(message.chat_id, NOT_LINKED_TEXT)]
        await self._audit_unlinked(
            update_id,
            actor_user_id=account.user_id,
            account_id=account.id,
            reason="stop_command",
        )
        return [OutboundMessage(message.chat_id, STOPPED_TEXT)]

    async def _handle_start(
        self,
        update_id: int,
        message: TelegramMessage,
        *,
        telegram_user_id: int,
        argument: str,
    ) -> list[OutboundMessage]:
        result = await TelegramLinkService(self.session).redeem(
            argument,
            telegram_user_id=telegram_user_id,
            chat_id=message.chat_id,
            username=_truncate(message.from_username, _USERNAME_MAX),
            first_name=_truncate(message.from_first_name, _FIRST_NAME_MAX),
        )
        await self._audit_redeem(update_id, result)
        return self._redeem_reply(message.chat_id, result)

    @staticmethod
    def _redeem_reply(chat_id: int, result: RedeemResult) -> list[OutboundMessage]:
        name = result.user_full_name or ""
        match result.outcome:
            case RedeemOutcome.LINKED:
                replies = [OutboundMessage(chat_id, linked_text(name))]
                if result.replaced_chat_id is not None:
                    replies.append(OutboundMessage(result.replaced_chat_id, REPLACED_TEXT))
                return replies
            case RedeemOutcome.REACTIVATED:
                return [OutboundMessage(chat_id, reactivated_text(name))]
            case RedeemOutcome.ALREADY_LINKED:
                return [OutboundMessage(chat_id, already_linked_text(name))]
            case RedeemOutcome.TELEGRAM_IN_USE:
                return [OutboundMessage(chat_id, TELEGRAM_IN_USE_TEXT)]
            case RedeemOutcome.USER_INACTIVE:
                return [OutboundMessage(chat_id, USER_INACTIVE_TEXT)]
            case RedeemOutcome.INVALID_LINK:
                return [OutboundMessage(chat_id, INVALID_LINK_TEXT)]

    async def _audit_unlinked(
        self,
        update_id: int,
        *,
        actor_user_id: UUID | None,
        account_id: UUID,
        reason: str,
    ) -> None:
        await AuditLogService(self.session).log_event(
            action="telegram.unlinked",
            entity_type="telegram_account",
            context=AuditLogContext(
                actor_user_id=actor_user_id,
                entity_id=str(account_id),
                metadata_json={
                    "channel": "telegram",
                    "telegram_account_id": str(account_id),
                    "reason": reason,
                },
                request_id=f"tg-update-{update_id}",
            ),
        )

    async def _audit_redeem(self, update_id: int, result: RedeemResult) -> None:
        """Ghi audit. Không ghi `telegram_user_id`/username. Mã sai hoặc lạ không audit."""
        if result.released_account_id is not None:
            # Hệ thống giải phóng liên kết của chủ cũ không còn hoạt động, không có người thao tác.
            await self._audit_unlinked(
                update_id,
                actor_user_id=None,
                account_id=result.released_account_id,
                reason="owner_inactive",
            )
        metadata: dict[str, object] = {"channel": "telegram"}
        match result.outcome:
            case RedeemOutcome.LINKED | RedeemOutcome.REACTIVATED:
                action, entity_type = "telegram.linked", "telegram_account"
                entity_id = str(result.account_id)
                metadata["telegram_account_id"] = entity_id
                if result.replaced_account_id is not None:
                    metadata["replaced_account_id"] = str(result.replaced_account_id)
                if result.outcome is RedeemOutcome.REACTIVATED:
                    metadata["reason"] = "reactivated"
            case RedeemOutcome.TELEGRAM_IN_USE | RedeemOutcome.USER_INACTIVE:
                action, entity_type = "telegram.link_rejected", "telegram_link_token"
                entity_id = str(result.token_id)
                metadata["reason"] = result.outcome.value
            case _:
                return
        await AuditLogService(self.session).log_event(
            action=action,
            entity_type=entity_type,
            context=AuditLogContext(
                actor_user_id=result.user_id,
                entity_id=entity_id,
                metadata_json=metadata,
                request_id=f"tg-update-{update_id}",
            ),
        )

    async def _record_update(self, update_id: int) -> bool:
        """Ghi `update_id`; trả False nếu đã có (update trùng). `RETURNING` thay cho `rowcount`."""
        statement = (
            pg_insert(TelegramProcessedUpdate)
            .values(update_id=update_id)
            .on_conflict_do_nothing(index_elements=["update_id"])
            .returning(TelegramProcessedUpdate.update_id)
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none() is not None
