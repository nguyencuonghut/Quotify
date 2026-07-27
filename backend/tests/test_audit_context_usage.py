from __future__ import annotations

from pathlib import Path


def test_audit_routes_use_shared_context_helper_for_client_ip() -> None:
    api_root = Path("app/api/v1")
    route_sources = [path for path in api_root.glob("*.py") if path.name not in {"audit_logs.py"}]

    violations: list[str] = []
    for path in route_sources:
        source = path.read_text(encoding="utf-8")
        if "_extract_client_ip" in source or "request.client.host" in source:
            violations.append(str(path))

    assert violations == []
