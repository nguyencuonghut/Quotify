from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

from app.api.v1.quotes import _build_version_response, _loaded_full_name
from app.models import QuoteVersion, User, UserStatus


def _make_version(**overrides: object) -> QuoteVersion:
    now = datetime.now(UTC)
    defaults: dict[str, object] = {
        "id": uuid4(),
        "quote_id": uuid4(),
        "version_number": 1,
        "received_date": date(2026, 8, 1),
        "status": "draft",
        "is_backfilled": False,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    version = QuoteVersion(**defaults)  # type: ignore[arg-type]
    version.lines = []
    return version


def test_loaded_full_name_returns_none_when_relationship_never_loaded() -> None:
    # `_build_version_response` dùng chung cho nhiều endpoint — không phải
    # endpoint nào cũng selectinload `created_by`, nên hàm này phải bỏ qua
    # an toàn thay vì kích hoạt lazy-load (crash trên AsyncSession).
    version = _make_version()

    assert _loaded_full_name(version, "created_by") is None


def test_loaded_full_name_returns_name_when_relationship_assigned() -> None:
    version = _make_version()
    version.created_by = User(
        id=uuid4(),
        email="a@example.com",
        full_name="Nguyễn Văn A",
        status=UserStatus.ACTIVE,
    )

    assert _loaded_full_name(version, "created_by") == "Nguyễn Văn A"


def test_loaded_full_name_returns_none_when_loaded_but_null() -> None:
    version = _make_version()
    version.created_by = None

    assert _loaded_full_name(version, "created_by") is None


def test_build_version_response_includes_created_by_name_when_loaded() -> None:
    version = _make_version()
    version.created_by = User(
        id=uuid4(),
        email="a@example.com",
        full_name="Nguyễn Văn A",
        status=UserStatus.ACTIVE,
    )

    response = _build_version_response(version)

    assert response.created_by_name == "Nguyễn Văn A"


def test_build_version_response_defaults_created_by_name_to_none_when_not_loaded() -> None:
    version = _make_version()

    response = _build_version_response(version)

    assert response.created_by_name is None
