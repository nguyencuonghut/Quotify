from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.session import get_db_session
from app.models import User
from app.schemas.alert_preferences import (
    AlertPreferencesResponse,
    AlertPreferencesUpdateRequest,
)
from app.services.user_alert_preference_service import (
    AlertPreferences,
    UserAlertPreferenceService,
)

# Đăng ký trước `users_router` trong router.py để `/users/{user_id}` không nuốt đường dẫn này.
router = APIRouter(prefix="/users/me/alert-preferences", tags=["users"])


def get_alert_preference_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserAlertPreferenceService:
    return UserAlertPreferenceService(session)


def _build_response(preferences: AlertPreferences) -> AlertPreferencesResponse:
    return AlertPreferencesResponse.model_validate(preferences, from_attributes=True)


@router.get("", response_model=AlertPreferencesResponse)
async def get_alert_preferences(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[UserAlertPreferenceService, Depends(get_alert_preference_service)],
) -> AlertPreferencesResponse:
    return _build_response(await service.get(current_user))


@router.put("", response_model=AlertPreferencesResponse)
async def update_alert_preferences(
    payload: AlertPreferencesUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[UserAlertPreferenceService, Depends(get_alert_preference_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AlertPreferencesResponse:
    try:
        preferences = await service.upsert(
            current_user,
            is_enabled=payload.is_enabled,
            min_level=payload.min_level,
            admin_receive_all=payload.admin_receive_all,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can receive all price alerts",
        ) from exc
    await session.commit()
    return _build_response(preferences)
