from uuid import UUID, uuid4
from datetime import datetime, UTC
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.quote import Quote
from app.models.quote_note import QuoteNote
from app.models.quote_note_revision import QuoteNoteRevision
from app.utils.sanitizer import sanitize_html


class QuoteNoteService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_note_by_quote_id(self, quote_id: UUID) -> QuoteNote | None:
        stmt = (
            select(QuoteNote)
            .where(QuoteNote.quote_id == quote_id)
            .options(
                selectinload(QuoteNote.revisions).selectinload(QuoteNoteRevision.author)
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_note(
        self,
        *,
        quote_id: UUID,
        content: str,
        author_id: UUID,
    ) -> QuoteNoteRevision:
        # Check if the Quote exists
        quote = await self.db.get(Quote, quote_id)
        if not quote:
            raise ValueError("Quote not found")

        # Sanitize HTML (this also enforces size limit validation)
        cleaned_content = sanitize_html(content)

        # Check if QuoteNote already exists for this quote
        stmt = select(QuoteNote).where(QuoteNote.quote_id == quote_id)
        note = (await self.db.execute(stmt)).scalar_one_or_none()

        if not note:
            # Create new QuoteNote
            note = QuoteNote(
                id=uuid4(),
                quote_id=quote_id,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            self.db.add(note)
            revision_number = 1
        else:
            # Increment revision number
            rev_stmt = select(func.max(QuoteNoteRevision.revision_number)).where(
                QuoteNoteRevision.note_id == note.id
            )
            max_rev = (await self.db.execute(rev_stmt)).scalar_one_or_none() or 0
            revision_number = max_rev + 1
            note.updated_at = datetime.now(UTC)

        # Create new QuoteNoteRevision
        revision = QuoteNoteRevision(
            id=uuid4(),
            note_id=note.id,
            revision_number=revision_number,
            content=cleaned_content,
            author_id=author_id,
            created_at=datetime.now(UTC),
        )
        self.db.add(revision)

        await self.db.flush()

        return revision

    async def update_revision(
        self,
        *,
        revision_id: UUID,
        content: str,
    ) -> QuoteNoteRevision:
        cleaned_content = sanitize_html(content)
        stmt = (
            select(QuoteNoteRevision)
            .where(QuoteNoteRevision.id == revision_id)
            .options(selectinload(QuoteNoteRevision.author))
        )
        revision = (await self.db.execute(stmt)).scalar_one_or_none()
        if not revision:
            raise ValueError("Revision not found")

        revision.content = cleaned_content
        note = await self.db.get(QuoteNote, revision.note_id)
        if note:
            note.updated_at = datetime.now(UTC)

        await self.db.flush()
        return revision

    async def delete_revision(
        self,
        *,
        revision_id: UUID,
    ) -> None:
        revision = await self.db.get(QuoteNoteRevision, revision_id)
        if not revision:
            raise ValueError("Revision not found")

        note_id = revision.note_id
        await self.db.delete(revision)

        # Check if any revisions remain for this note
        stmt = select(func.count(QuoteNoteRevision.id)).where(QuoteNoteRevision.note_id == note_id)
        count = (await self.db.execute(stmt)).scalar() or 0
        
        # We need to deduct 1 because the current revision deletion might only count after commit,
        # but SQLAlchemy in-session state count might already exclude it depending on cascade and flush.
        # Since we just called delete(revision) and haven't flushed yet, count might still be 1.
        # To be safe, let's flush first, then check count.
        await self.db.flush()
        
        count_stmt = select(func.count(QuoteNoteRevision.id)).where(QuoteNoteRevision.note_id == note_id)
        count = (await self.db.execute(count_stmt)).scalar() or 0
        if count == 0:
            note = await self.db.get(QuoteNote, note_id)
            if note:
                await self.db.delete(note)
                await self.db.flush()
