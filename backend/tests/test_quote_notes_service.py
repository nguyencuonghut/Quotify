from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.models import Quote
from app.models.quote_note import QuoteNote
from app.models.quote_note_revision import QuoteNoteRevision
from app.services.quote_note_service import QuoteNoteService


# Fake session mock
class FakeDbSession:
    def __init__(self):
        self.added = []
        self.committed = False
        self.quotes = {}
        self.notes = {}
        self.revisions = []

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, QuoteNote):
            self.notes[obj.id] = obj
        if isinstance(obj, QuoteNoteRevision):
            self.revisions.append(obj)

    async def commit(self):
        self.committed = True

    async def flush(self):
        pass

    async def get(self, model_class, id):
        if model_class == Quote:
            return self.quotes.get(id)
        if model_class == QuoteNote:
            return self.notes.get(id)
        if model_class == QuoteNoteRevision:
            for r in self.revisions:
                if r.id == id:
                    return r
        return None

    async def delete(self, obj):
        if isinstance(obj, QuoteNote):
            if obj.id in self.notes:
                del self.notes[obj.id]
        if isinstance(obj, QuoteNoteRevision):
            self.revisions = [r for r in self.revisions if r.id != obj.id]

    # Custom execute mock
    async def execute(self, statement):
        # We need this to mock the query finding QuoteNote by quote_id
        # and getting max revision_number of QuoteNoteRevision
        class FakeResult:
            def __init__(self, val):
                self._val = val
            def scalar_one_or_none(self):
                return self._val
            def scalars(self):
                return self
            def all(self):
                return self._val if isinstance(self._val, list) else [self._val]

        stmt_str = str(statement)
        if "quote_notes" in stmt_str and "quote_id" in stmt_str:
            # Finding QuoteNote by quote_id
            # Extract quote_id from bind params or return matching note
            # Let's return the first note matching quote_id
            for note in self.notes.values():
                return FakeResult(note)
            return FakeResult(None)

        if "quote_note_revisions" in stmt_str and "max" in stmt_str.lower():
            # Getting max revision_number
            # Return max revision_number from self.revisions
            if not self.revisions:
                return FakeResult(None)
            return FakeResult(max(r.revision_number for r in self.revisions))

        if "count" in stmt_str.lower() and "quote_note_revisions" in stmt_str:
            class ScalarResult:
                def __init__(self, val):
                    self._val = val
                def scalar(self):
                    return self._val
            return ScalarResult(len(self.revisions))

        if "quote_note_revisions" in stmt_str:
            # Querying a single revision by id in service methods
            return FakeResult(self.revisions[0] if self.revisions else None)

        return FakeResult(None)

@pytest.fixture
def fake_db():
    return FakeDbSession()

@pytest.fixture
def note_service(fake_db):
    return QuoteNoteService(fake_db)

@pytest.mark.asyncio
async def test_update_note_creates_new_note_and_first_revision(note_service, fake_db):
    quote_id = uuid4()
    author_id = uuid4()
    
    # Mock quote existence
    fake_db.quotes[quote_id] = Quote(id=quote_id)

    revision = await note_service.update_note(
        quote_id=quote_id,
        content="<p>Initial note content</p>",
        author_id=author_id
    )

    assert revision is not None
    assert revision.revision_number == 1
    assert revision.content == "<p>Initial note content</p>"
    assert revision.author_id == author_id
    assert fake_db.committed is False
    assert len(fake_db.notes) == 1
    assert len(fake_db.revisions) == 1

