"""Compose của chatbot (kế hoạch 5.1, S8): `bot-worker` ở dev, production và test.

Production giữ nguyên mọi thứ đang chạy: `bot-worker` nằm sau profile `chatbot` nên `up -d` thường
không khởi động nó. Worker không tự reload code và phải nhận SIGTERM để nhả lease (KT18), nên lệnh
khởi động phải để tín hiệu tới được arq.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]

ROOT = Path(__file__).resolve().parents[2]
SETTINGS_CLASS = "app.bot_worker.BotWorkerSettings"

# Container backend-test chỉ có thư mục backend/, không có file compose ở gốc repo (CI chạy ở host).
pytestmark = pytest.mark.skipif(
    not (ROOT / "docker-compose.yml").exists(),
    reason="Không có file compose ở gốc repo (đang chạy trong container backend)",
)


def _compose(name: str) -> dict[str, Any]:
    return yaml.safe_load((ROOT / name).read_text("utf-8"))  # type: ignore[no-any-return]


def _service(name: str, service: str) -> dict[str, Any]:
    return _compose(name)["services"][service]  # type: ignore[no-any-return]


def _seconds(value: str) -> float:
    match = re.fullmatch(r"(\d+(?:\.\d+)?)(s|m)", value)
    assert match, value
    return float(match.group(1)) * (60 if match.group(2) == "m" else 1)


# --- production ---------------------------------------------------------------------------------


def test_the_production_bot_worker_sits_behind_the_chatbot_profile() -> None:
    services = _compose("docker-compose.prod.yml")["services"]

    assert services["bot-worker"]["profiles"] == ["chatbot"]
    # Mọi service khác không có profile: `up -d` thường không bao giờ khởi động bot-worker.
    assert [name for name, spec in services.items() if "profiles" in spec] == ["bot-worker"]


def test_the_production_bot_worker_restarts_and_gets_time_to_release_its_lease() -> None:
    worker = _service("docker-compose.prod.yml", "bot-worker")

    assert worker["restart"] == "unless-stopped"
    # SIGTERM huỷ job và nhả lease mất khoảng 1 giây (S0(b)); chừa dự phòng, đừng để Docker SIGKILL.
    assert _seconds(worker["stop_grace_period"]) >= 30


def test_the_production_bot_worker_receives_sigterm_because_it_is_the_main_process() -> None:
    worker = _service("docker-compose.prod.yml", "bot-worker")

    # Dạng danh sách (không qua shell) để arq là tiến trình chính và nhận được SIGTERM.
    assert worker["command"] == ["arq", SETTINGS_CLASS]


def test_the_production_bot_worker_is_healthy_only_while_arq_keeps_its_heartbeat() -> None:
    health = _service("docker-compose.prod.yml", "bot-worker")["healthcheck"]

    assert health["test"] == ["CMD", "arq", "--check", SETTINGS_CLASS]
    # Khóa sức khỏe sống `health_check_interval + 1` giây (30 + 1): kiểm đủ thường xuyên hơn thế.
    assert _seconds(health["interval"]) <= 60
    assert _seconds(health["start_period"]) >= 10
    assert health["retries"] >= 2


def test_the_production_bot_worker_is_built_and_configured_like_the_other_worker() -> None:
    services = _compose("docker-compose.prod.yml")["services"]
    worker, bot = services["worker"], services["bot-worker"]

    assert bot["build"] == worker["build"]  # cùng Dockerfile, đích `prod`
    assert bot["env_file"] == worker["env_file"] == [".env"]
    environment = bot["environment"]
    assert environment["APP_ENV"] == "production"
    assert environment["LOG_FORMAT"] == "json"
    assert environment["REDIS_URL"] == "redis://redis:6379/0"
    assert environment["POSTGRES_HOST"] == "postgres"
    assert "BOT_STUB_DELAY_SECONDS" not in environment  # độ trễ giả chỉ dành cho dev


def test_the_production_bot_worker_leaves_the_kill_switch_to_the_env_file() -> None:
    environment = _service("docker-compose.prod.yml", "bot-worker")["environment"]

    # Cố định `CHATBOT_ENABLED` ở đây sẽ làm công tắc tắt khẩn cấp trong `.env` mất tác dụng.
    assert not {"CHATBOT_ENABLED", "CHATBOT_PILOT_USER_EMAILS", "TELEGRAM_ENABLED"} & set(
        environment
    )


def test_the_production_bot_worker_connects_to_the_redis_service_arq_reads() -> None:
    environment = _service("docker-compose.prod.yml", "bot-worker")["environment"]

    # arq đọc REDIS_HOST/REDIS_PORT (không đọc REDIS_URL): nếu đặt thì phải trỏ vào service `redis`.
    assert environment.get("REDIS_HOST", "redis") == "redis"
    assert str(environment.get("REDIS_PORT", "6379")) == "6379"


def test_the_production_bot_worker_waits_for_postgres_and_redis() -> None:
    depends = _service("docker-compose.prod.yml", "bot-worker")["depends_on"]

    assert depends["postgres"]["condition"] == "service_healthy"
    assert depends["redis"]["condition"] == "service_healthy"


# --- dev ----------------------------------------------------------------------------------------


def test_the_dev_bot_worker_is_in_the_telegram_profile_and_reports_its_health() -> None:
    worker = _service("docker-compose.yml", "bot-worker")

    assert worker["profiles"] == ["telegram"]
    assert "exec uv run arq " + SETTINGS_CLASS in worker["command"]  # `exec` để SIGTERM tới arq
    assert _seconds(worker["stop_grace_period"]) >= 30
    assert worker["healthcheck"]["test"][-3:] == ["arq", "--check", SETTINGS_CLASS]
    assert worker["depends_on"]["redis"]["condition"] == "service_healthy"


@pytest.mark.parametrize("service", ["backend", "telegram-poller", "bot-worker"])
def test_every_dev_service_that_looks_at_the_chatbot_flag_gets_the_same_default(
    service: str,
) -> None:
    environment = _service("docker-compose.yml", service)["environment"]

    # Backend cần cờ cho webhook và `/metrics` (`quotify_bot_enabled`); mặc định tắt như mọi nơi.
    assert environment["CHATBOT_ENABLED"] == "${CHATBOT_ENABLED:-false}"


@pytest.mark.parametrize("service", ["backend", "telegram-poller", "bot-worker"])
def test_the_dev_services_that_enforce_or_show_the_daily_allowance_get_the_same_limits(
    service: str,
) -> None:
    environment = _service("docker-compose.yml", service)["environment"]

    # Backend và poller (dev dùng polling) trả lời `/limit`, worker chặn thật: cùng một biến shell
    # cho cả ba, mặc định như `.env.example`, để thử hạn mức bằng `BOT_DAILY_TURN_LIMIT=2 ... up`.
    assert environment["BOT_DAILY_TURN_LIMIT"] == "${BOT_DAILY_TURN_LIMIT:-20}"
    assert environment["BOT_DAILY_FILE_LIMIT"] == "${BOT_DAILY_FILE_LIMIT:-5}"
    assert (
        environment["BOT_QUOTA_WARN_REMAINING_PERCENT"] == "${BOT_QUOTA_WARN_REMAINING_PERCENT:-20}"
    )


@pytest.mark.parametrize("service", ["backend", "telegram-poller"])
def test_the_services_that_decide_who_may_chat_get_the_pilot_list(service: str) -> None:
    environment = _service("docker-compose.yml", service)["environment"]

    assert environment["CHATBOT_PILOT_USER_EMAILS"] == "${CHATBOT_PILOT_USER_EMAILS:-}"


# --- test ---------------------------------------------------------------------------------------


def test_the_test_bot_worker_talks_only_to_the_fake_telegram_and_is_opt_in() -> None:
    services = _compose("docker-compose.test.yml")["services"]
    worker = services["bot-worker-test"]

    assert worker["profiles"] == ["chatbot"]  # `make docker-test` mặc định không chạy nó
    environment = worker["environment"]
    assert environment["TELEGRAM_API_BASE_URL"] == "http://fake-telegram:8081"
    assert environment["CHATBOT_ENABLED"] == "true"
    assert environment["BOT_STUB_DELAY_SECONDS"] == "0"  # không thừa hưởng độ trễ giả của .env dev
    assert environment["TELEGRAM_ENABLED"] == "true"
    assert (
        environment["TELEGRAM_BOT_TOKEN"] == "e2e-fake-bot-token"
    )  # không phải token dev trong .env
    assert environment["REDIS_URL"] == "redis://redis-test:6379/0"
    assert (
        environment["REDIS_HOST"] == "redis-test"
    )  # arq và chuông đọc REDIS_HOST, không đọc REDIS_URL
    assert "app_test" in environment["DATABASE_URL"]
    assert worker["depends_on"]["fake-telegram"]["condition"] == "service_healthy"
    # backend-e2e chạy migration trên app_test; thiếu nó thì hộp thư chưa có bảng và cron quét lỗi.
    assert worker["depends_on"]["backend-e2e"]["condition"] == "service_healthy"
    assert [n for n, spec in services.items() if "profiles" in spec] == ["bot-worker-test"]


def test_the_e2e_backend_ignores_the_dev_chatbot_flag_unless_asked() -> None:
    environment = _service("docker-compose.test.yml", "backend-e2e")["environment"]

    # .env của dev có thể bật chatbot; E2E không có worker nên tin chỉ xếp hàng và làm lệch kết quả.
    assert environment["CHATBOT_ENABLED"] == "${E2E_CHATBOT_ENABLED:-false}"
    # Cùng Redis với bot-worker-test, nếu không chuông rung vào Redis của dev (`redis` trong .env).
    assert environment["REDIS_HOST"] == "redis-test"


# --- chung --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    ["docker-compose.yml", "docker-compose.prod.yml", "docker-compose.test.yml"],
)
def test_no_chatbot_variable_is_required_by_compose(name: str) -> None:
    # `${VAR:?}` làm `docker compose config` hỏng khi thiếu biến (bài học production-readiness).
    text = (ROOT / name).read_text("utf-8")

    assert not re.search(r"\$\{(?:CHATBOT|BOT)_[A-Z_]+:\?", text)
