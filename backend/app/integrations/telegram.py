from __future__ import annotations

import html
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from app.core.config import Settings

TELEGRAM_MESSAGE_MAX_LENGTH = 4096
TELEGRAM_CAPTION_MAX_LENGTH = 1024
# Loại update webhook và poller cùng nhận; `callback_query` cho nút duyệt giá bất thường.
ALLOWED_UPDATES = ["message", "my_chat_member", "callback_query"]
_NOT_MODIFIED_MARKER = "message is not modified"
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
        disable_notification: bool = False,
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
        if disable_notification:
            payload["disable_notification"] = True
        result = await self._call("sendMessage", payload)
        return int(result["message_id"])

    async def send_photo(
        self,
        chat_id: int,
        png: bytes,
        caption: str,
        *,
        parse_mode: str | None = "HTML",
        reply_markup: dict[str, Any] | None = None,
    ) -> int:
        """Gửi ảnh PNG (multipart) kèm caption; trả về `message_id`.

        Caption dài hơn 1.024 ký tự bị từ chối TRƯỚC khi gọi mạng. `reply_markup`
        được gửi dưới dạng chuỗi JSON vì multipart không mang được object lồng nhau.
        """
        if len(caption) > TELEGRAM_CAPTION_MAX_LENGTH:
            raise TelegramMessageTooLongError(
                f"Caption dài {len(caption)} ký tự, vượt giới hạn {TELEGRAM_CAPTION_MAX_LENGTH}.",
            )
        data: dict[str, Any] = {"chat_id": str(chat_id), "caption": caption}
        if parse_mode:
            data["parse_mode"] = parse_mode
        if reply_markup is not None:
            data["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
        result = await self._call(
            "sendPhoto",
            data=data,
            files={"photo": ("chart.png", png, "image/png")},
        )
        return int(result["message_id"])

    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: str | None = None,
        show_alert: bool = False,
    ) -> None:
        payload: dict[str, Any] = {"callback_query_id": callback_query_id}
        if text is not None:
            payload["text"] = text
        if show_alert:
            payload["show_alert"] = True
        await self._call("answerCallbackQuery", payload)

    async def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        *,
        parse_mode: str | None = "HTML",
        reply_markup: dict[str, Any] | None = None,
    ) -> bool:
        """Sửa nội dung tin văn bản. Không dùng được cho tin ảnh (dùng `edit_message_caption`).

        Trả `True` nếu đã sửa, `False` nếu Telegram báo 400 `message is not modified`
        (nội dung y hệt, coi là thành công). Mọi lỗi 400 khác vẫn ném `TelegramApiError`.
        """
        if len(text) > TELEGRAM_MESSAGE_MAX_LENGTH:
            raise TelegramMessageTooLongError(
                f"Tin nhắn dài {len(text)} ký tự, vượt giới hạn {TELEGRAM_MESSAGE_MAX_LENGTH}.",
            )
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        return await self._call_edit("editMessageText", payload)

    async def edit_message_caption(
        self,
        chat_id: int,
        message_id: int,
        caption: str,
        *,
        parse_mode: str | None = "HTML",
        reply_markup: dict[str, Any] | None = None,
    ) -> bool:
        """Sửa caption của tin ảnh (tin ảnh không có text nên `editMessageText` bị 400).

        Trả `True` nếu đã sửa, `False` nếu 400 `message is not modified` (coi là thành công).
        Mọi lỗi 400 khác vẫn ném `TelegramApiError`.
        """
        if len(caption) > TELEGRAM_CAPTION_MAX_LENGTH:
            raise TelegramMessageTooLongError(
                f"Caption dài {len(caption)} ký tự, vượt giới hạn {TELEGRAM_CAPTION_MAX_LENGTH}.",
            )
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "caption": caption,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        return await self._call_edit("editMessageCaption", payload)

    async def edit_message_reply_markup(
        self,
        chat_id: int,
        message_id: int,
        reply_markup: dict[str, Any] | None = None,
    ) -> bool:
        """Thay bàn phím inline của tin; `reply_markup=None` nghĩa là bỏ bàn phím.

        Trả `True` nếu đã sửa, `False` nếu 400 `message is not modified` (coi là thành công).
        Mọi lỗi 400 khác vẫn ném `TelegramApiError`.
        """
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "reply_markup": reply_markup if reply_markup is not None else {"inline_keyboard": []},
        }
        return await self._call_edit("editMessageReplyMarkup", payload)

    async def _call_edit(self, method: str, payload: dict[str, Any]) -> bool:
        try:
            await self._call(method, payload)
        except TelegramApiError as exc:
            if exc.error_code == 400 and _NOT_MODIFIED_MARKER in exc.description.lower():
                return False
            raise
        return True

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
        data: dict[str, Any] | None = None,
        files: dict[str, tuple[str, bytes, str]] | None = None,
    ) -> Any:
        url = f"{self._api_base_url}/bot{self._token}/{method}"
        try:
            timeout = http_timeout or self._timeout_seconds
            if files is not None:
                # Multipart (sendPhoto): `data` là các trường form, `files` là phần tải lên.
                response = await self._get_http_client().post(
                    url,
                    data=data,
                    files=files,
                    timeout=timeout,
                )
            else:
                response = await self._get_http_client().post(
                    url,
                    json=payload or {},
                    timeout=timeout,
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
