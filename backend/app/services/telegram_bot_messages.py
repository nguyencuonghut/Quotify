"""Bộ tin nhắn tiếng Việt của bot Telegram (HTML). Dữ liệu động phải qua `escape_html`."""

from __future__ import annotations

from app.integrations.telegram import escape_html
from app.services.usage_gate import (
    BUSINESS_TIMEZONE,
    FILE_KINDS,
    QuotaDecision,
    QuotaSummary,
)

HELP_TEXT = (
    "Các lệnh:\n"
    "/start — Bắt đầu hoặc xem trạng thái liên kết\n"
    "/stop — Hủy liên kết Telegram với Quotify\n"
    "/help — Xem hướng dẫn này\n"
    "\n"
    "Bot này gửi thông báo biến động giá. Để liên kết, mở trang Hồ sơ trên Quotify."
)

UNKNOWN_TEXT = "Tôi chưa hiểu yêu cầu này. Gõ /help để xem hướng dẫn."

# Ảnh, tài liệu, giọng nói, sticker gửi cho chatbot khi chưa có tính năng đọc tệp (5.1, S5).
NON_TEXT_TEXT = "Hiện tôi chỉ đọc được tin nhắn văn bản. Bạn vui lòng gõ câu hỏi bằng chữ nhé."

# Gửi khi chat đã có quá nhiều tin đang chờ xử lý: tin mới không được ghi vào hộp thư (5.1, S5).
PENDING_LIMIT_TEXT = (
    "Bạn đang gửi nhiều câu hỏi cùng lúc nên tôi chưa kịp xử lý hết. "
    "Vui lòng đợi tôi trả lời các câu trước rồi hỏi tiếp."
)

# Câu trả lời cố định của `StubChatEngine` (đường ống chatbot chưa nối LLM, kế hoạch 5.1).
STUB_REPLY_TEXT = "Chatbot Quotify đang được cài đặt. Tính năng trả lời sẽ sớm có mặt."

# Gửi khi một tin quá cũ (sau sự cố dài) bị loại thay vì trả lời một câu hỏi đã cũ (mục 4.5).
EXPIRED_MESSAGE_TEXT = (
    "Hệ thống vừa gián đoạn nên chưa xử lý được tin nhắn của bạn. Vui lòng gửi lại câu hỏi."
)

# Gửi khi một tin đã hết số lần thử mà vẫn chưa được trả lời (kế hoạch 5.1, mục 4.5).
LOST_MESSAGE_TEXT = (
    "Xin lỗi, tôi chưa xử lý được tin nhắn trước đó của bạn. Vui lòng gửi lại câu hỏi."
)


def _resets_text(decision: QuotaDecision) -> str:
    when = decision.resets_at.astimezone(BUSINESS_TIMEZONE).strftime("%H:%M ngày %d/%m/%Y")
    return f"Hạn mức được làm mới lúc {when} (giờ Việt Nam)."


def quota_denied_text(decision: QuotaDecision) -> str:
    """Câu từ chối khi hết hạn mức (5.1, S10). Số liệu là số thật của cổng, không do engine sinh."""
    if decision.reason == "files":
        what = "lượt gửi ảnh hoặc PDF"
        advice = "Bạn vẫn có thể hỏi bằng chữ."
    else:
        what = "lượt hỏi"
        advice = "Cần thêm lượt, vui lòng liên hệ quản trị viên."
    return (
        f"Bạn đã dùng hết {decision.used}/{decision.limit} {what} hôm nay. "
        f"{_resets_text(decision)} {advice}"
    )


def _is_near_limit(used_before: int, limit: int, warn_percent: int) -> bool:
    """Sau lượt đang trả lời, phần còn lại không quá `warn_percent` phần trăm hạn mức."""
    remaining = limit - (used_before + 1)
    return limit > 0 and remaining * 100 <= warn_percent * limit


def quota_reminder_text(decision: QuotaDecision, kind: str, *, warn_percent: int) -> str | None:
    """Dòng nhắc cuối câu trả lời khi sắp hết hạn mức; do cổng thêm, không do engine sinh.

    Tính SAU lượt đang trả lời (nó sẽ được tính ngay khi câu trả lời được lưu). Lượt dùng tệp chỉ
    được nhắc khi chính tin này là tin có tệp.
    """
    if warn_percent <= 0:
        return None
    lines: list[str] = []
    if _is_near_limit(decision.turns_used, decision.turns_limit, warn_percent):
        remaining = max(0, decision.turns_limit - decision.turns_used - 1)
        lines.append(
            f"Bạn đã dùng hết {decision.turns_limit}/{decision.turns_limit} lượt hôm nay."
            if remaining == 0
            else f"Còn {remaining}/{decision.turns_limit} lượt hôm nay."
        )
    if kind in FILE_KINDS and _is_near_limit(
        decision.files_used, decision.files_limit, warn_percent
    ):
        remaining = max(0, decision.files_limit - decision.files_used - 1)
        lines.append(
            f"Bạn đã dùng hết {decision.files_limit}/{decision.files_limit} lượt gửi ảnh hoặc "
            "PDF hôm nay."
            if remaining == 0
            else f"Còn {remaining}/{decision.files_limit} lượt gửi ảnh hoặc PDF hôm nay."
        )
    return " ".join(lines) or None


