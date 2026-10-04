from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.models import User
from app.schemas.telegram import (
    TelegramAccountRead,
    TelegramLinkStatusRead,
    TelegramLinkTokenRead,
    TelegramPendingLinkRead,
)
from app.services.audit_log import AuditLogContext, AuditLogService
from app.services.telegram_link_service import TelegramLinkService

router = APIRouter(prefix="/users/me/telegram", tags=["telegram"])


def get_telegram_link_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TelegramLinkService:
    return TelegramLinkService(session)


def get_audit_log_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuditLogService:
    return AuditLogService(session)


def _is_enabled(settings: Settings) -> bool:
    return settings.telegram_enabled and bool(settings.telegram_bot_username)


@router.get("", response_model=TelegramLinkStatusRead)
async def get_telegram_link_status(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[TelegramLinkService, Depends(get_telegram_link_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TelegramLinkStatusRead:
    if not _is_enabled(settings):
        # Giữ nguyên hợp đồng khi tắt tính năng: vẫn 200 để giao diện tự ẩn panel.
        return TelegramLinkStatusRead(
            enabled=False,
            bot_username=None,
            account=None,
            pending_link=None,
        )

    link_status = await service.get_status(current_user.id)
    pending_link = None
    if link_status.pending_expires_at is not None:
        pending_link = TelegramPendingLinkRead(
            expires_at=link_status.pending_expires_at,
            expires_in_seconds=link_status.pending_expires_in_seconds or 0,
        )
    return TelegramLinkStatusRead(
        enabled=True,
        bot_username=settings.telegram_bot_username,
        account=(
            TelegramAccountRead.model_validate(link_status.account)
            if link_status.account is not None
            else None
        ),
        pending_link=pending_link,
    )


@router.post(
    "/link-token",
    response_model=TelegramLinkTokenRead,
    status_code=status.HTTP_201_CREATED,
)
async def issue_telegram_link_token(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[TelegramLinkService, Depends(get_telegram_link_service)],
    audit_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TelegramLinkTokenRead:
    if not _is_enabled(settings):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram integration is not enabled.",
        )
    await _enforce_link_token_rate_limit(request, current_user, settings)

    issued = await service.issue_link_token(current_user.id)
    await audit_service.log_event(
        action="telegram.link_requested",
        entity_type="telegram_link_token",
        context=AuditLogContext.from_request(
            request=request,
            current_user=current_user,
            entity_id=str(issued.token_id),
            metadata_json={"channel": "web"},
        ),
    )
    await session.commit()

    return TelegramLinkTokenRead(
        deep_link=f"https://t.me/{settings.telegram_bot_username}?start={issued.token}",
        expires_at=issued.expires_at,
        expires_in_seconds=issued.expires_in_seconds,
        bot_username=settings.telegram_bot_username,
    )


@router.delete("/link-token", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_telegram_link_request(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[TelegramLinkService, Depends(get_telegram_link_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    await service.cancel_pending(current_user.id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_telegram_account(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[TelegramLinkService, Depends(get_telegram_link_service)],
    audit_service: Annotated[AuditLogService, Depends(get_audit_log_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    # Không phụ thuộc cờ `TELEGRAM_ENABLED`: tắt tính năng không được làm kẹt việc hủy liên kết.
    account = await service.revoke_user_link(current_user.id, reason="user_unlink")
    if account is not None:
        await audit_service.log_event(
            action="telegram.unlinked",
            entity_type="telegram_account",
            context=AuditLogContext.from_request(
                request=request,
                current_user=current_user,
                entity_id=str(account.id),
                metadata_json={
                    "channel": "web",
                    "telegram_account_id": str(account.id),
                    "reason": "user_unlink",
                },
            ),
        )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _enforce_link_token_rate_limit(
    request: Request,
    current_user: User,
    settings: Settings,
) -> None:
    limit = settings.rate_limit_telegram_link_token
    window_seconds = settings.rate_limit_window_seconds
    if limit <= 0 or window_seconds <= 0:
        return
    decision = await request.app.state.rate_limiter.hit(
        key=f"telegram.link_token:{current_user.id}",
        limit=limit,
        window_seconds=window_seconds,
    )
    if not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded.",
            headers={"Retry-After": str(decision.retry_after)},
        )
