import { apiRequest } from '@/api/http'
import {
  mapQuoteDtoToDomain,
  mapQuoteVersionDtoToDomain,
  mapQuoteLineDtoToDomain,
  mapQuoteNoteDtoToDomain,
} from '@/api/quotes.mappers'
import type {
  QuoteCreatePayload,
  QuoteDraftUpdatePayload,
  QuoteLineDomain,
  QuoteLineDto,
  QuoteLinePurchaseTogglePayload,
  QuoteVersionDomain,
  QuoteVersionDto,
  QuoteDomain,
  QuoteDto,
  QuoteNoteDomain,
  QuoteNoteDto,
  QuoteNoteRevisionDomain,
  QuoteNoteRevisionDto,
} from '@/types/quotes'

export function createQuote(
  payload: QuoteCreatePayload,
  accessToken?: string | null,
): Promise<QuoteDomain> {
  return apiRequest<QuoteDto>('/quotes', {
    method: 'POST',
    body: JSON.stringify(payload),
    accessToken,
  }).then(mapQuoteDtoToDomain)
}

export function getQuote(
  id: string,
  accessToken?: string | null,
): Promise<QuoteDomain> {
  return apiRequest<QuoteDto>(`/quotes/${id}`, {
    accessToken,
  }).then(mapQuoteDtoToDomain)
}

export function createVersion(
  id: string,
  payload: QuoteDraftUpdatePayload,
  accessToken?: string | null,
): Promise<QuoteVersionDomain> {
  return apiRequest<QuoteVersionDto>(`/quotes/${id}/versions`, {
    method: 'POST',
    body: JSON.stringify(payload),
    accessToken,
  }).then(mapQuoteVersionDtoToDomain)
}

export function updateDraft(
  id: string,
  versionId: string,
  payload: QuoteDraftUpdatePayload,
  accessToken?: string | null,
): Promise<QuoteVersionDomain> {
  return apiRequest<QuoteVersionDto>(`/quotes/${id}/versions/${versionId}/draft`, {
    method: 'PUT',
    body: JSON.stringify(payload),
    accessToken,
  }).then(mapQuoteVersionDtoToDomain)
}

export function confirmVersion(
  id: string,
  versionId: string,
  accessToken?: string | null,
): Promise<QuoteVersionDomain> {
  return apiRequest<QuoteVersionDto>(`/quotes/${id}/versions/${versionId}/confirm`, {
    method: 'POST',
    accessToken,
  }).then(mapQuoteVersionDtoToDomain)
}

export function toggleLinePurchase(
  id: string,
  lineId: string,
  purchase: boolean,
  accessToken?: string | null,
): Promise<QuoteLineDomain> {
  const payload: QuoteLinePurchaseTogglePayload = { purchase }
  return apiRequest<QuoteLineDto>(`/quotes/${id}/lines/${lineId}/purchase`, {
    method: 'PUT',
    body: JSON.stringify(payload),
    accessToken,
  }).then(mapQuoteLineDtoToDomain)
}

export function uploadSourceFile(
  id: string,
  versionId: string,
  file: File,
  accessToken?: string | null,
): Promise<QuoteVersionDomain> {
  const formData = new FormData()
  formData.append('file', file)

  return apiRequest<QuoteVersionDto>(`/quotes/${id}/versions/${versionId}/source-file`, {
    method: 'POST',
    body: formData,
    accessToken,
  }).then(mapQuoteVersionDtoToDomain)
}

export function getQuoteNote(
  quoteId: string,
  accessToken?: string | null,
): Promise<QuoteNoteDomain> {
  return apiRequest<QuoteNoteDto>(`/quotes/${quoteId}/notes`, {
    accessToken,
  })
    .then(mapQuoteNoteDtoToDomain)
    .catch((err: any) => {
      if (err.status === 404 || (err.message && err.message.includes('404'))) {
        return {
          id: '',
          quoteId,
          createdAt: '',
          updatedAt: '',
          revisions: [],
        }
      }
      throw err
    })
}

export function updateQuoteNote(
  quoteId: string,
  content: string,
  accessToken?: string | null,
): Promise<QuoteNoteRevisionDomain> {
  return apiRequest<QuoteNoteRevisionDto>(`/quotes/${quoteId}/notes`, {
    method: 'PUT',
    body: JSON.stringify({ content }),
    accessToken,
  }).then((r) => ({
    id: r.id,
    revisionNumber: r.revision_number,
    content: r.content,
    authorId: r.author_id,
    authorName: r.author_name,
    createdAt: r.created_at,
  }))
}

export function updateQuoteNoteRevision(
  quoteId: string,
  revisionId: string,
  content: string,
  accessToken?: string | null,
): Promise<QuoteNoteRevisionDomain> {
  return apiRequest<QuoteNoteRevisionDto>(`/quotes/${quoteId}/notes/revisions/${revisionId}`, {
    method: 'PATCH',
    body: JSON.stringify({ content }),
    accessToken,
  }).then((r) => ({
    id: r.id,
    revisionNumber: r.revision_number,
    content: r.content,
    authorId: r.author_id,
    authorName: r.author_name,
    createdAt: r.created_at,
  }))
}

export function deleteQuoteNoteRevision(
  quoteId: string,
  revisionId: string,
  accessToken?: string | null,
): Promise<void> {
  return apiRequest<void>(`/quotes/${quoteId}/notes/revisions/${revisionId}`, {
    method: 'DELETE',
    accessToken,
  })
}
