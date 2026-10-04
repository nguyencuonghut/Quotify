from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from typing import TextIO

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.integrations.telegram import (
    TelegramClient,
    TelegramConfigurationError,
    TelegramError,
)


async def me_command(
    client: TelegramClient,
    *,
    configured_username: str,
    out: TextIO,
    err: TextIO,
) -> int:
    """In `@username (id)` của bot, không bao giờ in token. Trả 2 nếu username cấu hình lệch."""
    bot = await client.get_me()
    out.write(f"@{bot.username} (id={bot.id})\n")
    if configured_username and (bot.username or "").lower() != configured_username.lower():
        err.write(
            f"CẢNH BÁO: TELEGRAM_BOT_USERNAME='{configured_username}' khác với bot thật "
            f"'@{bot.username}'. Kiểm tra lại TELEGRAM_BOT_TOKEN và TELEGRAM_BOT_USERNAME.\n",
        )
        return 2
    return 0


ALLOWED_UPDATES = ["message", "my_chat_member"]

BOT_COMMANDS = [
    {"command": "start", "description": "Bắt đầu hoặc xem trạng thái liên kết"},
    {"command": "stop", "description": "Hủy liên kết Telegram với Quotify"},
    {"command": "help", "description": "Xem hướng dẫn"},
]


async def _describe_bot_and_webhook(
    client: TelegramClient,
    settings: Settings,
    *,
    out: TextIO,
    err: TextIO,
) -> tuple[bool, str]:
    """In bot và webhook hiện tại để người chạy đối chiếu trước khi thao tác.

    Trả (khớp_username, url_webhook_hiện_tại). Không khớp thì không được thao tác tiếp.
    """
    bot = await client.get_me()
    info = await client.get_webhook_info()
    current_url = str(info.get("url") or "")
    out.write(f"Bot: @{bot.username} (id={bot.id})\n")
    out.write(f"Webhook hiện tại: {current_url or '(chưa đặt)'}\n")
    configured = settings.telegram_bot_username
    if configured and (bot.username or "").lower() != configured.lower():
        err.write(
            f"Từ chối: TELEGRAM_BOT_USERNAME='{configured}' khác với bot thật '@{bot.username}'. "
            "Có thể đang dùng nhầm token của bot khác.\n",
        )
        return False, current_url
    return True, current_url


async def set_webhook_command(
    client: TelegramClient,
    settings: Settings,
    *,
    yes: bool,
    out: TextIO,
    err: TextIO,
) -> int:
    if not settings.telegram_webhook_url or not settings.telegram_webhook_secret:
        err.write("Thiếu TELEGRAM_WEBHOOK_URL hoặc TELEGRAM_WEBHOOK_SECRET.\n")
        return 1
    matches, _current = await _describe_bot_and_webhook(client, settings, out=out, err=err)
    if not matches:
        return 2
    out.write(f"Sẽ đặt webhook thành: {settings.telegram_webhook_url}\n")
    if not yes:
        out.write("Chưa thực hiện thay đổi nào. Chạy lại với --yes để xác nhận.\n")
        return 3
    await client.set_webhook(
        url=settings.telegram_webhook_url,
        secret_token=settings.telegram_webhook_secret,
        allowed_updates=ALLOWED_UPDATES,
        drop_pending_updates=False,
    )
    out.write("Đã đặt webhook.\n")
    return 0


async def delete_webhook_command(
    client: TelegramClient,
    settings: Settings,
    *,
    yes: bool,
    out: TextIO,
    err: TextIO,
) -> int:
    matches, _current = await _describe_bot_and_webhook(client, settings, out=out, err=err)
    if not matches:
        return 2
    if not yes:
        out.write("Chưa thực hiện thay đổi nào. Chạy lại với --yes để xóa webhook.\n")
        return 3
    await client.delete_webhook(drop_pending_updates=False)
    out.write("Đã xóa webhook.\n")
    return 0


async def info_command(client: TelegramClient, *, out: TextIO, err: TextIO) -> int:
    """In trạng thái webhook (không có secret). Chỉ có giá trị sau khi đã có tin thật đi qua."""
    info = await client.get_webhook_info()
    for key in (
        "url",
        "pending_update_count",
        "last_error_date",
        "last_error_message",
        "allowed_updates",
        "ip_address",
    ):
        out.write(f"{key}: {info.get(key)}\n")
    return 0


async def commands_command(
    client: TelegramClient,
    settings: Settings,
    *,
    yes: bool,
    out: TextIO,
    err: TextIO,
) -> int:
    matches, _current = await _describe_bot_and_webhook(client, settings, out=out, err=err)
    if not matches:
        return 2
    if not yes:
        out.write("Chưa thực hiện thay đổi nào. Chạy lại với --yes để đăng ký lệnh.\n")
        return 3
    await client.set_my_commands(BOT_COMMANDS, scope={"type": "all_private_chats"})
    out.write("Đã đăng ký lệnh /start, /stop, /help cho chat riêng.\n")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Công cụ quản trị bot Telegram của Quotify.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("me", help="In username của bot (xác minh token), không in token.")
    subparsers.add_parser("info", help="In trạng thái webhook hiện tại.")
    for name, help_text in (
        ("set", "Đặt webhook theo TELEGRAM_WEBHOOK_URL và TELEGRAM_WEBHOOK_SECRET."),
        ("delete", "Xóa webhook."),
        ("commands", "Đăng ký lệnh /start, /stop, /help cho chat riêng."),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("--yes", action="store_true", help="Xác nhận thực hiện thay đổi.")
    return parser


async def _run(command: str, *, yes: bool) -> int:
    settings = get_settings()
    configure_logging(
        settings.log_level,
        log_format=settings.log_format,
        app_env=settings.app_env,
    )
    try:
        client = TelegramClient.from_settings(settings)
    except TelegramConfigurationError as exc:
        print(f"Lỗi cấu hình: {exc}", file=sys.stderr)
        return 1

    try:
        if command == "me":
            return await me_command(
                client,
                configured_username=settings.telegram_bot_username,
                out=sys.stdout,
                err=sys.stderr,
            )
        if command == "info":
            return await info_command(client, out=sys.stdout, err=sys.stderr)
        if command == "set":
            return await set_webhook_command(
                client, settings, yes=yes, out=sys.stdout, err=sys.stderr
            )
        if command == "delete":
            return await delete_webhook_command(
                client, settings, yes=yes, out=sys.stdout, err=sys.stderr
            )
        if command == "commands":
            return await commands_command(client, settings, yes=yes, out=sys.stdout, err=sys.stderr)
        return 1
    except TelegramError as exc:
        print(f"Lỗi Telegram: {exc}", file=sys.stderr)
        return 1
    finally:
        await client.aclose()


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return asyncio.run(_run(args.command, yes=bool(getattr(args, "yes", False))))
