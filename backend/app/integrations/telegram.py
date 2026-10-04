from __future__ import annotations

import html
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from app.core.config import Settings

TELEGRAM_MESSAGE_MAX_LENGTH = 4096
DEFAULT_TELEGRAM_API_BASE_URL = "https://api.telegram.org"


class TelegramError(Exception):
    """Lỗi gốc của tích hợp Telegram. Thông điệp KHÔNG bao giờ chứa token bot."""


class TelegramConfigurationError(TelegramError):
    """Tính năng Telegram chưa được bật hoặc chưa cấu hình đủ."""


class TelegramNetworkError(TelegramError):
    """Không gọi được Telegram (mạng, timeout...). Đã làm sạch, không chứa URL."""


class TelegramMessageTooLongError(TelegramError):
    """Nội dung tin nhắn vượt giới hạn 4.096 ký tự của Telegram."""


class TelegramApiError(TelegramError):
    def __init__(
        self,
        description: str,
        *,
        error_code: int | None = None,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(description)
        self.description = description
        self.error_code = error_code
        self.retry_after = retry_after


class TelegramForbiddenError(TelegramApiError):
    """Telegram trả 403: thường là người dùng đã chặn bot."""


class TelegramRateLimitError(TelegramApiError):
    """Telegram trả 429: vượt giới hạn tốc độ, xem `retry_after`."""


@dataclass(frozen=True, slots=True)
class TelegramBotInfo:
    id: int
    username: str | None
    first_name: str | None


def escape_html(value: str) -> str:
    """Escape dữ liệu động trước khi chèn vào tin nhắn `parse_mode=HTML`."""
    return html.escape(value, quote=False)


class TelegramClient:
    """Client Telegram Bot API mỏng, an toàn với token.

    Token bot nằm trong URL (`/bot<token>/METHOD`) nên mọi đường lộ URL phải bị
    chặn: không `raise_for_status()`, không chuyển tiếp thông điệp lỗi của
    httpx, và ném lại lỗi đã làm sạch bằng `from None`.
    """

    def __init__(
        self,
        *,
        token: str,
        api_base_url: str = DEFAULT_TELEGRAM_API_BASE_URL,
        timeout_seconds: float = 10.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._token = token
        self._api_base_url = api_base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._http_client = http_client
        self._owns_http_client = http_client is None

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> TelegramClient:
        if not settings.telegram_bot_token:
            raise TelegramConfigurationError("Chưa cấu hình TELEGRAM_BOT_TOKEN.")
        return cls(
            token=settings.telegram_bot_token,
            api_base_url=settings.telegram_api_base_url,
            timeout_seconds=settings.telegram_http_timeout_seconds,
            http_client=http_client,
        )

    def __repr__(self) -> str:
        return f"TelegramClient(api_base_url={self._api_base_url!r}, token=<redacted>)"

    async def aclose(self) -> None:
        if self._http_client is not None and self._owns_http_client:
            await self._http_client.aclose()
            self._http_client = None

    async def get_me(self) -> TelegramBotInfo:
        result = await self._call("getMe")
        return TelegramBotInfo(
            id=int(result["id"]),
            username=result.get("username"),
            first_name=result.get("first_name"),
        )

    async def send_message(
        self,
        chat_id: int,
        text: str,
        *,
        parse_mode: str | None = "HTML",
        reply_markup: dict[str, Any] | None = None,
    ) -> int:
        if len(text) > TELEGRAM_MESSAGE_MAX_LENGTH:
            raise TelegramMessageTooLongError(
                f"Tin nhắn dài {len(text)} ký tự, vượt giới hạn {TELEGRAM_MESSAGE_MAX_LENGTH}.",
            )
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        result = await self._call("sendMessage", payload)
        return int(result["message_id"])

    async def set_webhook(
        self,
        *,
        url: str,
        secret_token: str,
        allowed_updates: list[str],
        drop_pending_updates: bool = False,
    ) -> None:
        await self._call(
            "setWebhook",
            {
                "url": url,
                "secret_token": secret_token,
                "allowed_updates": allowed_updates,
                "drop_pending_updates": drop_pending_updates,
            },
        )

    async def delete_webhook(self, *, drop_pending_updates: bool = False) -> None:
        await self._call("deleteWebhook", {"drop_pending_updates": drop_pending_updates})

    async def get_webhook_info(self) -> dict[str, Any]:
        result = await self._call("getWebhookInfo")
        return dict(result)

    async def get_updates(
        self,
        *,
        offset: int | None,
        timeout_seconds: int,
        allowed_updates: list[str],
    ) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {
            "timeout": timeout_seconds,
            "allowed_updates": allowed_updates,
        }
        if offset is not None:
            payload["offset"] = offset
        # Timeout HTTP phải lớn hơn thời gian long-poll, nếu không request bị cắt giữa chừng.
        result = await self._call("getUpdates", payload, http_timeout=timeout_seconds + 10)
        return [dict(item) for item in result]

    async def set_my_commands(
        self,
        commands: list[dict[str, str]],
        *,
        scope: dict[str, str] | None = None,
    ) -> None:
        payload: dict[str, Any] = {"commands": commands}
        if scope is not None:
            payload["scope"] = scope
        await self._call("setMyCommands", payload)

    def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient()
        return self._http_client

    async def _call(
        self,
        method: str,
        payload: dict[str, Any] | None = None,
        *,
        http_timeout: float | None = None,
    ) -> Any:
        url = f"{self._api_base_url}/bot{self._token}/{method}"
        try:
            response = await self._get_http_client().post(
                url,
                json=payload or {},
                timeout=http_timeout or self._timeout_seconds,
            )
        except httpx.HTTPError as exc:
            # `from None`: ngắt chuỗi nguyên nhân, vì exception của httpx có thể mang URL (token).
            raise TelegramNetworkError(
                f"Không thể gọi Telegram ({method}): {type(exc).__name__}.",
            ) from None

        try:
            body = response.json()
        except ValueError:
            raise TelegramApiError(
                f"Phản hồi Telegram không hợp lệ ({method}).",
                error_code=response.status_code,
            ) from None

        if not isinstance(body, dict) or not body.get("ok"):
            self._raise_api_error(method, body, response.status_code)
        return body.get("result")

    @staticmethod
    def _raise_api_error(method: str, body: Any, http_status: int) -> None:
        data = body if isinstance(body, dict) else {}
        error_code = data.get("error_code")
        if not isinstance(error_code, int):
            error_code = http_status
        description = str(data.get("description") or f"Lỗi Telegram ({method}).")
        parameters = data.get("parameters")
        retry_after = None
        if isinstance(parameters, dict) and isinstance(parameters.get("retry_after"), int):
            retry_after = parameters["retry_after"]

        if error_code == 403:
            raise TelegramForbiddenError(description, error_code=error_code)
        if error_code == 429:
            raise TelegramRateLimitError(
                description,
                error_code=error_code,
                retry_after=retry_after,
            )
        raise TelegramApiError(description, error_code=error_code, retry_after=retry_after)
