"""Đường gửi câu trả lời của chatbot (kế hoạch 5.1, mục 4.7).

Câu trả lời do engine sinh được gửi dạng văn bản thuần. Telegram giới hạn mỗi tin 4.096 ký tự nên
tin dài được chia ở ranh giới đoạn, dòng hoặc khoảng trắng, tối đa `max_parts` phần.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

from app.integrations.telegram import TELEGRAM_MESSAGE_MAX_LENGTH, TelegramRateLimitError

ELLIPSIS = "…"
# Thứ tự ưu tiên của ranh giới: đoạn, rồi dòng, rồi khoảng trắng.
_SEPARATORS = ("\n\n", "\n", " ")
# Chờ ít nhất từng này giây khi gặp 429: Telegram không kèm `retry_after` (hoặc kèm 0) thì không
# được gọi lại liên tục.
_MIN_RETRY_AFTER_SECONDS = 1


class SendBudgetExceededError(Exception):
    """Phải chờ 429 lâu hơn thời gian còn lại của ngân sách gửi: dừng, để lần claim sau gửi tiếp.

    `retry_after`: số giây Telegram bảo chờ, để lần thử sau không đến sớm hơn mức đó.
    """

    def __init__(self, retry_after: float) -> None:
        super().__init__(f"Cần chờ {retry_after} giây, vượt ngân sách gửi.")
        self.retry_after = retry_after


def _now() -> float:
    return time.monotonic()


async def _wait(seconds: float) -> None:
    await asyncio.sleep(seconds)


def _units(text: str) -> int:
    """Độ dài tính bằng đơn vị UTF-16, cách Telegram đo (emoji ngoài BMP chiếm 2 đơn vị).

    Đếm theo UTF-16 thay vì số ký tự để một phần không bao giờ vượt giới hạn dù có emoji.
    """
    return len(text.encode("utf-16-le")) // 2


def _fit(text: str, limit: int) -> int:
    """Số ký tự dài nhất của tiền tố `text` có độ dài UTF-16 không quá `limit`."""
    units = 0
    for index, char in enumerate(text):
        units += 2 if ord(char) > 0xFFFF else 1
        if units > limit:
            return index
    return len(text)


def _boundary(rest: str, window: int) -> tuple[int, str] | None:
    """Vị trí và dấu ngắt để cắt `rest` trong cửa sổ `window` ký tự, hoặc `None` nếu không có.

    Ưu tiên ranh giới ở nửa sau của cửa sổ (đoạn, rồi dòng, rồi khoảng trắng) để không tạo phần quá
    ngắn, ví dụ tiêu đề ngắn rồi danh sách dài; không có thì lấy ranh giới nào cũng được.
    """
    for minimum in (window // 2, 1):
        for separator in _SEPARATORS:
            # Ranh giới có thể nằm ngay sau cửa sổ: phần trước nó vẫn vừa giới hạn.
            cut = rest.rfind(separator, 0, window + len(separator))
            if cut >= minimum:
                return cut, separator
    return None


def split_reply(
    text: str,
    *,
    max_parts: int,
    max_length: int = TELEGRAM_MESSAGE_MAX_LENGTH,
) -> list[str]:
    """Chia câu trả lời thành các phần không quá `max_length` (đơn vị UTF-16), đúng thứ tự.

    Vượt `max_parts` thì phần cuối bị cắt bớt và kết thúc bằng dấu "…".
    """
    parts: list[str] = []
    rest = text.strip()
    while rest:
        if len(parts) == max_parts:  # còn dư mà đã đủ số phần: cắt bớt, báo bằng dấu "…"
            last = parts[-1]
            parts[-1] = last[: _fit(last, max_length - 1)].rstrip() + ELLIPSIS
            break
        if _units(rest) <= max_length:
            parts.append(rest)
            break
        window = _fit(rest, max_length)
        boundary = _boundary(rest, window)
        if boundary is None:
            parts.append(rest[:window])
            rest = rest[window:].lstrip()
        else:
            cut, separator = boundary
            parts.append(rest[:cut].rstrip())
            rest = rest[cut + len(separator) :].lstrip()
    return parts


def append_footer(
    text: str,
    footer: str,
    *,
    max_parts: int,
    max_length: int = TELEGRAM_MESSAGE_MAX_LENGTH,
) -> str:
    """Nối `footer` (vd dòng nhắc hạn mức) vào cuối câu trả lời sao cho `split_reply` không cắt mất.

    Câu trả lời đầy đủ `max_parts` phần thì phần thân bị cắt bớt (kèm "…") để nhường chỗ cho dòng
    nhắc, thay vì để dòng nhắc rơi vào phần bị cắt. Gọi TRƯỚC khi lưu câu trả lời để lần gửi lại sau
    sự cố chia tin giống hệt.
    """
    body = text.strip()
    if not footer:
        return body

    def survives(candidate: str) -> bool:
        parts = split_reply(candidate, max_parts=max_parts, max_length=max_length)
        return bool(parts) and parts[-1].endswith(footer)

    joined = f"{body}\n\n{footer}"
    if survives(joined):
        return joined

    def cut(length: int) -> str:
        return f"{body[:length].rstrip()}{ELLIPSIS}\n\n{footer}"

    # Tìm phần thân dài nhất còn nhường đủ chỗ (càng ngắn càng dễ vừa nên tìm nhị phân được).
    low, high = 0, len(body)
    while low < high:
        middle = (low + high + 1) // 2
        if survives(cut(middle)):
            low = middle
        else:
            high = middle - 1
    return cut(low)


async def send_parts(
    client: Any,
    chat_id: int,
    parts: list[str],
    *,
    start: int,
    budget_seconds: float,
    on_part_sent: Callable[[int], Awaitable[bool]],
) -> bool:
    """Gửi các phần từ vị trí `start`, văn bản thuần, đúng thứ tự.

    429: chờ `retry_after` rồi gửi lại cùng phần đó, miễn là còn trong ngân sách; quá ngân sách
    thì ném `SendBudgetExceededError`. Sau mỗi phần gọi `on_part_sent(số phần đã gửi)`; trả `False`
    nghĩa là dòng không còn của lần claim này nên dừng. Trả `True` khi đã gửi hết.
    """
    deadline = _now() + budget_seconds
    for index in range(start, len(parts)):
        while True:
            try:
                await client.send_message(chat_id, parts[index], parse_mode=None)
                break
            except TelegramRateLimitError as exc:
                wait = max(_MIN_RETRY_AFTER_SECONDS, exc.retry_after or 0)
                if wait > deadline - _now():
                    raise SendBudgetExceededError(wait) from None
                await _wait(wait)
        if not await on_part_sent(index + 1):
            return False
    return True
