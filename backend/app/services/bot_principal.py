from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import has_permission
from app.auth.service import AuthService
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
