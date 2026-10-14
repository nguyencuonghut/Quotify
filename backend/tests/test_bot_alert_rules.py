"""Luật cảnh báo của chatbot (kế hoạch 5.1, S7): tên số đo trong từng luật phải khớp mã thật."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from app.core.bot_metrics import BotMetrics, BotSnapshot, set_active_bot_metrics

ROOT = Path(__file__).resolve().parents[2]
RULES_FILE = ROOT / "docker" / "observability" / "alert_rules.yml"
EXPECTED_RULES = {"ChatbotQueueStuck", "ChatbotUpdatesFailing", "ChatbotMetricsUnavailable"}


def exported_metric_names() -> set[str]:
    """Mọi tên số đo mà collector xuất khi có đủ dữ liệu."""
    from prometheus_client import generate_latest

    metrics = BotMetrics(lambda: None, ttl_seconds=0)  # type: ignore[arg-type, return-value]
    metrics.ok = True
    metrics.snapshot = BotSnapshot(
        enabled=True,
        updates={"queued": 1, "processing": 1, "replied": 1, "failed": 1, "dropped": 1},
        queued_oldest_age_seconds=1.0,
        quota_denied=1,
        recent_failures=1,
    )
    set_active_bot_metrics(metrics)
    try:
        text = generate_latest().decode()
    finally:
        set_active_bot_metrics(None)
    return set(re.findall(r"^(quotify_bot_[a-z_]+)", text, flags=re.MULTILINE))


def load_rules() -> list[dict[str, object]]:
    document = yaml.safe_load(RULES_FILE.read_text("utf-8"))
    [group] = [g for g in document["groups"] if g["name"] == "quotify-chatbot"]
    return list(group["rules"])


def test_the_chatbot_has_its_own_alert_group_with_the_planned_rules() -> None:
    assert {rule["alert"] for rule in load_rules()} == EXPECTED_RULES


def test_every_metric_used_by_a_chatbot_rule_is_really_exported() -> None:
    exported = exported_metric_names()

    for rule in load_rules():
        used = set(re.findall(r"quotify_bot_[a-z_]+", str(rule["expr"])))
        assert used, rule["alert"]
        assert used <= exported, f"{rule['alert']} dùng số đo không tồn tại: {used - exported}"
        labels = rule["labels"]
        assert isinstance(labels, dict) and labels["severity"] in {"warning", "critical"}
        assert rule["for"]
        annotations = rule["annotations"]
        assert (
            isinstance(annotations, dict) and annotations["summary"] and annotations["description"]
        )


def test_the_collector_exports_exactly_the_metrics_the_plan_names() -> None:
    assert exported_metric_names() == {
        "quotify_bot_metrics_up",
        "quotify_bot_enabled",
        "quotify_bot_updates",
        "quotify_bot_queued_oldest_age_seconds",
        "quotify_bot_quota_denied",
        "quotify_bot_recent_failures",
    }


def _rule(name: str) -> dict[str, object]:
    [rule] = [r for r in load_rules() if r["alert"] == name]
    return rule


def test_the_queue_alert_fires_after_120_seconds_held_for_5_minutes() -> None:
    rule = _rule("ChatbotQueueStuck")

    assert rule["expr"] == "quotify_bot_queued_oldest_age_seconds > 120"
    assert rule["for"] == "5m"
    assert rule["labels"] == {"severity": "warning"}


def test_the_failure_alert_watches_the_30_minute_failure_gauge_not_a_24_hour_delta() -> None:
    rule = _rule("ChatbotUpdatesFailing")

    # Gauge 24 giờ vừa tăng vừa giảm khi dòng cũ rơi khỏi cửa sổ nên `delta` bỏ sót hay báo trễ lỗi
    # mới; gauge 30 phút chỉ phụ thuộc dòng lỗi vừa kết thúc.
    assert rule["expr"] == "quotify_bot_recent_failures > 0"
    assert rule["for"] == "1m"
    assert rule["labels"] == {"severity": "warning"}


def test_the_unavailable_alert_watches_the_up_gauge() -> None:
    rule = _rule("ChatbotMetricsUnavailable")

    assert rule["expr"] == "quotify_bot_metrics_up == 0"
    assert rule["for"] == "10m"
    assert rule["labels"] == {"severity": "warning"}


def test_the_chatbot_rules_use_the_new_prefix_and_leave_the_old_groups_alone() -> None:
    document = yaml.safe_load(RULES_FILE.read_text("utf-8"))
    groups = {group["name"] for group in document["groups"]}

    # Hai nhóm cũ (còn tên `fastapivue_*`, nợ RR-19) không bị sửa lan.
    assert {"fastapivue-production-readiness", "quotify-price-alerts"} <= groups
    for rule in load_rules():
        assert "fastapivue" not in str(rule["expr"])


@pytest.mark.skipif(shutil.which("promtool") is None, reason="Máy này không có promtool")
def test_the_rules_pass_the_promtool_unit_tests() -> None:
    # Mô phỏng chuỗi số đo để chứng minh luật nổ đúng lúc và không nổ oan (cú pháp đúng chưa đủ).
    result = subprocess.run(  # noqa: S603
        ["promtool", "test", "rules", "docker/observability/tests/chatbot_alert_rules_test.yml"],  # noqa: S607
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
