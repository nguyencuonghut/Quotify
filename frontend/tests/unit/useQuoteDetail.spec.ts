import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useQuoteDetail } from '@/composables/useQuoteDetail'
import { useAuthStore } from '@/stores/auth.store'

const quotesApiMock = vi.hoisted(() => ({
  getQuote: vi.fn(),
  confirmVersion: vi.fn(),
  toggleLinePurchase: vi.fn(),
  uploadSourceFile: vi.fn(),
  getQuoteNote: vi.fn(),
  updateQuoteNote: vi.fn(),
  updateQuoteNoteRevision: vi.fn(),
  deleteQuoteNoteRevision: vi.fn(),
}))

vi.mock('@/api/quotes.api', () => quotesApiMock)

describe('useQuoteDetail', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()

    const authStore = useAuthStore()
    authStore.accessToken = 'mock-token'
  })

  it('initializes note states correctly', () => {
    const detail = useQuoteDetail('mock-token')

    expect(detail.note.value).toBeNull()
    expect(detail.isNoteLoading.value).toBe(false)
    expect(detail.isSavingNote.value).toBe(false)
    expect(detail.noteErrorMsg.value).toBeNull()
  })

  it('loads note along with quote details', async () => {
    const mockQuote = {
      id: 'quote-123',
      supplierId: 'supp-1',
      supplierName: 'ABC Corp',
      supplierCode: 'ABC',
      createdById: null,
      createdAt: '2026-07-28T00:00:00Z',
      updatedAt: '2026-07-28T00:00:00Z',
      versions: [
        {
          id: 'v1',
          quoteId: 'quote-123',
          versionNumber: 1,
          receivedDate: '2026-07-28',
          status: 'draft',
          fileId: null,
          isBackfilled: false,
          backfillReason: null,
          createdById: null,
          confirmedAt: null,
          confirmedById: null,
          createdAt: '2026-07-28T00:00:00Z',
          updatedAt: '2026-07-28T00:00:00Z',
          lines: [],
        },
      ],
    }

    const mockNote = {
      id: 'note-456',
      quoteId: 'quote-123',
      createdAt: '2026-07-28T00:00:00Z',
      updatedAt: '2026-07-28T00:00:00Z',
      revisions: [
        {
          id: 'rev-1',
          revisionNumber: 1,
          content: '<p>Standard Market conditions</p>',
          authorId: 'user-1',
          authorName: 'Admin User',
          createdAt: '2026-07-28T00:00:00Z',
        },
      ],
    }

    quotesApiMock.getQuote.mockResolvedValue(mockQuote)
    quotesApiMock.getQuoteNote.mockResolvedValue(mockNote)

    const detail = useQuoteDetail('mock-token')
    await detail.loadQuote('quote-123')

    expect(quotesApiMock.getQuote).toHaveBeenCalledWith('quote-123', 'mock-token')
    expect(quotesApiMock.getQuoteNote).toHaveBeenCalledWith('quote-123', 'mock-token')
    expect(detail.quote.value).toEqual(mockQuote)
    expect(detail.note.value).toEqual(mockNote)
  })

  it('can update quote note and prepend new revision to list', async () => {
    const quoteId = 'quote-123'
    const newContent = '<p>New Market shift detected</p>'
    const mockRevision = {
      id: 'rev-2',
      revisionNumber: 2,
      content: newContent,
      authorId: 'user-1',
      authorName: 'Admin User',
      createdAt: '2026-07-28T01:00:00Z',
    }

    // Set existing note state
    const detail = useQuoteDetail('mock-token')
    detail.note.value = {
      id: 'note-456',
      quoteId,
      createdAt: '2026-07-28T00:00:00Z',
      updatedAt: '2026-07-28T00:00:00Z',
      revisions: [
        {
          id: 'rev-1',
          revisionNumber: 1,
          content: '<p>Standard Market conditions</p>',
          authorId: 'user-1',
          authorName: 'Admin User',
          createdAt: '2026-07-28T00:00:00Z',
        },
      ],
    }

    quotesApiMock.updateQuoteNote.mockResolvedValue(mockRevision)

    const rev = await detail.handleUpdateNote(quoteId, newContent)

    expect(quotesApiMock.updateQuoteNote).toHaveBeenCalledWith(quoteId, newContent, 'mock-token')
    expect(rev).toEqual(mockRevision)
    
    // Check that revision was prepended
    expect(detail.note.value?.revisions).toHaveLength(2)
    expect(detail.note.value?.revisions[0]).toEqual(mockRevision)
    expect(detail.note.value?.updatedAt).toBe(mockRevision.createdAt)
  })

  it('can update a specific note revision content', async () => {
    const quoteId = 'quote-123'
    const revisionId = 'rev-1'
    const updatedContent = '<p>Updated content</p>'
    const mockRevision = {
      id: revisionId,
      revisionNumber: 1,
      content: updatedContent,
      authorId: 'user-1',
      authorName: 'Admin User',
      createdAt: '2026-07-28T00:00:00Z',
    }

    const detail = useQuoteDetail('mock-token')
    detail.note.value = {
      id: 'note-456',
      quoteId,
      createdAt: '2026-07-28T00:00:00Z',
      updatedAt: '2026-07-28T00:00:00Z',
      revisions: [
        {
          id: revisionId,
          revisionNumber: 1,
          content: '<p>Old content</p>',
          authorId: 'user-1',
          authorName: 'Admin User',
          createdAt: '2026-07-28T00:00:00Z',
        },
      ],
    }

    quotesApiMock.updateQuoteNoteRevision.mockResolvedValue(mockRevision)

    const rev = await detail.handleUpdateNoteRevision(quoteId, revisionId, updatedContent)

    expect(quotesApiMock.updateQuoteNoteRevision).toHaveBeenCalledWith(quoteId, revisionId, updatedContent, 'mock-token')
    expect(rev).toEqual(mockRevision)
    expect(detail.note.value?.revisions[0].content).toBe(updatedContent)
  })

  it('can delete a specific note revision and clean state when empty', async () => {
    const quoteId = 'quote-123'
    const revisionId = 'rev-1'

    const detail = useQuoteDetail('mock-token')
    detail.note.value = {
      id: 'note-456',
      quoteId,
      createdAt: '2026-07-28T00:00:00Z',
      updatedAt: '2026-07-28T00:00:00Z',
      revisions: [
        {
          id: revisionId,
          revisionNumber: 1,
          content: '<p>Content</p>',
          authorId: 'user-1',
          authorName: 'Admin User',
          createdAt: '2026-07-28T00:00:00Z',
        },
      ],
    }

    quotesApiMock.deleteQuoteNoteRevision.mockResolvedValue(undefined)

    await detail.handleDeleteNoteRevision(quoteId, revisionId)

    expect(quotesApiMock.deleteQuoteNoteRevision).toHaveBeenCalledWith(quoteId, revisionId, 'mock-token')
    expect(detail.note.value?.id).toBe('')
    expect(detail.note.value?.revisions).toHaveLength(0)
  })
})
