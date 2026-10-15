"""Phần thuần túy của hạn mức mỗi ngày (kế hoạch 5.1, S10): biên ngày, câu từ chối, câu nhắc."""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from app.services.telegram_bot_messages import (
    limit_summary_text,
    quota_denied_text,
    quota_reminder_text,
)
from app.services.usage_gate import (
    BUSINESS_TIMEZONE,
    QuotaDecision,
    QuotaSummary,
    business_day_bounds,
)

VN = ZoneInfo("Asia/Ho_Chi_Minh")


@pytest.fixture(params=["UTC", "Asia/Ho_Chi_Minh", "America/Los_Angeles"])
def process_timezone(request: pytest.FixtureRequest) -> Iterator[str]:
    """Chạy cùng một kiểm tra dưới ba múi giờ của TIẾN TRÌNH (hệ thống UTC, UTC+7, UTC-8)."""
    previous = os.environ.get("TZ")
    os.environ["TZ"] = request.param
    time.tzset()
    yield request.param
    if previous is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = previous
    time.tzset()


def test_the_business_day_runs_from_midnight_to_midnight_in_vietnam_whatever_the_server_zone(
    process_timezone: str,
) -> None:
    start, end = business_day_bounds(datetime(2026, 10, 14, 16, 59, 59, tzinfo=UTC))  # 23:59:59 VN

    assert start == datetime(2026, 10, 13, 17, 0, tzinfo=UTC)  # 00:00 ngày 14 giờ Việt Nam
    assert end == datetime(2026, 10, 14, 17, 0, tzinfo=UTC)  # 00:00 ngày 15 giờ Việt Nam


def test_one_second_later_it_is_the_next_business_day(process_timezone: str) -> None:
    start, end = business_day_bounds(datetime(2026, 10, 14, 17, 0, 0, tzinfo=UTC))  # 00:00:00 VN

    assert start == datetime(2026, 10, 14, 17, 0, tzinfo=UTC)
    assert end == datetime(2026, 10, 15, 17, 0, tzinfo=UTC)


def test_a_moment_given_in_another_zone_lands_in_the_vietnamese_day() -> None:
    # 23:30 ngày 14 ở Los Angeles (UTC-7 mùa hè) là 13:30 ngày 15 ở Việt Nam.
    los_angeles = datetime(2026, 10, 14, 23, 30, tzinfo=ZoneInfo("America/Los_Angeles"))

    start, _ = business_day_bounds(los_angeles)

    assert start.astimezone(VN).date().isoformat() == "2026-10-15"


def test_a_moment_without_a_zone_is_refused_instead_of_guessed() -> None:
    with pytest.raises(ValueError, match="múi giờ"):
        business_day_bounds(datetime(2026, 10, 14, 12, 0))


def _decision(**overrides: object) -> QuotaDecision:
    values: dict[str, object] = {
        "allowed": True,
        "reason": None,
        "used": 0,
        "limit": 20,
        "resets_at": datetime(2026, 10, 15, 0, 0, tzinfo=VN),
        "turns_used": 0,
        "turns_limit": 20,
        "files_used": 0,
        "files_limit": 5,
    }
    values.update(overrides)
    return QuotaDecision(**values)  # type: ignore[arg-type]


def test_the_refusal_says_how_many_turns_were_used_and_when_they_come_back() -> None:
    decision = _decision(allowed=False, reason="turns", used=20, limit=20, turns_used=20)

    text = quota_denied_text(decision)

    assert "20/20 lượt hỏi" in text
    assert "00:00 ngày 15/10/2026 (giờ Việt Nam)" in text
    assert "quản trị viên" in text


def test_the_file_refusal_says_the_user_can_still_ask_in_text() -> None:
    decision = _decision(allowed=False, reason="files", used=5, limit=5, files_used=5)

    text = quota_denied_text(decision)

    assert "5/5 lượt gửi ảnh hoặc PDF" in text
    assert "bằng chữ" in text
    assert "00:00 ngày 15/10/2026" in text


def test_the_reset_time_is_shown_in_vietnamese_time_even_when_given_in_utc() -> None:
    decision = _decision(
        allowed=False,
        reason="turns",
        used=20,
        resets_at=datetime(2026, 10, 14, 17, 0, tzinfo=UTC),
    )

    assert "00:00 ngày 15/10/2026" in quota_denied_text(decision)