@pytest.mark.asyncio
async def test_update_note_appends_revision_increments_number(note_service, fake_db):
    quote_id = uuid4()
    author_id = uuid4()
    
    # 1. Setup existing note & version 1
    fake_db.quotes[quote_id] = Quote(id=quote_id)
    existing_note = QuoteNote(id=uuid4(), quote_id=quote_id)
    fake_db.notes[existing_note.id] = existing_note
    v1_revision = QuoteNoteRevision(
        id=uuid4(),
        note_id=existing_note.id,
        revision_number=1,
        content="<p>Version 1</p>",
        author_id=author_id
    )
    fake_db.revisions.append(v1_revision)

    # 2. Update note (creates revision 2)
    revision = await note_service.update_note(
        quote_id=quote_id,
        content="<p>Version 2 update</p>",
        author_id=author_id
    )

    assert revision.revision_number == 2
    assert revision.content == "<p>Version 2 update</p>"
    assert len(fake_db.revisions) == 2
    assert fake_db.committed is False

@pytest.mark.asyncio
async def test_update_note_sanitizes_html_xss(note_service, fake_db):
    quote_id = uuid4()
    author_id = uuid4()
    fake_db.quotes[quote_id] = Quote(id=quote_id)

    dangerous_content = '<p>Note <script>alert("XSS")</script> content <iframe src="hack"></iframe></p>'
    revision = await note_service.update_note(
        quote_id=quote_id,
        content=dangerous_content,
        author_id=author_id
    )

    # Script and iframe tags must be cleaned out by sanitizer
    assert "alert" not in revision.content
    assert "<script>" not in revision.content
    assert "<iframe>" not in revision.content
    assert "Note" in revision.content

@pytest.mark.asyncio
async def test_update_note_throws_error_if_payload_exceeds_limit(note_service, fake_db):
    quote_id = uuid4()
    author_id = uuid4()
    fake_db.quotes[quote_id] = Quote(id=quote_id)

    too_large_content = "<p>" + ("a" * 20480) + "</p>"
    with pytest.raises(ValueError, match="Payload size exceeds maximum allowed limit"):
        await note_service.update_note(
            quote_id=quote_id,
            content=too_large_content,
            author_id=author_id
        )

@pytest.mark.asyncio
async def test_update_revision_updates_content_and_sanitizes(note_service, fake_db):
    quote_id = uuid4()
    author_id = uuid4()
    
    # 1. Setup existing note and revision
    fake_db.quotes[quote_id] = Quote(id=quote_id)
    note = QuoteNote(id=uuid4(), quote_id=quote_id, created_at=datetime.now(UTC), updated_at=datetime.now(UTC))
    fake_db.notes[note.id] = note
    revision = QuoteNoteRevision(
        id=uuid4(),
        note_id=note.id,
        revision_number=1,
        content="<p>Old content</p>",
        author_id=author_id,
        created_at=datetime.now(UTC)
    )
    fake_db.revisions.append(revision)

    # 2. Update revision
    updated_rev = await note_service.update_revision(
        revision_id=revision.id,
        content="<p>New content <script>alert('XSS')</script></p>"
    )

    assert updated_rev.id == revision.id
    assert "alert" not in updated_rev.content
    assert "New content" in updated_rev.content
    assert updated_rev.content == "<p>New content </p>"

@pytest.mark.asyncio
async def test_delete_revision_deletes_and_cleans_note_if_empty(note_service, fake_db):
    quote_id = uuid4()
    author_id = uuid4()
    
    # 1. Setup existing note and revision
    fake_db.quotes[quote_id] = Quote(id=quote_id)
    note = QuoteNote(id=uuid4(), quote_id=quote_id, created_at=datetime.now(UTC), updated_at=datetime.now(UTC))
    fake_db.notes[note.id] = note
    revision = QuoteNoteRevision(
        id=uuid4(),
        note_id=note.id,
        revision_number=1,
        content="<p>Initial content</p>",
        author_id=author_id,
        created_at=datetime.now(UTC)
    )
    fake_db.revisions.append(revision)

    assert len(fake_db.revisions) == 1
    assert len(fake_db.notes) == 1

    # 2. Delete revision
    await note_service.delete_revision(revision_id=revision.id)

    assert len(fake_db.revisions) == 0
    # Because count of revisions is 0, note should also be deleted
    assert len(fake_db.notes) == 0
