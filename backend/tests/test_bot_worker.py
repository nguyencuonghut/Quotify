"""Cấu hình và khởi động của worker chatbot (kế hoạch 5.1, S1)."""

from __future__ import annotations

from typing import Any

import arq.worker
import pytest
from pydantic import ValidationError

import app.bot_worker as bot_worker
from app.bot_worker import (
    BotWorkerConfig,
    BotWorkerSettings,
    cleanup_bot_updates,
    drain_chat,
    sweep_bot_updates,
)
from app.core.config import Settings
from app.integrations.telegram import (
    TelegramApiError,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRateLimitError,
)
from app.services import chat_engine
from app.services.bot_reply_sender import SendBudgetExceededError


def _settings(**overrides: Any) -> Settings:
    # `_env_file=None`: không để `.env` của máy dev (có token bot thật) lọt vào test.
    return Settings(_env_file=None, **overrides)  # type: ignore[call-arg]


def test_the_worker_settings_are_self_contained_and_follow_the_plan() -> None:
    # arq đọc `cls.__dict__`: lớp con của `WorkerSettings` sẽ không thừa hưởng gì (đo ở S0(b)).
    assert BotWorkerSettings.__bases__ == (object,)
    kwargs = arq.worker.get_kwargs(BotWorkerSettings)

    assert kwargs["functions"] == [drain_chat]
    # Cron quét đánh chuông lại và cron dọn dữ liệu cũ (S3).
    assert {job.coroutine for job in kwargs["cron_jobs"]} == {
        sweep_bot_updates,
        cleanup_bot_updates,
    }
    assert kwargs["queue_name"] == "quotify:bot"  # không bao giờ là hàng đợi mặc định của arq
    assert kwargs["max_tries"] == 1  # thử lại do claim và lease quyết định, không phải arq
    assert kwargs["retry_jobs"] is False  # không để lại job mồ côi khi bị hủy
    assert kwargs["keep_result"] == 0  # mặc định 3600 giây chặn `_job_id` 1 giờ sau job lỗi
    assert kwargs["health_check_interval"] <= 60  # mặc định 3600 làm worker chết trông khỏe
    # Job không được bị arq hủy khi dòng cuối của vòng drain còn đang chạy: engine, gửi, và tối đa
    # hai câu xin lỗi (mỗi câu một lần gọi HTTP, có timeout) quanh đó.
    config = BotWorkerConfig()
    http_timeout = Settings(_env_file=None).telegram_http_timeout_seconds  # type: ignore[call-arg]
    assert kwargs["job_timeout"] > (
        config.drain_budget_seconds
        + config.row_timeout_seconds
        + config.send_budget_seconds
        + 2 * http_timeout
    )


def test_the_cron_jobs_sweep_every_thirty_seconds_and_clean_up_once_a_day() -> None:
    jobs = {job.coroutine: job for job in arq.worker.get_kwargs(BotWorkerSettings)["cron_jobs"]}

    sweep = jobs[sweep_bot_updates]
    # Hai lần mỗi phút, lệch giây với các cron khác; không ràng buộc phút hay giờ.
    assert sweep.second == {10, 40}
    assert sweep.minute is None and sweep.hour is None
    cleanup = jobs[cleanup_bot_updates]
    assert (cleanup.hour, cleanup.minute, cleanup.second) == (3, 40, 0)  # đúng một lần mỗi ngày


def test_the_chatbot_settings_have_the_planned_defaults_and_reach_the_worker_config() -> None:
    defaults = _settings()
    assert defaults.bot_stub_delay_seconds == 0  # production không bao giờ trễ giả
    assert defaults.bot_retry_backoff_seconds == 5
    assert defaults.bot_message_ttl_seconds == 1200
    assert defaults.bot_sweep_stale_seconds == 30
    assert defaults.bot_terminal_retention_days == 30
    assert defaults.bot_reply_max_parts == 4
    assert defaults.bot_send_budget_seconds == 60
    assert defaults.bot_typing_interval_seconds == 4

    config = BotWorkerConfig.from_settings(
        _settings(
            BOT_RETRY_BACKOFF_SECONDS=7,
            BOT_MESSAGE_TTL_SECONDS=11,
            BOT_SWEEP_STALE_SECONDS=13,
            BOT_TERMINAL_RETENTION_DAYS=17,
            BOT_REPLY_MAX_PARTS=2,
            BOT_SEND_BUDGET_SECONDS=19,
            BOT_TYPING_INTERVAL_SECONDS=3,
        )
    )

    assert config.retry_backoff_seconds == 7
    assert config.message_ttl_seconds == 11
    assert config.sweep_stale_seconds == 13
    assert config.terminal_retention_days == 17  # mỗi biến vào đúng trường, không hoán đổi
    assert config.reply_max_parts == 2
    assert config.send_budget_seconds == 19
    assert config.typing_interval_seconds == 3