def _usage_line(label: str, used: int, limit: int) -> str:
    if limit == 0:
        return f"• {label}: đã dùng {used}, không giới hạn"
    return f"• {label}: đã dùng {used}/{limit}, còn {max(0, limit - used)}"


def limit_summary_text(summary: QuotaSummary) -> str:
    """Trả lời lệnh `/limit`: lượt đã dùng, còn lại và giờ làm mới (không có token)."""
    when = summary.resets_at.astimezone(BUSINESS_TIMEZONE).strftime("%H:%M ngày %d/%m/%Y")
    return (
        "Hạn mức hôm nay (giờ Việt Nam):\n"
        f"{_usage_line('Lượt hỏi', summary.turns_used, summary.turns_limit)}\n"
        f"{_usage_line('Lượt gửi ảnh hoặc PDF', summary.files_used, summary.files_limit)}\n"
        f"Hạn mức được làm mới lúc {when}."
    )


SYSTEM_ERROR_TEXT = "Hệ thống tạm thời chưa xử lý được yêu cầu. Vui lòng thử lại sau."

START_TEXT = (
    "Xin chào! Đây là bot thông báo biến động giá của Quotify. Để nhận thông báo, hãy mở trang "
    'Hồ sơ trên Quotify, bấm "Liên kết Telegram" rồi mở đường dẫn liên kết được tạo.'
)

INVALID_LINK_TEXT = (
    "Đường dẫn liên kết không hợp lệ hoặc đã hết hạn. "
    "Hãy tạo đường dẫn mới trong trang Hồ sơ trên Quotify."
)

TELEGRAM_IN_USE_TEXT = (
    "Tài khoản Telegram này đang liên kết với một tài khoản Quotify khác. "
    "Hãy gõ /stop ở đây hoặc hủy liên kết ở tài khoản đó trước, rồi tạo đường dẫn mới."
)

USER_INACTIVE_TEXT = "Tài khoản Quotify của bạn hiện không hoạt động nên không thể liên kết."

REPLACED_TEXT = (
    "Liên kết Telegram này đã được thay thế bằng một tài khoản Telegram khác. "
    "Bạn sẽ không nhận thông báo ở đây nữa."
)


STOPPED_TEXT = (
    "Đã hủy liên kết. Bạn sẽ không nhận thông báo nữa. "
    "Để liên kết lại, hãy tạo đường dẫn mới trong trang Hồ sơ trên Quotify."
)

NOT_LINKED_TEXT = "Tài khoản Telegram này chưa được liên kết."


def linked_text(full_name: str) -> str:
    return (
        f"✅ Đã liên kết với tài khoản <b>{escape_html(full_name)}</b>. "
        "Bạn sẽ nhận thông báo biến động giá tại đây. Gõ /stop để hủy liên kết."
    )


def reactivated_text(full_name: str) -> str:
    return f"✅ Đã kích hoạt lại liên kết với <b>{escape_html(full_name)}</b>."


def already_linked_text(full_name: str) -> str:
    return (
        f"Tài khoản Telegram này đã liên kết với <b>{escape_html(full_name)}</b>. "
        "Gõ /help để xem hướng dẫn."
    )


# Lời nhắn khi bấm nút duyệt giá bất thường: văn bản thuần (answerCallbackQuery không có HTML).
ACCEPTED_TOAST = "Đã xác nhận giá đúng."
REJECTED_TOAST = "Đã đánh dấu nhập sai."
INVALID_CARD_TEXT = "Thẻ này không còn hợp lệ."
NO_REVIEW_PERMISSION_TEXT = "Bạn không có quyền duyệt giá bất thường."
BUSY_TEXT = "Hệ thống đang bận, vui lòng bấm lại sau ít giây."
TOO_FAST_TEXT = "Bạn bấm quá nhanh, vui lòng thử lại sau."


def already_reviewed_text(reviewer_name: str | None) -> str:
    return f"Đã được xử lý bởi {reviewer_name}." if reviewer_name else "Đã được xử lý."
