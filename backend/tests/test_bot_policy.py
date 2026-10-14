"""Chính sách bật chatbot dựng từ cấu hình, và việc nối vào runner (kế hoạch 5.1, KT13 và KT17).

Đảm bảo "mặc định tắt" được chứng minh bằng `Settings` thật, không chỉ bằng chính sách dựng tay.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from app.api.v1.telegram import get_telegram_runner
from app.core.config import Settings
from app.services import telegram_bot_messages as bot_messages
from app.services.bot_dispatcher import ArqBotDispatcher, NullBotDispatcher, build_chatbot_runtime
from app.services.bot_policy import ChatbotPolicy


def _settings(**overrides: Any) -> Settings:
    # `_env_file=None`: không để `.env` của máy dev (có token bot thật) lọt vào test.
    return Settings(_env_file=None, **overrides)  # type: ignore[call-arg]


def test_the_chatbot_is_off_by_default() -> None:
    policy = ChatbotPolicy.from_settings(_settings())

    assert policy.enabled is False
    assert policy.allows("ai.do@honghafeed.vn") is False


def test_the_chatbot_needs_both_its_own_flag_and_the_telegram_flag() -> None:
    only_chatbot = ChatbotPolicy.from_settings(_settings(CHATBOT_ENABLED=True))
    only_telegram = ChatbotPolicy.from_settings(_settings(TELEGRAM_ENABLED=True))
    both = ChatbotPolicy.from_settings(_settings(CHATBOT_ENABLED=True, TELEGRAM_ENABLED=True))

    assert (only_chatbot.enabled, only_telegram.enabled, both.enabled) == (False, False, True)


def test_an_empty_pilot_list_means_everyone_who_is_linked() -> None:
    policy = ChatbotPolicy.from_settings(
        _settings(CHATBOT_ENABLED=True, TELEGRAM_ENABLED=True, CHATBOT_PILOT_USER_EMAILS="  "),
    )

    assert policy.pilot_emails is None
    assert policy.allows("bat.ky@honghafeed.vn") is True


def test_the_pilot_list_is_trimmed_case_insensitive_and_limits_who_is_handed_off() -> None:
    policy = ChatbotPolicy.from_settings(
        _settings(
            CHATBOT_ENABLED=True,
            TELEGRAM_ENABLED=True,
            CHATBOT_PILOT_USER_EMAILS=" Thu.Nghiem@HongHaFeed.vn , b@x.vn,, ",
        ),
    )

    assert policy.pilot_emails == frozenset({"thu.nghiem@honghafeed.vn", "b@x.vn"})
    assert policy.allows("THU.NGHIEM@honghafeed.vn") is True
    assert policy.allows("nguoi.khac@honghafeed.vn") is False
    assert policy.allows(None) is False


def test_a_pilot_list_that_is_set_but_has_no_email_closes_the_chatbot() -> None:
    policy = ChatbotPolicy.from_settings(
        _settings(CHATBOT_ENABLED=True, TELEGRAM_ENABLED=True, CHATBOT_PILOT_USER_EMAILS=" , "),
    )

    assert policy.pilot_emails == frozenset()
    assert policy.allows("bat.ky@honghafeed.vn") is False


def test_the_runtime_has_no_bell_when_the_chatbot_is_off_and_an_arq_bell_when_it_is_on() -> None:
    _, off_dispatcher = build_chatbot_runtime(_settings())
    on_policy, on_dispatcher = build_chatbot_runtime(
        _settings(CHATBOT_ENABLED=True, TELEGRAM_ENABLED=True),
    )

    assert isinstance(off_dispatcher, NullBotDispatcher)
    assert on_policy.enabled
    assert isinstance(on_dispatcher, ArqBotDispatcher)


@pytest.mark.parametrize(
    ("overrides", "expected_enabled"),
    [({}, False), ({"CHATBOT_ENABLED": True}, True)],
)
async def test_the_webhook_runner_is_wired_from_the_settings(
    overrides: dict[str, Any],
    expected_enabled: bool,
) -> None:
    settings = _settings(
        TELEGRAM_ENABLED=True,
        TELEGRAM_BOT_TOKEN="123456:TEST-TOKEN",
        **overrides,
    )
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))

    runner = get_telegram_runner(request, settings)  # type: ignore[arg-type]

    try:
        assert runner.chatbot.enabled is expected_enabled
        expected_type = ArqBotDispatcher if expected_enabled else NullBotDispatcher
        assert isinstance(runner.dispatcher, expected_type)
        assert request.app.state.telegram_runner is runner
    finally:
        await runner.aclose()


def test_the_pending_cap_defaults_to_five_and_follows_the_setting() -> None:
    assert ChatbotPolicy.from_settings(_settings()).max_pending_per_chat == 5
    assert (
        ChatbotPolicy.from_settings(_settings(BOT_MAX_PENDING_PER_CHAT=9)).max_pending_per_chat == 9
    )


def test_the_pending_cap_cannot_be_zero() -> None:
    with pytest.raises(ValidationError):
        _settings(BOT_MAX_PENDING_PER_CHAT=0)


def test_a_full_queue_never_outlives_the_message_ttl() -> None:
    # Dòng cuối của hàng đầy phải còn hạn khi tới lượt: TTL phải chứa cả hàng đợi (kế hoạch 4.8).
    settings = _settings()
    worst_case_seconds = settings.bot_max_pending_per_chat * (
        settings.bot_row_timeout_seconds + settings.bot_send_budget_seconds
    )

    assert settings.bot_message_ttl_seconds >= worst_case_seconds


@pytest.mark.parametrize("name", ["NON_TEXT_TEXT", "PENDING_LIMIT_TEXT"])
def test_the_new_user_facing_messages_are_vietnamese_with_diacritics(name: str) -> None:
    message = getattr(bot_messages, name)

    assert not message.isascii()  # tiếng Việt có dấu, không phải chuỗi không dấu
    assert "<" not in message and "&" not in message  # gửi bằng HTML nên không có ký tự đặc biệt
