"""Bot Telegram giả dựng trên PostgreSQL thật: runner thật, client qua `httpx.MockTransport`."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from db_helpers import create_user, issue_token, next_telegram_id, next_update_id
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from telegram_fakes import Outbox, make_update

from app.services.telegram_update_runner import TelegramUpdateRunner

FULL_NAME = "Nguyễn Văn <An> & Bình"
ESCAPED_NAME = "Nguyễn Văn &lt;An&gt; &amp; Bình"


@dataclass
class Bot:
    session_factory: async_sessionmaker[AsyncSession]
    runner: TelegramUpdateRunner
    outbox: Outbox
    # Chỉ có khi dựng bằng fixture `chatbot_bot` (đường ống chatbot bật).
    dispatcher: Any = None
    client: Any = None

    async def send(self, text_: str, *, tg: int, username: str | None = None) -> int:
        update_id = next_update_id()
        await self.runner.process(
            make_update(update_id, text_, user_id=tg, first_name="Telegram An", username=username),
        )
        return update_id

    async def inbox_rows(self, chat_id: int) -> list[Any]:
        """Các dòng hộp thư bot của một chat, theo thứ tự `update_id`.

        DB tạm dùng chung cả phiên test nên phải lọc theo chat (mỗi test có chat riêng).
        """
        async with self.session_factory() as session:
            result = await session.execute(
                text(
                    "select update_id, chat_id, user_id, status, payload_text, reply_text, "
                    "reply_saved_at, attempts, error_category, finished_at "
                    "from bot_updates where chat_id = :c "
                    "order by update_id"
                ),
                {"c": chat_id},
            )
            return list(result.all())

    async def drain(
        self,
        chat_id: int,
        *,
        engine: Any = None,
        config: Any = None,
        client: Any = None,
        session_factory: Any = None,
        readonly_session_factory: Any = None,
    ) -> int:
        """Chạy `drain_chat` của worker bot một lần cho một chat. Trả số dòng đã xử lý."""
        from app.bot_worker import BotWorkerConfig, drain_chat
        from app.services.chat_engine import StubChatEngine

        ctx = {
            "session_factory": session_factory or self.session_factory,
            "telegram_client": client or self.client,
            "chat_engine": engine or StubChatEngine(),
            "bot_config": config or BotWorkerConfig(),
        }
        if readonly_session_factory is not None:
            ctx["readonly_session_factory"] = readonly_session_factory
        return await drain_chat(ctx, chat_id)

    async def insert_row(
        self,
        chat_id: int,
        user_id: uuid.UUID,
        update_id: int,
        *,
        status: str = "queued",
        attempts: int = 0,
        lease_until: Any = None,
        text_: str = "x",
        received_at: Any = None,
        finished_at: Any = None,
        reply_text: str | None = None,
        sent_parts: int = 0,
    ) -> None:
        """Chèn thẳng một dòng hộp thư ở trạng thái tùy ý (dựng sẵn tình huống sự cố)."""
        async with self.session_factory() as session:
            await session.execute(
                text(
                    "insert into bot_updates (update_id, chat_id, telegram_user_id, user_id, "
                    "status, payload_text, attempts, lease_until, received_at, finished_at, "
                    "reply_text, sent_parts) "
                    "values (:id, :chat, :chat, :user, :status, :text, :attempts, :lease, "
                    "coalesce(:received, now()), :finished, :reply, :parts)"
                ),
                {
                    "id": update_id,
                    "chat": chat_id,
                    "user": user_id,
                    "status": status,
                    "text": text_,
                    "attempts": attempts,
                    "lease": lease_until,
                    "received": received_at,
                    "finished": finished_at,
                    "reply": reply_text,
                    "parts": sent_parts,
                },
            )
            await session.commit()

    async def sweep(self, *, config: Any = None, dispatcher: Any = None) -> Any:
        """Chạy `sweep_bot_updates` một lần; trả bên đánh chuông giả để xem đã rung cho ai."""
        from telegram_fakes import FakeBotDispatcher

        from app.bot_worker import BotWorkerConfig, sweep_bot_updates

        used = dispatcher if dispatcher is not None else FakeBotDispatcher()
        ctx = {
            "session_factory": self.session_factory,
            "bot_config": config or BotWorkerConfig(),
            "dispatcher": used,
        }
        await sweep_bot_updates(ctx)
        return used

    async def cleanup(self, *, config: Any = None) -> int:
        """Chạy `cleanup_bot_updates` một lần; trả số dòng đã xóa."""
        from app.bot_worker import BotWorkerConfig, cleanup_bot_updates

        ctx = {"session_factory": self.session_factory, "bot_config": config or BotWorkerConfig()}
        return await cleanup_bot_updates(ctx)

    async def set_lease(self, update_id: int, lease_until: Any) -> None:
        """Đặt `lease_until` của một dòng (vd cho lease hết hạn để mô phỏng worker đã chết)."""
        async with self.session_factory() as session:
            await session.execute(
                text("update bot_updates set lease_until = :l where update_id = :i"),
                {"l": lease_until, "i": update_id},
            )
            await session.commit()

    async def row(self, update_id: int) -> Any:
        async with self.session_factory() as session:
            result = await session.execute(
                text(
                    "select update_id, chat_id, status, attempts, lease_until, payload_text, "
                    "reply_text, reply_saved_at, sent_parts, error_category, finished_at "
                    "from bot_updates where update_id = :i"
                ),
                {"i": update_id},
            )
            return result.first()

    async def process_raw(self, payload: dict[str, Any]) -> None:
        await self.runner.process(payload)

    async def accounts(self, user_id: uuid.UUID) -> list[Any]:
        async with self.session_factory() as session:
            result = await session.execute(
                text(
                    "select id, telegram_user_id, status, revoked_reason, username, first_name, "
                    "last_seen_at from telegram_accounts where user_id = :u "
                    "order by created_at, id"
                ),
                {"u": user_id},
            )
            return list(result.all())

    async def audit(self, user_id: uuid.UUID | None = None) -> list[Any]:
        """Audit `telegram.*` của một người dùng; `None` thì chỉ sự kiện hệ thống (không actor)."""
        condition = "actor_user_id = :u" if user_id is not None else "actor_user_id is null"
        async with self.session_factory() as session:
            result = await session.execute(
                text(
                    "select action, entity_type, entity_id, metadata_json, request_id "
                    f"from audit_logs where {condition} and action like 'telegram.%' "
                    "order by created_at, id"
                ),
                {"u": user_id} if user_id is not None else {},
            )
            return list(result.all())


async def linked_user(bot: Bot, *, full_name: str = FULL_NAME) -> tuple[uuid.UUID, int]:
    """Một người dùng đã liên kết xong với một Telegram mới. Trả (user_id, telegram_user_id)."""
    user_id = await create_user(bot.session_factory, full_name=full_name)
    tg = next_telegram_id()
    await bot.send(f"/start {await issue_token(bot.session_factory, user_id)}", tg=tg)
    bot.outbox.requests.clear()
    return user_id, tg
