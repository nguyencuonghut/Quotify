from __future__ import annotations

import json
from secrets import compare_digest
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.core.config import Settings, get_settings
from app.db.session import get_sessionmaker
from app.integrations.telegram import TelegramClient, TelegramConfigurationError
from app.services.telegram_update_runner import (
    TelegramTemporaryError,
    TelegramUpdateRunner,
)

router = APIRouter(prefix="/telegram", tags=["telegram"])

# Update của Telegram rất nhỏ; chặn body lớn bất thường trước khi parse.
MAX_WEBHOOK_BODY_BYTES = 256 * 1024


async def verify_telegram_webhook_secret(
    settings: Annotated[Settings, Depends(get_settings)],
    x_telegram_bot_api_secret_token: Annotated[str | None, Header()] = None,
) -> None:
    """404 khi tính năng tắt (không lộ route), 403 khi sai secret. Chạy TRƯỚC khi đọc body."""
    if not (
        settings.telegram_enabled
        and settings.telegram_mode == "webhook"
        and settings.telegram_webhook_secret
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    if x_telegram_bot_api_secret_token is None or not compare_digest(
        x_telegram_bot_api_secret_token.encode(),
        settings.telegram_webhook_secret.encode(),
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden.")


def get_telegram_runner(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> TelegramUpdateRunner:
    runner: TelegramUpdateRunner | None = getattr(request.app.state, "telegram_runner", None)
    if runner is None:
        try:
            client = TelegramClient.from_settings(settings)
        except TelegramConfigurationError:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Telegram chưa được cấu hình.",
            ) from None
        runner = TelegramUpdateRunner(session_factory=get_sessionmaker(), client=client)
        request.app.state.telegram_runner = runner
    return runner


@router.post(
    "/webhook",
    include_in_schema=False,
    dependencies=[Depends(verify_telegram_webhook_secret)],
)
async def telegram_webhook(
    request: Request,
    runner: Annotated[TelegramUpdateRunner, Depends(get_telegram_runner)],
) -> dict[str, bool]:
    """Nhận update từ Telegram. Luôn 200 với update đã xác thực (kể cả body lạ, update trùng).

    Nhận `Request` thay vì khai báo `body` kiểu dict: FastAPI sẽ trả 422 cho body hỏng TRƯỚC
    khi chạy dependency kiểm secret, làm lộ route và khiến Telegram thử lại.
    """
    body = await request.body()
    if not body or len(body) > MAX_WEBHOOK_BODY_BYTES:
        return {"ok": True}
    try:
        payload = json.loads(body)
    except ValueError:
        return {"ok": True}

    try:
        await runner.process(payload)
    except TelegramTemporaryError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Tạm thời chưa xử lý được.",
        ) from None
    return {"ok": True}
