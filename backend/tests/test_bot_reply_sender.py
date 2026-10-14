"""Chia câu trả lời dài của chatbot thành các tin Telegram (kế hoạch 5.1, mục 4.7)."""

from __future__ import annotations

from app.services.bot_reply_sender import split_reply


def _units(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def test_a_short_reply_stays_one_part() -> None:
    assert split_reply("xin chào", max_parts=4, max_length=20) == ["xin chào"]


def test_an_empty_reply_has_no_parts() -> None:
    assert split_reply("  \n\n ", max_parts=4, max_length=20) == []


def test_a_long_reply_is_cut_at_a_paragraph_boundary() -> None:
    assert split_reply("aaaa bbbb\n\ncccc dddd", max_parts=4, max_length=12) == [
        "aaaa bbbb",
        "cccc dddd",
    ]


def test_without_a_paragraph_boundary_it_is_cut_at_a_line_boundary() -> None:
    assert split_reply("aaaa bbbb\ncccc dddd", max_parts=4, max_length=12) == [
        "aaaa bbbb",
        "cccc dddd",
    ]


def test_without_any_newline_it_is_cut_at_a_space() -> None:
    assert split_reply("aaaa bbbb cccc dddd", max_parts=4, max_length=12) == [
        "aaaa bbbb",
        "cccc dddd",
    ]


def test_a_paragraph_boundary_wins_over_a_line_boundary_and_a_space() -> None:
    assert split_reply("ab cd\nef\n\ngh ij", max_parts=4, max_length=12) == [
        "ab cd\nef",
        "gh ij",
    ]


def test_a_word_longer_than_the_limit_is_cut_hard() -> None:
    assert split_reply("x" * 30, max_parts=4, max_length=12) == ["x" * 12, "x" * 12, "x" * 6]


def test_the_limit_counts_utf16_units_so_emoji_never_push_a_part_over() -> None:
    parts = split_reply("😀" * 10, max_parts=4, max_length=8)  # mỗi emoji là 2 đơn vị UTF-16

    assert parts == ["😀" * 4, "😀" * 4, "😀" * 2]
    assert all(_units(part) <= 8 for part in parts)


def test_a_reply_beyond_the_part_cap_is_cut_with_an_ellipsis_and_stays_within_the_limit() -> None:
    reply = "\n\n".join(["a" * 9] * 5)  # 5 phần nếu không bị giới hạn

    parts = split_reply(reply, max_parts=2, max_length=10)

    assert len(parts) == 2
    assert parts[0] == "a" * 9
    assert parts[1].endswith("…") and _units(parts[1]) <= 10  # phần dư bị cắt, có dấu "…"


def test_a_reply_that_exactly_fits_the_part_cap_gets_no_ellipsis() -> None:
    reply = "\n\n".join(["a" * 9] * 2)

    assert split_reply(reply, max_parts=2, max_length=10) == ["a" * 9, "a" * 9]


def test_a_short_heading_before_a_long_list_does_not_waste_a_whole_part() -> None:
    heading = "Kết quả:\n\n"
    lines = "\n".join(
        f"dòng {number:03d} " + "x" * 90 for number in range(150)
    )  # không có dòng trống

    parts = split_reply(heading + lines, max_parts=4, max_length=4096)

    assert len(parts[0]) > 2048  # không tách tiêu đề thành một tin riêng vài ký tự
    assert not parts[-1].endswith("…")  # nhờ vậy không phải cắt cụt phần cuối
    assert "\n".join(parts).count("dòng ") == 150  # đủ 150 dòng


def test_a_reply_of_exactly_the_limit_is_one_part_and_one_unit_more_is_two() -> None:
    assert split_reply("a" * 12, max_parts=4, max_length=12) == ["a" * 12]
    assert split_reply("a" * 13, max_parts=4, max_length=12) == ["a" * 12, "a"]


def test_a_boundary_right_after_the_window_still_keeps_the_part_whole() -> None:
    # "aaaa bbbb" vừa đúng 9, dấu cách ngay sau nó là ranh giới nên không phải cắt lùi.
    assert split_reply("aaaa bbbb cccc", max_parts=4, max_length=9) == ["aaaa bbbb", "cccc"]


def test_a_paragraph_boundary_wins_even_when_a_later_line_boundary_is_closer_to_the_limit() -> None:
    parts = split_reply("aaaaaaa\n\nbbb\ncccccccc", max_parts=4, max_length=14)

    assert parts == ["aaaaaaa", "bbb\ncccccccc"]


def test_no_part_starts_or_ends_with_whitespace_and_none_is_empty() -> None:
    texts = [
        "aaa   bbb   ccc   ddd   eee",
        "aaa\n\n\n\nbbb\n\n\n\nccc\n\n\n\nddd",
        "x" * 10 + "   " + "y" * 10,
        "  mở đầu có khoảng trắng " + "z" * 30,
    ]
    for text in texts:
        for part in split_reply(text, max_parts=6, max_length=10):
            assert part and part == part.strip()


def test_the_cut_part_with_an_ellipsis_still_fits_when_it_was_exactly_full() -> None:
    reply = "\n\n".join(["a" * 10] * 5)  # mỗi phần đầy đúng giới hạn

    parts = split_reply(reply, max_parts=2, max_length=10)

    assert parts[0] == "a" * 10
    assert parts[1] == "a" * 9 + "…"  # nhường chỗ cho dấu "…" để không vượt giới hạn


def test_a_reply_that_fits_exactly_is_not_split_even_when_it_has_a_boundary_inside() -> None:
    assert split_reply("aaaa bbbb cc", max_parts=4, max_length=12) == ["aaaa bbbb cc"]


def test_whitespace_that_is_not_a_boundary_is_dropped_after_a_hard_cut() -> None:
    # Tab không phải ranh giới ưu tiên nên đây là cắt cứng; phần sau không được bắt đầu bằng tab.
    assert split_reply("x" * 12 + "\t" + "y" * 3, max_parts=4, max_length=12) == ["x" * 12, "yyy"]


def test_trailing_whitespace_is_trimmed_before_the_ellipsis() -> None:
    # Cắt phần cuối còn 9 đơn vị thì kết thúc bằng khoảng trắng; "…" không đứng sau khoảng trắng.
    assert split_reply("aaaaaaaa b\n\nccc", max_parts=1, max_length=10) == ["aaaaaaaa…"]
