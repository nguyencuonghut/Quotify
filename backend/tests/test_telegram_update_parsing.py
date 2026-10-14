from __future__ import annotations

from typing import Any

import pytest

from app.services.telegram_update_service import parse_command, parse_update


def _chat_member_update(
    *, chat_type: str = "private", new_status: str = "kicked"
) -> dict[str, Any]:
    return {
        "update_id": 77,
        "my_chat_member": {
            "chat": {"id": 42, "type": chat_type},
            "from": {"id": 42, "is_bot": False, "first_name": "An"},
            "date": 0,
            "old_chat_member": {"user": {"id": 1, "is_bot": True}, "status": "member"},
            "new_chat_member": {"user": {"id": 1, "is_bot": True}, "status": new_status},
        },
    }


def test_my_chat_member_update_is_parsed() -> None:
    update = parse_update(_chat_member_update(new_status="kicked"))

    assert update is not None
    assert update.message is None
    assert update.chat_member is not None
    assert update.chat_member.chat_type == "private"
    assert update.chat_member.from_user_id == 42
    assert update.chat_member.new_status == "kicked"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda u: u["my_chat_member"].pop("chat"),
        lambda u: u["my_chat_member"].pop("new_chat_member"),
        lambda u: u["my_chat_member"].update(new_chat_member={"status": 5}),
        lambda u: u.update(my_chat_member="nope"),
    ],
)
def test_malformed_my_chat_member_is_tolerated(mutate: Any) -> None:
    payload = _chat_member_update()
    mutate(payload)

    update = parse_update(payload)

    assert update is not None
    assert update.chat_member is None


def test_message_sender_names_are_parsed() -> None:
    update = parse_update(
        {
            "update_id": 1,
            "message": {
                "text": "/start abc",
                "chat": {"id": 5, "type": "private"},
                "from": {"id": 5, "first_name": "An", "username": "an_nguyen"},
            },
        }
    )

    assert update is not None
    assert update.message is not None
    assert (update.message.from_username, update.message.from_first_name) == ("an_nguyen", "An")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("/stop", ("/stop", "")),
        ("/STOP@Quotify_Bot", ("/stop", "")),
        ("/start   code123 ", ("/start", "code123")),
        ("xin chào", (None, "")),
        (None, (None, "")),
    ],
)
def test_parse_command(text: str | None, expected: tuple[str | None, str]) -> None:
    assert parse_command(text) == expected


def test_a_callback_query_is_parsed_with_its_message_and_data() -> None:
    update = parse_update(
        {
            "update_id": 9,
            "callback_query": {
                "id": "abc",
                "from": {"id": 42, "is_bot": False, "first_name": "An"},
                "message": {"message_id": 7, "chat": {"id": 42, "type": "private"}},
                "data": "pa:ok:123",
            },
        }
    )

    assert update is not None and update.callback is not None
    assert (update.callback.id, update.callback.from_user_id) == ("abc", 42)
    assert (update.callback.chat_id, update.callback.message_id) == (42, 7)
    assert update.callback.data == "pa:ok:123"


def test_a_callback_query_missing_its_message_still_keeps_the_id_so_it_can_be_answered() -> None:
    update = parse_update({"update_id": 9, "callback_query": {"id": "abc", "from": {"id": 42}}})

    assert update is not None and update.callback is not None
    assert (update.callback.id, update.callback.chat_id, update.callback.message_id) == (
        "abc",
        None,
        None,
    )
    assert parse_update({"update_id": 9, "callback_query": {"from": {"id": 42}}}).callback is None  # type: ignore[union-attr]


def _message_update(**fields: Any) -> dict[str, Any]:
    return {
        "update_id": 5,
        "message": {
            "message_id": 1,
            "date": 0,
            "chat": {"id": 42, "type": "private"},
            "from": {"id": 42, "is_bot": False, "first_name": "An"},
            **fields,
        },
    }


@pytest.mark.parametrize(
    ("fields", "kind"),
    [
        ({"text": "xin chào"}, "text"),
        ({"photo": [{"file_id": "p"}]}, "photo"),
        ({"document": {"file_id": "d"}}, "document"),
        ({"voice": {"file_id": "v"}}, "voice"),
        ({"audio": {"file_id": "a"}}, "audio"),
        ({"video": {"file_id": "v"}}, "video"),
        ({"video_note": {"file_id": "n"}}, "video_note"),
        ({"sticker": {"file_id": "s"}}, "sticker"),
        ({"animation": {"file_id": "g"}}, "animation"),
        ({"photo": [{"file_id": "p"}], "caption": "chú thích"}, "photo"),
        ({}, "other"),
    ],
)
def test_the_message_kind_is_recognised_without_reading_any_file(
    fields: dict[str, Any], kind: str
) -> None:
    update = parse_update(_message_update(**fields))

    assert update is not None and update.message is not None
    assert update.message.kind == kind


def test_text_wins_when_a_message_somehow_carries_both_text_and_an_attachment() -> None:
    update = parse_update(_message_update(text="xin chào", photo=[{"file_id": "p"}]))

    assert update is not None and update.message is not None
    assert update.message.kind == "text"
    assert update.message.text == "xin chào"


def test_a_non_string_text_is_not_a_text_message() -> None:
    update = parse_update(_message_update(text=123, sticker={"file_id": "s"}))

    assert update is not None and update.message is not None
    assert update.message.kind == "sticker"
    assert update.message.text is None


def test_a_gif_is_an_animation_even_though_telegram_also_sets_the_document_field() -> None:
    # Bot API: tin có `animation` cũng được đặt `document` (tương thích ngược).
    update = parse_update(_message_update(animation={"file_id": "g"}, document={"file_id": "g"}))

    assert update is not None and update.message is not None
    assert update.message.kind == "animation"


@pytest.mark.parametrize(
    ("fields", "kind"),
    [
        ({"location": {"latitude": 1.0, "longitude": 2.0}}, "location"),
        ({"contact": {"phone_number": "1", "first_name": "An"}}, "contact"),
        ({"poll": {"id": "1", "question": "?"}}, "poll"),
        ({"dice": {"emoji": "🎲", "value": 3}}, "dice"),
        ({"venue": {"title": "x"}}, "venue"),
        (
            {"pinned_message": {"message_id": 1}},
            "other",
        ),  # tin dịch vụ, không phải nội dung người dùng
        ({"message_auto_delete_timer_changed": {"message_auto_delete_time": 5}}, "other"),
    ],
)
def test_user_content_that_is_not_a_file_is_told_apart_from_service_messages(
    fields: dict[str, Any], kind: str
) -> None:
    update = parse_update(_message_update(**fields))

    assert update is not None and update.message is not None
    assert update.message.kind == kind
