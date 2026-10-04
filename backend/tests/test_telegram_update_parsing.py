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
