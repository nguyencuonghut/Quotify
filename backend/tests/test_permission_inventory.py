from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest


def _find_backend_root() -> Path:
    current_path = Path(__file__).resolve()
    for parent in current_path.parents:
        backend_app_root = parent / "backend" / "app"
        if (backend_app_root / "auth" / "seed_data.py").exists():
            return backend_app_root
        container_app_root = parent / "app"
        if (container_app_root / "auth" / "seed_data.py").exists():
            return container_app_root

    raise AssertionError("Không tìm thấy backend app root để kiểm tra permission inventory.")


def _find_frontend_root() -> Path | None:
    current_path = Path(__file__).resolve()
    for parent in current_path.parents:
        frontend_root = parent / "frontend" / "src"
        if frontend_root.exists():
            return frontend_root

    return None


BACKEND_ROOT = _find_backend_root()
FRONTEND_ROOT = _find_frontend_root()
SEED_DATA_PATH = BACKEND_ROOT / "auth" / "seed_data.py"

BACKEND_PERMISSION_CALLS = {"require_permission", "has_permission"}
FRONTEND_PERMISSION_PATTERN = re.compile(r"permissionStore\.can\(\s*['\"]([^'\"]+)['\"]")
FRONTEND_PERMISSION_PROPERTY_PATTERN = re.compile(
    r"(?:requiredPermission|permission):\s*['\"]([^'\"]+)['\"]",
)


def test_backend_permission_usage_is_seeded() -> None:
    used_permissions: set[str] = set()
    seeded_permissions = _load_seeded_permission_codes()

    for path in BACKEND_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name):
                continue
            if node.func.id not in BACKEND_PERMISSION_CALLS:
                continue
            if not node.args or not isinstance(node.args[0], ast.Constant):
                continue
            if isinstance(node.args[0].value, str):
                used_permissions.add(node.args[0].value)

    missing_permissions = used_permissions - seeded_permissions

    assert missing_permissions == set()


def test_frontend_permission_visibility_usage_is_seeded() -> None:
    if FRONTEND_ROOT is None:
        pytest.skip("Frontend source không có trong backend-only test container.")

    used_permissions: set[str] = set()
    seeded_permissions = _load_seeded_permission_codes()

    for path in list(FRONTEND_ROOT.rglob("*.ts")) + list(FRONTEND_ROOT.rglob("*.vue")):
        content = path.read_text(encoding="utf-8")
        used_permissions.update(FRONTEND_PERMISSION_PATTERN.findall(content))
        used_permissions.update(FRONTEND_PERMISSION_PROPERTY_PATTERN.findall(content))

    missing_permissions = used_permissions - seeded_permissions

    assert missing_permissions == set()


def test_quotify_permission_bundle_is_seeded() -> None:
    expected_permissions = {
        "material_types.read",
        "material_types.create",
        "material_types.update",
        "material_types.delete",
        "material_types.import",
        "materials.read",
        "materials.create",
        "materials.update",
        "materials.delete",
        "materials.import",
        "suppliers.read",
        "suppliers.create",
        "suppliers.update",
        "suppliers.delete",
        "suppliers.import",
        "quotes.read",
        "quotes.create",
        "quotes.update",
        "quotes.mark_purchased",
        "quote_notes.read",
        "quote_notes.create",
        "quote_notes.update",
        "exchange_rates.read",
        "quotify_settings.read",
        "quotify_settings.update",
    }

    assert expected_permissions <= _load_seeded_permission_codes()


def _load_seeded_permission_codes() -> set[str]:
    tree = ast.parse(SEED_DATA_PATH.read_text(encoding="utf-8"), filename=str(SEED_DATA_PATH))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        has_permission_assignment = any(
            isinstance(target, ast.Name) and target.id == "BASE_PERMISSION_CODES"
            for target in node.targets
        )
        if not has_permission_assignment:
            continue
        if not isinstance(node.value, ast.List):
            continue
        return {
            item.value
            for item in node.value.elts
            if isinstance(item, ast.Constant) and isinstance(item.value, str)
        }

    raise AssertionError("BASE_PERMISSION_CODES was not found in seed_data.py")
