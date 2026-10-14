from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import has_permission
from app.auth.service import AuthService
from app.models.telegram_account import TELEGRAM_ACCOUNT_HOLDING_STATUSES, TelegramAccount
from app.models.user import User


@dataclass(frozen=True, slots=True)
class BotPrincipal:
    """Người dùng Quotify đứng sau một tin nhắn Telegram, kèm quyền để kiểm từng công cụ.

    Service không tự kiểm quyền (RR-3), nên mọi công cụ của chatbot phải hỏi `can(...)`. Nạp mới
    ở mỗi tin: quyền bị thu hồi giữa hai tin có hiệu lực ở tin kế tiếp.
    """

    # `repr=False`: bản ghi người dùng đầy đủ (có băm mật khẩu) không được lọt vào log.
    user: User = field(repr=False)

    @property
    def user_id(self) -> UUID:
        return self.user.id

    def can(self, permission_code: str) -> bool:
        return has_permission(self.user, permission_code)


async def load_bot_principal(session: AsyncSession, user_id: UUID) -> BotPrincipal | None:
    """`None` nếu người dùng không còn tồn tại hoặc không còn `ACTIVE`."""
    user = await AuthService(session).get_active_user(user_id=user_id)
    return BotPrincipal(user) if user is not None else None


async def delivery_block_reason(
    session: AsyncSession,
    *,
    telegram_user_id: int,
    user_id: UUID | None = None,
) -> str | None:
    """Vì sao KHÔNG nên gửi tin cho Telegram này, hoặc `None` nếu liên kết còn hiệu lực.

    `forbidden`: người dùng đã chặn bot (liên kết `blocked`). `unlinked`: không còn liên kết nào
    đang giữ, hoặc liên kết giờ thuộc về người dùng khác (`user_id` cho trước thì phải khớp).
    """
    row = (
        await session.execute(
            select(TelegramAccount.status, TelegramAccount.user_id).where(
                TelegramAccount.telegram_user_id == telegram_user_id,
                TelegramAccount.status.in_(TELEGRAM_ACCOUNT_HOLDING_STATUSES),
            )
        )
    ).first()
    if row is None or (user_id is not None and row.user_id != user_id):
        return "unlinked"
    return "forbidden" if row.status == "blocked" else None
