from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime

from app.core.request_id import request_id_context

# Token bot Telegram nằm trong URL `https://api.telegram.org/bot<id>:<chuỗi>/METHOD` nên mọi
# dòng log URL (httpx, traceback) đều có thể làm lộ token. Che ở cấp Formatter để phủ cả
# `message` lẫn traceback, kể cả khi ai đó hạ mức log của httpx xuống INFO.
_TELEGRAM_URL_TOKEN = re.compile(r"bot\d{6,}:[A-Za-z0-9_-]{20,}")
_TELEGRAM_BARE_TOKEN = re.compile(r"(?<![\w:])\d{6,}:[A-Za-z0-9_-]{30,}(?![\w-])")


def redact_secrets(text: str) -> str:
    redacted = _TELEGRAM_URL_TOKEN.sub("bot<redacted>", text)
    return _TELEGRAM_BARE_TOKEN.sub("<redacted-telegram-token>", redacted)


class PlainLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact_secrets(super().format(record))


class JsonLogFormatter(logging.Formatter):
    def __init__(self, *, app_env: str) -> None:
        super().__init__()
        self.app_env = app_env

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_secrets(record.getMessage()),
            "environment": self.app_env,
            "request_id": request_id_context.get() or None,
        }

        if record.exc_info:
            payload["exception"] = redact_secrets(self.formatException(record.exc_info))

        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str, *, log_format: str, app_env: str) -> None:
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level.upper())

    handler = logging.StreamHandler()
    if log_format == "json":
        handler.setFormatter(JsonLogFormatter(app_env=app_env))
    else:
        handler.setFormatter(PlainLogFormatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))

    root_logger.addHandler(handler)

    # httpx ghi cả URL của mỗi request ở mức INFO (kể cả token bot Telegram trong path).
    # Lớp scrub ở Formatter là chốt chặn chính, hạ mức log là lớp phòng thủ thứ hai.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
