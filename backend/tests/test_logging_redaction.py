from __future__ import annotations

import io
import json
import logging
from collections.abc import Iterator

import httpx
import pytest

from app.core.logging import configure_logging
from app.integrations.telegram import TelegramClient

FAKE_TOKEN = "123456789:AAFakeTokenFakeTokenFakeTokenFake12"


@pytest.fixture
def captured_logs() -> Iterator[io.StringIO]:
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    saved_levels = {name: logging.getLogger(name).level for name in ("httpx", "httpcore")}

    stream = io.StringIO()
    yield stream

    root.handlers[:] = saved_handlers
    root.setLevel(saved_level)
    for name, level in saved_levels.items():
        logging.getLogger(name).setLevel(level)


def _configure(stream: io.StringIO, *, log_format: str) -> None:
    configure_logging("INFO", log_format=log_format, app_env="test")
    handler = logging.getLogger().handlers[0]
    assert isinstance(handler, logging.StreamHandler)
    handler.setStream(stream)


@pytest.mark.parametrize("log_format", ["json", "plain"])
def test_log_messages_never_contain_the_bot_token(
    captured_logs: io.StringIO,
    log_format: str,
) -> None:
    _configure(captured_logs, log_format=log_format)

    logging.getLogger("app.test").info(
        "HTTP Request: POST https://api.telegram.org/bot%s/getMe", FAKE_TOKEN
    )

    output = captured_logs.getvalue()
    assert FAKE_TOKEN not in output
    assert "bot<redacted>" in output


@pytest.mark.parametrize("log_format", ["json", "plain"])
def test_exception_tracebacks_are_redacted(
    captured_logs: io.StringIO,
    log_format: str,
) -> None:
    _configure(captured_logs, log_format=log_format)

    try:
        raise RuntimeError(f"failed https://api.telegram.org/bot{FAKE_TOKEN}/sendMessage")
    except RuntimeError:
        logging.getLogger("app.test").exception("send failed")

    output = captured_logs.getvalue()
    assert FAKE_TOKEN not in output
    if log_format == "json":
        payload = json.loads(output.strip().splitlines()[-1])
        assert "bot<redacted>" in payload["exception"]


def test_bare_token_without_the_bot_prefix_is_redacted(captured_logs: io.StringIO) -> None:
    _configure(captured_logs, log_format="plain")

    logging.getLogger("app.test").info("token=%s", FAKE_TOKEN)

    assert FAKE_TOKEN not in captured_logs.getvalue()


def test_httpx_request_lines_are_quiet_by_default(captured_logs: io.StringIO) -> None:
    _configure(captured_logs, log_format="json")

    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING


@pytest.mark.asyncio
async def test_httpx_info_log_of_a_real_client_call_is_scrubbed(
    captured_logs: io.StringIO,
) -> None:
    _configure(captured_logs, log_format="json")
    # Giả lập ai đó hạ mức log xuống INFO: lớp scrub ở Formatter vẫn phải che token.
    logging.getLogger("httpx").setLevel(logging.INFO)
    http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={"ok": True, "result": {"id": 1, "username": "quotify_dev_bot"}},
            )
        )
    )
    client = TelegramClient(token=FAKE_TOKEN, http_client=http_client)

    await client.get_me()
    await http_client.aclose()

    output = captured_logs.getvalue()
    assert "HTTP Request" in output
    assert FAKE_TOKEN not in output
