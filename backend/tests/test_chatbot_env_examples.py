"""Hai file `.env` mẫu mô tả đủ biến của chatbot (kế hoạch 5.1, S8).

Người vận hành chép file mẫu thành `.env`; một biến thiếu nghĩa là họ không biết nó tồn tại, một giá
trị lệch mặc định nghĩa là chép mẫu xong hành vi đã khác mà không ai chủ ý đổi.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter

from app.core.config import Settings

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = [".env.example", ".env.production.example"]
# Chỉ để thử trên dev (độ trễ giả của engine giả); production không có lý do nhắc tới nó.
DEV_ONLY = {"BOT_STUB_DELAY_SECONDS"}

pytestmark = pytest.mark.skipif(
    not (ROOT / ".env.example").exists(),
    reason="Không có file .env mẫu ở gốc repo (đang chạy trong container backend)",
)


def _chatbot_fields() -> dict[str, object]:
    """Biến môi trường của chatbot trong Settings → trường của nó."""
    return {
        field.alias: field
        for field in Settings.model_fields.values()
        if field.alias and field.alias.startswith(("BOT_", "CHATBOT_"))
    }


def _documented(name: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in (ROOT / name).read_text("utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip() and not key.lstrip().startswith("#"):
            values[key.strip()] = value.strip()
    return values


def test_there_are_chatbot_settings_to_document() -> None:
    assert {"CHATBOT_ENABLED", "BOT_MAX_ATTEMPTS", "BOT_LEASE_SECONDS"} <= set(_chatbot_fields())


@pytest.mark.parametrize("example", EXAMPLES)
def test_every_chatbot_variable_is_documented(example: str) -> None:
    expected = set(_chatbot_fields()) - (
        DEV_ONLY if example == ".env.production.example" else set()
    )

    assert expected - set(_documented(example)) == set()


@pytest.mark.parametrize("example", EXAMPLES)
def test_a_documented_value_is_the_default_so_copying_the_example_changes_nothing(
    example: str,
) -> None:
    documented = _documented(example)
    fields = _chatbot_fields()

    for name, raw in documented.items():
        if name not in fields:
            continue
        field = fields[name]
        parsed = TypeAdapter(field.annotation).validate_python(raw)  # type: ignore[attr-defined]
        assert parsed == field.default, f"{example}: {name}={raw!r}"  # type: ignore[attr-defined]


def test_the_production_example_does_not_offer_the_dev_only_knobs() -> None:
    assert DEV_ONLY & set(_documented(".env.production.example")) == set()


def test_no_example_documents_a_chatbot_variable_that_settings_does_not_know() -> None:
    known = set(_chatbot_fields())
    for example in EXAMPLES:
        unknown = {
            name for name in _documented(example) if name.startswith(("BOT_", "CHATBOT_"))
        } - known

        assert unknown == set(), example
