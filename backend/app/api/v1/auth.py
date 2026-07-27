from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.permissions import resolve_permission_codes, resolve_role_names
from app.auth.service import (
    AuthService,
    InactiveUserError,
    InvalidCredentialsError,
    RefreshTokenError,
)
from app.core.config import Settings, get_settings
from app.core.rate_limit import build_rate_limit_dependency
from app.db.session import get_db_session
from app.models import User
from app.schemas.auth import AccessTokenResponse, CurrentUserResponse, LoginRequest
from app.services import AuditLogContext, AuditLogService

router = APIRouter(prefix="/auth", tags=["auth"])

limit_auth_login = build_rate_limit_dependency(
    scope="auth.login",
    limit_setting="rate_limit_auth_login",
)


def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuthService:
    return AuthService(session)


def get_audit_log_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuditLogService:
    return AuditLogService(session)


@router.post(
    "/login",
    response_model=AccessTokenResponse,
    dependencies=[Depends(limit_auth_login)],
)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    audit_log_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AccessTokenResponse:
    try:
        auth_bundle = await auth_service.authenticate(
            email=payload.email,
            password=payload.password,
        )
    except (InvalidCredentialsError, InactiveUserError) as exc:
        await audit_log_service.log_event(
            action="auth.login_failed",
            entity_type="auth_session",
            context=AuditLogContext.from_request(
                request=request,
                metadata_json={
                    "email": payload.email,
                    "outcome": "failed",
                },
            ),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        ) from exc

    _set_refresh_cookie(
        response=response,
        refresh_token=auth_bundle.refresh_token,
        settings=settings,
        expires_at=auth_bundle.refresh_token_expires_at,
    )

    await audit_log_service.log_event(
        action="auth.login_succeeded",
        entity_type="user",
        context=AuditLogContext.from_request(
            request=request,
            current_user=auth_bundle.user,
            entity_id=str(auth_bundle.user.id),
            metadata_json={
                "email": auth_bundle.user.email,
                "outcome": "succeeded",
            },
        ),
    )

    await auth_service.session.commit()

    return _build_access_token_response(
        auth_bundle.access_token,
        auth_bundle.access_token_expires_at,
    )


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    request: Request,
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    audit_log_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AccessTokenResponse:
    cookie_token = request.cookies.get(settings.auth_refresh_cookie_name)
    if cookie_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is missing.",
        )

    try:
        auth_bundle = await auth_service.refresh_session(refresh_token=cookie_token)
    except RefreshTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is invalid.",
        ) from exc

    _set_refresh_cookie(
        response=response,
        refresh_token=auth_bundle.refresh_token,
        settings=settings,
        expires_at=auth_bundle.refresh_token_expires_at,
    )

    await audit_log_service.log_event(
        action="auth.session_refreshed",
        entity_type="user",
        context=AuditLogContext.from_request(
            request=request,
            current_user=auth_bundle.user,
            entity_id=str(auth_bundle.user.id),
            metadata_json={
                "email": auth_bundle.user.email,
            },
        ),
    )

    await auth_service.session.commit()

    return _build_access_token_response(
        auth_bundle.access_token,
        auth_bundle.access_token_expires_at,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    audit_log_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    refresh_token = request.cookies.get(settings.auth_refresh_cookie_name)
    revoked_user: User | None = None
    if refresh_token is not None:
        revoked_user = await auth_service.revoke_refresh_token(refresh_token=refresh_token)

    _clear_refresh_cookie(response=response, settings=settings)

    await audit_log_service.log_event(
        action="auth.logout",
        entity_type="user",
        context=AuditLogContext.from_request(
            request=request,
            current_user=revoked_user,
            entity_id=str(revoked_user.id) if revoked_user is not None else None,
            metadata_json={
                "has_refresh_cookie": refresh_token is not None,
            },
        ),
    )
    await auth_service.session.commit()


@router.get("/me", response_model=CurrentUserResponse)
async def me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> CurrentUserResponse:
    return _build_current_user_response(current_user)


def _build_access_token_response(token: str, expires_at: datetime) -> AccessTokenResponse:
    expires_in = max(0, int((expires_at - datetime.now(UTC)).total_seconds()))
    return AccessTokenResponse(
        access_token=token,
        expires_in=expires_in,
    )


def _build_current_user_response(user: User) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=user.id,
        email=user.email,
        status=user.status.value,
        roles=sorted(resolve_role_names(user)),
        permissions=sorted(resolve_permission_codes(user)),
        last_login_at=user.last_login_at,
        full_name=user.full_name,
        avatar_url=user.avatar_url,
    )


def _set_refresh_cookie(
    *,
    response: Response,
    refresh_token: str,
    settings: Settings,
    expires_at: datetime,
) -> None:
    response.set_cookie(
        key=settings.auth_refresh_cookie_name,
        value=refresh_token,
        httponly=True,
        secure=settings.auth_refresh_cookie_secure,
        samesite=settings.auth_refresh_cookie_samesite,
        path=settings.auth_refresh_cookie_path,
        expires=expires_at,
    )
    response.set_cookie(
        key=settings.auth_logged_in_cookie_name,
        value="true",
        httponly=False,
        secure=settings.auth_refresh_cookie_secure,
        samesite=settings.auth_refresh_cookie_samesite,
        path="/",
        expires=expires_at,
    )


def _clear_refresh_cookie(*, response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.auth_refresh_cookie_name,
        path=settings.auth_refresh_cookie_path,
        samesite=settings.auth_refresh_cookie_samesite,
        secure=settings.auth_refresh_cookie_secure,
    )
    response.delete_cookie(
        key=settings.auth_logged_in_cookie_name,
        path="/",
        samesite=settings.auth_refresh_cookie_samesite,
        secure=settings.auth_refresh_cookie_secure,
    )
