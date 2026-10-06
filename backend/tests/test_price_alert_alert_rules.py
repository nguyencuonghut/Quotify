"""Luật cảnh báo và kiểm tra tuân thủ của thông báo giá (1C, Slice 7)."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml

from app.core.price_alert_metrics import (
    PriceAlertMetrics,
    PriceAlertSnapshot,
    set_active_metrics,
)

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "compliance" / "check-price-alert-readiness.sh"


def exported_metric_names() -> set[str]:
    """Mọi tên số đo mà collector xuất khi có đủ dữ liệu."""
    from prometheus_client import generate_latest

    metrics = PriceAlertMetrics(lambda: None, ttl_seconds=0)  # type: ignore[arg-type, return-value]
    metrics.ok = True
    metrics.snapshot = PriceAlertSnapshot(
        enabled=True,
        scan_lag_seconds=1.0,
        watermark_lag_seconds=1.0,
        messages={"pending": 1, "sending": 1, "failed": 1},
        oldest_pending_age_seconds=1.0,
        anomalies_pending=1,
    )
    set_active_metrics(metrics)
    try:
        text = generate_latest().decode()
    finally:
        set_active_metrics(None)
    return set(re.findall(r"^(quotify_price_alert_[a-z_]+)", text, flags=re.MULTILINE))


def load_rules() -> list[dict[str, str]]:
    document = yaml.safe_load((ROOT / "docker/observability/alert_rules.yml").read_text("utf-8"))
    [group] = [g for g in document["groups"] if g["name"] == "quotify-price-alerts"]
    return list(group["rules"])


def test_every_metric_used_by_an_alert_rule_is_really_exported() -> None:
    exported = exported_metric_names()
    rules = load_rules()

    assert {rule["alert"] for rule in rules} == {
        "PriceAlertScanStale",
        "PriceAlertMessagesStuck",
        "PriceAlertSendFailures",
        "PriceAlertMetricsUnavailable",
    }
    for rule in rules:
        used = set(re.findall(r"quotify_price_alert_[a-z_]+", rule["expr"]))
        assert used, rule["alert"]
        assert used <= exported, f"{rule['alert']} dùng số đo không tồn tại: {used - exported}"
        assert rule["for"] and rule["labels"]["severity"] in {"warning", "critical"}


def test_the_scan_stale_rule_matches_the_two_minute_heartbeat_promise() -> None:
    [rule] = [r for r in load_rules() if r["alert"] == "PriceAlertScanStale"]

    assert "> 120" in rule["expr"] and rule["labels"]["severity"] == "critical"


def run_check(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["bash", str(SCRIPT)],  # noqa: S607
        env={"ROOT_DIR": str(root), "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_repository_passes_the_price_alert_compliance_check() -> None:
    result = run_check(ROOT)

    assert result.returncode == 0, result.stderr


def test_the_compliance_check_names_what_is_missing(tmp_path: Path) -> None:
    result = run_check(tmp_path)

    assert result.returncode == 1
    for item in (
        "docker/nginx/maintenance.conf",
        "mục 13 của runbook",
        "mục 14 của runbook",
        "PRICE_ALERT_RECIPIENT_EMAILS",
        "APP_PUBLIC_URL",
        "luật cảnh báo quét trễ",
    ):
        assert item in result.stderr


def test_the_production_readiness_script_calls_the_price_alert_check() -> None:
    script = (ROOT / "scripts/compliance/check-production-readiness.sh").read_text("utf-8")

    assert "check-price-alert-readiness.sh" in script