@pytest.mark.parametrize(
    "name",
    ["BOT_REPLY_MAX_PARTS", "BOT_SEND_BUDGET_SECONDS", "BOT_TYPING_INTERVAL_SECONDS"],
)
def test_the_send_path_settings_must_be_positive(name: str) -> None:
    # 0 làm chỉ báo "đang gõ" lặp không nghỉ, ngân sách gửi bằng 0, hay câu trả lời không phần nào.
    with pytest.raises(ValidationError):
        _settings(**{name: 0})


def test_the_row_timeout_and_the_send_budget_leave_room_inside_the_lease() -> None:
    config = BotWorkerConfig()

    # Lease phải dài hơn thời gian tối đa của một dòng (engine rồi gửi), nếu không worker khác chạy
    # chồng lên khi dòng chưa xong.
    assert config.lease_seconds > config.row_timeout_seconds + config.send_budget_seconds
    # Chỉ báo "đang gõ" phải lặp lại trước khi cái cũ hết hiệu lực (khoảng 5 giây).
    assert config.typing_interval_seconds < 5


async def test_startup_configures_logging_and_builds_the_worker_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(TELEGRAM_BOT_TOKEN="123456:TEST-TOKEN")
    configured: list[tuple[Any, ...]] = []
    monkeypatch.setattr(bot_worker, "get_settings", lambda: settings)
    monkeypatch.setattr(
        bot_worker,
        "configure_logging",
        lambda *args, **kwargs: configured.append((args, kwargs)),
    )
    marker = object()
    monkeypatch.setattr(bot_worker, "get_sessionmaker", lambda: marker)
    ctx: dict[str, Any] = {}

    await bot_worker.startup(ctx)

    assert len(configured) == 1  # worker không qua `create_app` nên phải tự bật bộ che token
    assert ctx["session_factory"] is marker
    assert ctx["bot_config"] == BotWorkerConfig.from_settings(settings)
    assert {"telegram_client", "chat_engine", "dispatcher"} <= ctx.keys()
    assert "TEST-TOKEN" not in repr(ctx["telegram_client"])
    await bot_worker.shutdown(ctx)


@pytest.mark.parametrize(
    ("app_env", "expected_sleeps"),
    [("development", [3.0]), ("production", [])],
)
async def test_the_stub_delay_is_a_dev_only_knob_and_production_ignores_it(
    monkeypatch: pytest.MonkeyPatch,
    app_env: str,
    expected_sleeps: list[float],
) -> None:
    # Biến này chỉ để thử SIGTERM giữa lượt trên dev: lỡ lọt vào `.env` production thì bị bỏ qua.
    settings = _settings(
        TELEGRAM_BOT_TOKEN="123456:TEST-TOKEN",
        BOT_STUB_DELAY_SECONDS=3,
        APP_ENV=app_env,
    )
    monkeypatch.setattr(bot_worker, "get_settings", lambda: settings)
    monkeypatch.setattr(bot_worker, "configure_logging", lambda *args, **kwargs: None)
    monkeypatch.setattr(bot_worker, "get_sessionmaker", lambda: object())
    slept: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr(chat_engine.asyncio, "sleep", fake_sleep)
    ctx: dict[str, Any] = {}
    await bot_worker.startup(ctx)

    await ctx["chat_engine"].reply(None)  # engine giả không đọc `turn`

    assert slept == expected_sleeps
    await bot_worker.shutdown(ctx)


@pytest.mark.parametrize(
    ("error", "kind"),
    [
        (TelegramForbiddenError("Forbidden: bot was blocked", error_code=403), "blocked"),
        (TelegramApiError("Bad Request", error_code=400), "rejected"),
        (TelegramApiError("Not Found", error_code=404), "rejected"),
        (TelegramApiError("Bad Gateway", error_code=502), "failed"),  # lỗi phía Telegram: thử lại
        (TelegramApiError("Internal", error_code=500), "failed"),
        (TelegramRateLimitError("Too Many Requests", error_code=429, retry_after=3), "failed"),
        (TelegramNetworkError("Không thể gọi Telegram (sendMessage): ConnectError."), "failed"),
        (TimeoutError(), "timeout"),
        (SendBudgetExceededError(30), "timeout"),
        (RuntimeError("lạ"), "failed"),
    ],
)
def test_send_errors_are_classified_into_block_reject_retry_or_timeout(
    error: Exception, kind: str
) -> None:
    assert bot_worker._send_failure_kind(error) == kind
