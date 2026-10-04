from __future__ import annotations

import pytest

from app.core.config import Settings


def _settings(value: str | None) -> Settings:
    data: dict[str, object] = {"app_env": "test", "otel_enabled": False}
    if value is not None:
        data["PRICE_ALERT_RECIPIENT_EMAILS"] = value
    return Settings.model_validate(data)


def test_the_pilot_list_is_empty_by_default() -> None:
    assert _settings(None).price_alert_recipient_email_set == frozenset()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("a@x.vn", {"a@x.vn"}),
        (" A@X.vn , b@x.vn ,, ", {"a@x.vn", "b@x.vn"}),
        ("   ", set()),
    ],
)
def test_the_pilot_list_is_trimmed_lowercased_and_split_on_commas(
    raw: str, expected: set[str]
) -> None:
    assert _settings(raw).price_alert_recipient_email_set == frozenset(expected)