@pytest.mark.parametrize(
    ("used_before", "expected"),
    [
        (13, None),  # còn 6/20 = 30%: chưa nhắc
        (14, None),  # còn 5/20 = 25%: chưa nhắc
        (15, "Còn 4/20 lượt hôm nay."),  # còn 4/20 = đúng 20%: nhắc
        (18, "Còn 1/20 lượt hôm nay."),
        (19, "Bạn đã dùng hết 20/20 lượt hôm nay."),  # lượt cuối: nói rõ đã hết
    ],
)
def test_the_reminder_appears_at_the_threshold_and_counts_the_turn_being_answered(
    used_before: int, expected: str | None
) -> None:
    decision = _decision(turns_used=used_before)

    assert quota_reminder_text(decision, "text", warn_percent=20) == expected


def test_no_reminder_when_it_is_switched_off_or_the_turns_are_unlimited() -> None:
    assert quota_reminder_text(_decision(turns_used=19), "text", warn_percent=0) is None
    unlimited = _decision(turns_used=500, turns_limit=0)
    assert quota_reminder_text(unlimited, "text", warn_percent=20) is None


def test_a_file_turn_also_reminds_about_the_file_allowance() -> None:
    decision = _decision(turns_used=3, files_used=3)

    text = quota_reminder_text(decision, "photo", warn_percent=20)

    assert text == "Còn 1/5 lượt gửi ảnh hoặc PDF hôm nay."  # còn 1/5 = 20%; lượt chữ còn nhiều


def test_the_last_file_turn_says_the_file_allowance_is_used_up() -> None:
    decision = _decision(turns_used=3, files_used=4)  # lượt file thứ 5 trên 5

    text = quota_reminder_text(decision, "document", warn_percent=20)

    assert text == "Bạn đã dùng hết 5/5 lượt gửi ảnh hoặc PDF hôm nay."


def test_a_file_turn_near_both_limits_reminds_about_both_in_one_line() -> None:
    decision = _decision(turns_used=15, files_used=3)

    text = quota_reminder_text(decision, "photo", warn_percent=20)

    assert text == "Còn 4/20 lượt hôm nay. Còn 1/5 lượt gửi ảnh hoặc PDF hôm nay."


def test_a_text_turn_never_mentions_the_file_allowance() -> None:
    decision = _decision(turns_used=3, files_used=4)  # lượt file sắp hết nhưng tin này là chữ

    assert quota_reminder_text(decision, "text", warn_percent=20) is None


def test_the_summary_lists_used_remaining_and_the_reset_time_without_tokens() -> None:
    summary = QuotaSummary(
        turns_used=3,
        turns_limit=20,
        files_used=0,
        files_limit=5,
        resets_at=datetime(2026, 10, 15, 0, 0, tzinfo=BUSINESS_TIMEZONE),
    )

    text = limit_summary_text(summary)

    assert "đã dùng 3/20, còn 17" in text
    assert "đã dùng 0/5, còn 5" in text
    assert "00:00 ngày 15/10/2026" in text
    assert "token" not in text.lower()


def test_the_summary_never_shows_a_negative_remainder_after_the_limit_was_lowered() -> None:
    summary = QuotaSummary(
        turns_used=25,  # hôm nay đã dùng 25 khi mức còn 30; sau đó mức bị hạ xuống 20
        turns_limit=20,
        files_used=0,
        files_limit=5,
        resets_at=datetime(2026, 10, 15, 0, 0, tzinfo=BUSINESS_TIMEZONE),
    )

    assert "đã dùng 25/20, còn 0" in limit_summary_text(summary)


def test_the_summary_says_unlimited_instead_of_a_zero_limit() -> None:
    summary = QuotaSummary(
        turns_used=7,
        turns_limit=0,
        files_used=0,
        files_limit=0,
        resets_at=datetime(2026, 10, 15, 0, 0, tzinfo=BUSINESS_TIMEZONE),
    )

    text = limit_summary_text(summary)

    assert "đã dùng 7, không giới hạn" in text
    assert "0/0" not in text
