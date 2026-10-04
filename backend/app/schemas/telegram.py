from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class TelegramAccountRead(BaseModel):
    """Chỉ trả những gì giao diện cần. Không trả `telegram_user_id` hay `chat_id`."""

    model_config = ConfigDict(from_attributes=True)

    status: Literal["active", "blocked"]
    username: str | None
    first_name: str | None
    linked_at: datetime


class TelegramPendingLinkRead(BaseModel):
    expires_at: datetime
    expires_in_seconds: int


class TelegramLinkStatusRead(BaseModel):
    enabled: bool
    bot_username: str | None
    account: TelegramAccountRead | None
    pending_link: TelegramPendingLinkRead | None


class TelegramLinkTokenRead(BaseModel):
    deep_link: str
    expires_at: datetime
    expires_in_seconds: int
    bot_username: str
