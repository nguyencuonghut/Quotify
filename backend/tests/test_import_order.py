"""Mỗi điểm vào của ứng dụng phải nạp được trong một tiến trình mới (không vòng nạp)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "module",
    [
        "app.worker",  # worker nạp app.db.session trước tiên
        "app.db.session",
        "app.core.observability",
        "app.core.price_alert_metrics",
        "app.main",
        "app.price_freshness_seed",
        "app.price_alert_replay",
    ],
)
def test_the_module_imports_cleanly_as_the_first_import_of_a_fresh_process(module: str) -> None:
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", f"import {module}"],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr[-800:]
