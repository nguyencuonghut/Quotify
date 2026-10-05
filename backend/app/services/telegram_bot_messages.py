"""Bộ tin nhắn tiếng Việt của bot Telegram (HTML). Dữ liệu động phải qua `escape_html`."""

from __future__ import annotations

from app.integrations.telegram import escape_html

HELP_TEXT = (
    "Các lệnh:\n"
    "/start — Bắt đầu hoặc xem trạng thái liên kết\n"
    "/stop — Hủy liên kết Telegram với Quotify\n"
    "/help — Xem hướng dẫn này\n"
    "\n"
    "Bot này gửi thông báo biến động giá. Để liên kết, mở trang Hồ sơ trên Quotify."
)

UNKNOWN_TEXT = "Tôi chưa hiểu yêu cầu này. Gõ /help để xem hướng dẫn."

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
