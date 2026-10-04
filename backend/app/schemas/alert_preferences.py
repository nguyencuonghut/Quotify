from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

AlertLevel = Literal["light", "medium", "large"]


class AlertPreferencesUpdateRequest(BaseModel):
    is_enabled: bool
    # None nghĩa là dùng mức mặc định theo vai trò.
    min_level: AlertLevel | None = None
    admin_receive_all: bool = False


class AlertPreferencesResponse(BaseModel):
    is_enabled: bool
    min_level: AlertLevel | None
    effective_min_level: AlertLevel
    admin_receive_all: bool
