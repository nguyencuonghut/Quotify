from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_permission
from app.db.session import get_db_session
from app.models import Permission, User
from app.schemas import PermissionResponse

router = APIRouter(prefix="/permissions", tags=["permissions"])


@router.get("", response_model=list[PermissionResponse])
async def list_permissions(
    current_user: Annotated[User, Depends(require_permission("permissions.read"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[PermissionResponse]:
    result = await session.execute(select(Permission).order_by(Permission.code))
    permissions = result.scalars().all()
    return [PermissionResponse(code=p.code, description=p.description) for p in permissions]
