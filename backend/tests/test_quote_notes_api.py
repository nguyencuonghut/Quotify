from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.v1.quotes import get_quote_note_service
from app.api.v1.quotify_settings import get_audit_log_service
from app.auth.dependencies import get_current_user
from app.db.session import get_db_session
from app.models import Permission, Role, User, UserStatus
from app.models.quote_note import QuoteNote
from app.models.quote_note_revision import QuoteNoteRevision


class MockSession:
    def __init__(self) -> None:
        self.committed = False

    async def commit(self) -> None:
        self.committed = True

    async def flush(self) -> None:
        pass


class MockAuditLogService:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def log_event(self, **kwargs: Any) -> None:
        context = kwargs.pop("context", None)
        event = dict(kwargs)
        if context is not None:
            event.update(
                {
                    "actor_user_id": context.actor_user_id,
                    "entity_id": context.entity_id,
                    "ip_address": context.ip_address,
                    "metadata_json": context.metadata_json,
                    "request_id": context.request_id,
                }
            )
        self.events.append(event)


class MockQuoteNoteService:
    def __init__(self) -> None:
        self.notes: dict[Any, QuoteNote] = {}
        self.revisions: list[QuoteNoteRevision] = []

    async def get_note_by_quote_id(self, quote_id: Any) -> QuoteNote | None:
        for note in self.notes.values():
            if note.quote_id == quote_id:
                return note
        return None

    async def update_note(
        self, *, quote_id: Any, content: str, author_id: Any
    ) -> QuoteNoteRevision:
        if content == "error":
            raise ValueError("Invalid content")

        note = await self.get_note_by_quote_id(quote_id)
        if not note:
            note = QuoteNote(
                id=uuid4(),
                quote_id=quote_id,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            self.notes[note.id] = note
            revision_number = 1
        else:
            revision_number = len(note.revisions) + 1
            note.updated_at = datetime.now(UTC)

        # Mock author user object
        author = User(
            id=author_id,
            email="admin@example.com",
            full_name="Admin User",
            avatar_url="/api/v1/files/avatar/download",
        )

        revision = QuoteNoteRevision(
            id=uuid4(),
            note_id=note.id,
            revision_number=revision_number,
            content=content,
            author_id=author_id,
            created_at=datetime.now(UTC),
        )
        revision.author = author
        note.revisions.append(revision)
        self.revisions.append(revision)
        return revision

    async def update_revision(self, *, revision_id: Any, content: str) -> QuoteNoteRevision:
        if content == "error":
            raise ValueError("Invalid revision content")
        for r in self.revisions:
            if r.id == revision_id:
                r.content = content
                return r
        raise ValueError("Revision not found")

    async def get_revision_by_id(self, revision_id: Any) -> QuoteNoteRevision | None:
        for revision in self.revisions:
            if revision.id == revision_id:
                return revision
        return None

    async def delete_revision(self, *, revision_id: Any) -> None:
        found = False
        for r in self.revisions:
            if r.id == revision_id:
                found = True
                break
        if not found:
            raise ValueError("Revision not found")
        self.revisions = [r for r in self.revisions if r.id != revision_id]


@pytest.fixture
def override_dependencies(
    app: FastAPI,
) -> Generator[tuple[MockQuoteNoteService, MockAuditLogService, MockSession], None, None]:
    permissions = [
        Permission(id=uuid4(), code="quote_notes.read"),
        Permission(id=uuid4(), code="quote_notes.create"),
        Permission(id=uuid4(), code="quote_notes.update"),
    ]
    admin_role = Role(id=uuid4(), name="admin", is_system=True)
    admin_role.permissions = permissions
    admin_user = User(
        id=uuid4(), email="admin@example.com", status=UserStatus.ACTIVE, full_name="Admin User"
    )
    admin_user.roles = [admin_role]

    note_service = MockQuoteNoteService()
    audit_service = MockAuditLogService()
    session = MockSession()

    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[get_quote_note_service] = lambda: note_service
    app.dependency_overrides[get_audit_log_service] = lambda: audit_service
    app.dependency_overrides[get_db_session] = lambda: session

    yield note_service, audit_service, session

    app.dependency_overrides.clear()


def make_note_user(*, permissions: list[str]) -> User:
    role = Role(id=uuid4(), name="user", is_system=True)
    role.permissions = [Permission(id=uuid4(), code=permission) for permission in permissions]
    user = User(
        id=uuid4(),
        email=f"user-{uuid4()}@example.com",
        status=UserStatus.ACTIVE,
        full_name="Regular User",
    )
    user.roles = [role]
    return user


@pytest.mark.asyncio
async def test_get_note_returns_empty_note_if_not_found(
    client: AsyncClient,
    override_dependencies: tuple[MockQuoteNoteService, MockAuditLogService, MockSession],
) -> None:
    quote_id = uuid4()
    response = await client.get(f"/api/v1/quotes/{quote_id}/notes")
    assert response.status_code == 200
    data = response.json()
    assert data["quote_id"] == str(quote_id)
    assert data["id"] is None
    assert data["revisions"] == []


@pytest.mark.asyncio
async def test_get_note_returns_note_and_revisions(
    client: AsyncClient,
    override_dependencies: tuple[MockQuoteNoteService, MockAuditLogService, MockSession],
) -> None:
    note_service, _, _ = override_dependencies
    quote_id = uuid4()

    # Pre-populate note and a revision
    await note_service.update_note(quote_id=quote_id, content="<p>Test note</p>", author_id=uuid4())

    response = await client.get(f"/api/v1/quotes/{quote_id}/notes")
    assert response.status_code == 200
    data = response.json()
    assert data["quote_id"] == str(quote_id)
    assert len(data["revisions"]) == 1
    assert data["revisions"][0]["content"] == "<p>Test note</p>"
    assert data["revisions"][0]["author_name"] == "Admin User"
    assert data["revisions"][0]["author_avatar_url"] == "/api/v1/files/avatar/download"


@pytest.mark.asyncio
async def test_update_note_creates_and_logs_audit(
    client: AsyncClient,
    override_dependencies: tuple[MockQuoteNoteService, MockAuditLogService, MockSession],
) -> None:
    _, audit_service, _ = override_dependencies
    quote_id = uuid4()

    response = await client.put(
        f"/api/v1/quotes/{quote_id}/notes",
        json={"content": "<p>New Content</p>"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["revision_number"] == 1
    assert data["content"] == "<p>New Content</p>"
    assert data["author_name"] == "Admin User"
    assert data["author_avatar_url"] is None

    # Verify audit log was emitted
    assert len(audit_service.events) == 1
    assert audit_service.events[0]["action"] == "quotes.note_updated"
    assert audit_service.events[0]["entity_id"] == str(quote_id)
    assert audit_service.events[0]["metadata_json"]["quote_id"] == str(quote_id)
    assert audit_service.events[0]["metadata_json"]["revision_number"] == 1


@pytest.mark.asyncio
async def test_user_with_note_create_permission_can_add_note_to_any_quote(
    app: FastAPI,
    client: AsyncClient,
    override_dependencies: tuple[MockQuoteNoteService, MockAuditLogService, MockSession],
) -> None:
    _, audit_service, session = override_dependencies
    note_user = make_note_user(permissions=["quote_notes.create"])
    app.dependency_overrides[get_current_user] = lambda: note_user
    quote_id = uuid4()

    response = await client.put(
        f"/api/v1/quotes/{quote_id}/notes",
        json={"content": "<p>Nhận định thị trường mới</p>"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["revision_number"] == 1
    assert data["author_name"] == "Regular User"
    assert session.committed is True
    assert len(audit_service.events) == 1
    assert audit_service.events[0]["actor_user_id"] == note_user.id
    assert audit_service.events[0]["entity_id"] == str(quote_id)


@pytest.mark.asyncio
async def test_update_note_handles_value_error(
    client: AsyncClient,
    override_dependencies: tuple[MockQuoteNoteService, MockAuditLogService, MockSession],
) -> None:
    quote_id = uuid4()

    response = await client.put(
        f"/api/v1/quotes/{quote_id}/notes",
        json={"content": "error"},
    )

    assert response.status_code == 400
    assert "Invalid content" in response.json()["detail"]


@pytest.mark.asyncio
async def test_update_revision_api_success_and_logs_audit(
    client: AsyncClient,
    override_dependencies: tuple[MockQuoteNoteService, MockAuditLogService, MockSession],
) -> None:
    note_service, audit_service, _ = override_dependencies
    quote_id = uuid4()

    # Pre-populate note and a revision
    revision = await note_service.update_note(
        quote_id=quote_id, content="<p>Initial content</p>", author_id=uuid4()
    )

    response = await client.patch(
        f"/api/v1/quotes/{quote_id}/notes/revisions/{revision.id}",
        json={"content": "<p>Updated content</p>"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["content"] == "<p>Updated content</p>"
    assert data["id"] == str(revision.id)

    # Verify audit log was emitted
    assert len(audit_service.events) == 1
    assert audit_service.events[0]["action"] == "quotes.note_revision_updated"
    assert audit_service.events[0]["metadata_json"]["quote_id"] == str(quote_id)
    assert audit_service.events[0]["metadata_json"]["revision_id"] == str(revision.id)


@pytest.mark.asyncio
async def test_user_can_update_own_note_revision(
    app: FastAPI,
    client: AsyncClient,
    override_dependencies: tuple[MockQuoteNoteService, MockAuditLogService, MockSession],
) -> None:
    note_service, audit_service, _ = override_dependencies
    quote_id = uuid4()
    note_user = make_note_user(permissions=["quote_notes.update"])
    app.dependency_overrides[get_current_user] = lambda: note_user
    revision = await note_service.update_note(
        quote_id=quote_id,
        content="<p>Nhận định ban đầu</p>",
        author_id=note_user.id,
    )

    response = await client.patch(
        f"/api/v1/quotes/{quote_id}/notes/revisions/{revision.id}",
        json={"content": "<p>Nhận định đã sửa</p>"},
    )

    assert response.status_code == 200
    assert response.json()["content"] == "<p>Nhận định đã sửa</p>"
    assert len(audit_service.events) == 1


@pytest.mark.asyncio
async def test_user_cannot_update_another_users_note_revision(
    app: FastAPI,
    client: AsyncClient,
    override_dependencies: tuple[MockQuoteNoteService, MockAuditLogService, MockSession],
) -> None:
    note_service, audit_service, session = override_dependencies
    quote_id = uuid4()
    other_user_id = uuid4()
    current_user = make_note_user(permissions=["quote_notes.update"])
    app.dependency_overrides[get_current_user] = lambda: current_user
    revision = await note_service.update_note(
        quote_id=quote_id,
        content="<p>Ghi chú của người khác</p>",
        author_id=other_user_id,
    )

    response = await client.patch(
        f"/api/v1/quotes/{quote_id}/notes/revisions/{revision.id}",
        json={"content": "<p>Sửa trái phép</p>"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Bạn chỉ được sửa hoặc xóa ghi chú do chính mình tạo."
    assert audit_service.events == []
    assert session.committed is False


@pytest.mark.asyncio
async def test_delete_revision_api_success_and_logs_audit(
    client: AsyncClient,
    override_dependencies: tuple[MockQuoteNoteService, MockAuditLogService, MockSession],
) -> None:
    note_service, audit_service, _ = override_dependencies
    quote_id = uuid4()

    # Pre-populate note and a revision
    revision = await note_service.update_note(
        quote_id=quote_id, content="<p>Initial content</p>", author_id=uuid4()
    )

    response = await client.delete(
        f"/api/v1/quotes/{quote_id}/notes/revisions/{revision.id}",
    )

    assert response.status_code == 204

    # Verify audit log was emitted
    assert len(audit_service.events) == 1
    assert audit_service.events[0]["action"] == "quotes.note_revision_deleted"
    assert audit_service.events[0]["metadata_json"]["quote_id"] == str(quote_id)
    assert audit_service.events[0]["metadata_json"]["revision_id"] == str(revision.id)


@pytest.mark.asyncio
async def test_user_cannot_delete_another_users_note_revision(
    app: FastAPI,
    client: AsyncClient,
    override_dependencies: tuple[MockQuoteNoteService, MockAuditLogService, MockSession],
) -> None:
    note_service, audit_service, session = override_dependencies
    quote_id = uuid4()
    other_user_id = uuid4()
    current_user = make_note_user(permissions=["quote_notes.update"])
    app.dependency_overrides[get_current_user] = lambda: current_user
    revision = await note_service.update_note(
        quote_id=quote_id,
        content="<p>Ghi chú của người khác</p>",
        author_id=other_user_id,
    )

    response = await client.delete(
        f"/api/v1/quotes/{quote_id}/notes/revisions/{revision.id}",
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Bạn chỉ được sửa hoặc xóa ghi chú do chính mình tạo."
    assert audit_service.events == []
    assert session.committed is False
