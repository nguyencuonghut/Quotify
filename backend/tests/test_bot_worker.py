"""Cấu hình và khởi động của worker chatbot (kế hoạch 5.1, S1)."""

from __future__ import annotations

from typing import Any

import arq.worker
import pytest

import app.bot_worker as bot_worker
from app.bot_worker import BotWorkerConfig, BotWorkerSettings, drain_chat
from app.core.config import Settings


def _settings(**overrides: Any) -> Settings:
    # `_env_file=None`: không để `.env` của máy dev (có token bot thật) lọt vào test.
    return Settings(_env_file=None, **overrides)  # type: ignore[call-arg]


def test_the_worker_settings_are_self_contained_and_follow_the_plan() -> None:
    # arq đọc `cls.__dict__`: lớp con của `WorkerSettings` sẽ không thừa hưởng gì (đo ở S0(b)).
    assert BotWorkerSettings.__bases__ == (object,)
    kwargs = arq.worker.get_kwargs(BotWorkerSettings)

    assert kwargs["functions"] == [drain_chat]
    assert kwargs["queue_name"] == "quotify:bot"  # không bao giờ là hàng đợi mặc định của arq
    assert kwargs["max_tries"] == 1  # thử lại do claim và lease quyết định, không phải arq
    assert kwargs["retry_jobs"] is False  # không để lại job mồ côi khi bị hủy
    assert kwargs["keep_result"] == 0  # mặc định 3600 giây chặn `_job_id` 1 giờ sau job lỗi
    assert kwargs["health_check_interval"] <= 60  # mặc định 3600 làm worker chết trông khỏe
    # Job không được bị arq hủy khi dòng cuối của vòng drain còn đang chạy (S4 thêm ngân sách gửi).
    config = BotWorkerConfig()
    assert kwargs["job_timeout"] > config.drain_budget_seconds + config.row_timeout_seconds


def test_the_row_timeout_leaves_room_inside_the_lease() -> None:
    config = BotWorkerConfig()

    # Lease phải dài hơn thời gian tối đa của một dòng, nếu không worker khác chạy chồng.
    assert config.lease_seconds > config.row_timeout_seconds


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
    assert {"telegram_client", "chat_engine"} <= ctx.keys()
    assert "TEST-TOKEN" not in repr(ctx["telegram_client"])
    await bot_worker.shutdown(ctx)
