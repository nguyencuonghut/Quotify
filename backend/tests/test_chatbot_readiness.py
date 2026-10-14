"""Tài sản vận hành của chatbot có đủ trong repo (kế hoạch 5.1, S8)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "compliance" / "check-chatbot-readiness.sh"
RUNBOOK = ROOT / "docs" / "runbooks" / "deploy-vps-production.md"

pytestmark = pytest.mark.skipif(
    not SCRIPT.parent.exists(),
    reason="Không có thư mục scripts ở gốc repo (đang chạy trong container backend)",
)


def run_check(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["bash", str(SCRIPT)],  # noqa: S607
        env={"ROOT_DIR": str(root), "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        check=False,
    )


def _runbook_section_16() -> str:
    text = RUNBOOK.read_text("utf-8")
    return text[text.index("## 16. ") :]


def test_the_repository_passes_the_chatbot_compliance_check() -> None:
    result = run_check(ROOT)

    assert result.returncode == 0, result.stderr


def test_the_compliance_check_names_what_is_missing(tmp_path: Path) -> None:
    result = run_check(tmp_path)

    assert result.returncode == 1
    for item in (
        "mục 16 của runbook",
        "service bot-worker trong compose production",
        "profile chatbot của bot-worker",
        "healthcheck của bot-worker",
        "CHATBOT_ENABLED",
        "CHATBOT_PILOT_USER_EMAILS",
        "BOT_MAX_ATTEMPTS",
        "migration của hộp thư bot",
        "luật cảnh báo hàng đợi kẹt",
        "luật cảnh báo lỗi liên tiếp",
        "luật cảnh báo mất số đo",
    ):
        assert item in result.stderr, item


ASSETS = (
    "docs/runbooks/deploy-vps-production.md",
    "docker-compose.prod.yml",
    ".env.production.example",
    "docker/observability/alert_rules.yml",
    "backend/alembic/versions/20261013_1000_create_bot_updates.py",
)


def _copy_assets(target: Path) -> Path:
    for relative in ASSETS:
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text((ROOT / relative).read_text("utf-8"), "utf-8")
    return target


def _edit(root: Path, relative: str, old: str, new: str) -> None:
    path = root / relative
    text = path.read_text("utf-8")
    assert text.count(old) == 1, old
    path.write_text(text.replace(old, new), "utf-8")


def test_a_copy_of_the_assets_passes_so_the_mutations_below_mean_something(
    tmp_path: Path,
) -> None:
    assert run_check(_copy_assets(tmp_path)).returncode == 0


BOT_WORKER_PROFILE = "    profiles:\n      - chatbot\n"
BOT_WORKER_HEALTHCHECK = '      test: ["CMD", "arq", "--check", "app.bot_worker.BotWorkerSettings"]'


@pytest.mark.parametrize(
    ("label", "edits"),
    [
        (
            "profile chatbot của bot-worker",
            # Chuyển profile sang service `worker`: bot-worker sẽ khởi động ở `up -d` thường.
            [
                (BOT_WORKER_PROFILE, ""),
                ("  worker:\n    build:", "  worker:\n" + BOT_WORKER_PROFILE + "    build:"),
            ],
        ),
        (
            "healthcheck của bot-worker",
            # Một dòng đã bị bỏ dấu (comment) không còn là healthcheck.
            [(BOT_WORKER_HEALTHCHECK, "      # " + BOT_WORKER_HEALTHCHECK.strip())],
        ),
        ("restart của bot-worker", [("    restart: unless-stopped\n", "")]),
        ("stop_grace_period của bot-worker", [("    stop_grace_period: 30s\n", "")]),
    ],
)
def test_the_compose_checks_look_inside_the_bot_worker_service_only(
    tmp_path: Path, label: str, edits: list[tuple[str, str]]
) -> None:
    root = _copy_assets(tmp_path)
    for old, new in edits:
        _edit(root, "docker-compose.prod.yml", old, new)

    result = run_check(root)

    assert result.returncode == 1
    assert label in result.stderr


def test_the_check_looks_for_the_runbook_notes_inside_section_16_only(tmp_path: Path) -> None:
    # Từ khóa nằm ở mục khác của runbook không được tính là đã có hướng dẫn cho chatbot.
    runbook = tmp_path / "docs" / "runbooks" / "deploy-vps-production.md"
    runbook.parent.mkdir(parents=True)
    runbook.write_text(
        "## 12. Telegram\n\nCHATBOT_ENABLED=false --profile chatbot stop bot-worker "
        "CHATBOT_PILOT_USER_EMAILS --max-connections\n\n## 16. Chatbot\n\nChưa viết gì.\n",
        "utf-8",
    )

    result = run_check(tmp_path)

    assert "mục 16 của runbook" not in result.stderr  # tiêu đề có
    assert "công tắc tắt khẩn cấp trong mục 16" in result.stderr
    assert "cách bật bot-worker trong mục 16" in result.stderr
    assert "cách đặt danh sách pilot trong mục 16" in result.stderr
    assert "đăng ký lại webhook với max_connections trong mục 16" in result.stderr


def test_the_production_readiness_script_runs_the_chatbot_check_and_profile() -> None:
    script = (ROOT / "scripts/compliance/check-production-readiness.sh").read_text("utf-8")

    assert "check-chatbot-readiness.sh" in script
    # `config` thường bỏ qua service có profile: không nêu profile thì lỗi trong bot-worker sẽ lọt.
    assert "--profile chatbot" in script


def test_runbook_section_16_covers_switching_on_off_watching_and_the_webhook() -> None:
    section = _runbook_section_16()

    for needle in (
        "--profile chatbot",
        "CHATBOT_ENABLED=false",
        "stop bot-worker",
        "CHATBOT_PILOT_USER_EMAILS",
        "--max-connections",
        "quotify_bot_queued_oldest_age_seconds",
        "ChatbotQueueStuck",
        "arq --check",
        "docker compose",
    ):
        assert needle in section, needle


def _build_lines(text: str) -> list[str]:
    return [
        line
        for line in text.splitlines()
        if line.startswith("docker compose -f docker-compose.prod.yml build ")
    ]


def test_the_reusable_build_commands_name_the_bot_worker_too() -> None:
    # Cùng Dockerfile và target với `worker` nhưng tên image khác: bỏ sót nghĩa là chạy image cũ.
    runbook = RUNBOOK.read_text("utf-8")
    sections = {
        "mục 3": runbook[runbook.index("## 3. ") : runbook.index("## 4. ")],
        "mục 9.4": runbook[runbook.index("### 9.4 ") : runbook.index("### 9.5 ")],
        "mục 15.6": runbook[runbook.index("### 15.6 ") : runbook.index("## 16. ")],
    }

    for name, section in sections.items():
        lines = _build_lines(section)
        assert lines, name
        assert all("bot-worker" in line for line in lines), name


def test_the_recreate_steps_warn_that_naming_a_profile_service_starts_it() -> None:
    runbook = RUNBOOK.read_text("utf-8")
    step_9_7 = runbook[runbook.index("### 9.7 ") : runbook.index("### 9.8 ")]
    quick = runbook[runbook.index("### 15.6 ") : runbook.index("## 16. ")]

    assert "--profile chatbot up -d bot-worker" in step_9_7
    assert "KHÔNG chạy" in quick  # dòng recreate bot-worker chỉ dành cho lúc chatbot đang chạy


def test_the_telegram_kill_switch_also_stops_the_bot_worker() -> None:
    # Worker đọc cờ lúc khởi động: tắt Telegram ở backend mà không dừng nó thì nó vẫn gửi tin.
    runbook = RUNBOOK.read_text("utf-8")
    section = runbook[runbook.index("### 12.5 ") : runbook.index("### 12.6 ")]

    assert "stop bot-worker" in section


def test_section_16_covers_a_hung_worker_the_backend_settings_and_the_purge() -> None:
    section = _runbook_section_16()

    assert (
        "**treo**" in section and "restart bot-worker" in section
    )  # restart policy không xử lý treo
    assert "BOT_QUEUE_NAME" in section and "BOT_MAX_PENDING_PER_CHAT" in section  # backend đọc
    assert "operator_purge" in section  # dòng còn mở giữ nội dung tin cho tới khi bị dọn
