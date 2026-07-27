from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from app.core.request_id import request_id_context


class JsonLogFormatter(logging.Formatter):
    def __init__(self, *, app_env: str) -> None:
        super().__init__()
        self.app_env = app_env

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "environment": self.app_env,
            "request_id": request_id_context.get() or None,
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str, *, log_format: str, app_env: str) -> None:
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level.upper())

    handler = logging.StreamHandler()
    if log_format == "json":
        handler.setFormatter(JsonLogFormatter(app_env=app_env))
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))

    root_logger.addHandler(handler)
