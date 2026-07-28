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
        await self.db.commit()

        return revision
