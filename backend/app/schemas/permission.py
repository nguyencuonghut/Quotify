from __future__ import annotations

from pydantic import BaseModel


class PermissionResponse(BaseModel):
    code: str
    description: str | None = None
