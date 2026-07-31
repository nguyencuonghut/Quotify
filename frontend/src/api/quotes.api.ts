import { apiRequest } from '@/api/http'
import {
  mapQuoteDtoToDomain,
  mapQuoteVersionDtoToDomain,
  mapQuoteLineDtoToDomain,
  mapQuoteNoteDtoToDomain,
  mapQuoteFlattenedDtoToDomain,
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
  QuoteFlattenedDto,
  QuoteFlattenedDomain,
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

export function deleteDraftVersion(
  id: string,
  versionId: string,
  accessToken?: string | null,
): Promise<void> {
  return apiRequest<void>(`/quotes/${id}/versions/${versionId}`, {
    method: 'DELETE',
    accessToken,
  })
}

export function toggleLinePurchase(
  id: string,
  lineId: string,
  purchase: boolean,
  purchaseDate?: string | null,
  accessToken?: string | null,
): Promise<QuoteLineDomain> {
  const payload: QuoteLinePurchaseTogglePayload = {
    purchase,
    purchase_date: purchaseDate,
  }
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
    authorAvatarUrl: r.author_avatar_url,
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
    authorAvatarUrl: r.author_avatar_url,
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

export function getQuotesList(
  params: Record<string, any>,
  accessToken?: string | null,
): Promise<{ items: QuoteFlattenedDomain[]; total: number }> {
  const queryParams: Record<string, string> = {}
  Object.keys(params).forEach((key) => {
    if (params[key] !== undefined && params[key] !== null && params[key] !== '') {
      const snakeKey = key.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`)
      queryParams[snakeKey] = String(params[key])
    }
  })

  const searchParams = new URLSearchParams(queryParams).toString()
  const url = `/quotes${searchParams ? `?${searchParams}` : ''}`

  return apiRequest<{ items: QuoteFlattenedDto[]; total: number }>(url, {
    method: 'GET',
    accessToken,
  }).then((res) => ({
    items: Array.isArray(res.items) ? res.items.map(mapQuoteFlattenedDtoToDomain) : [],
    total: res.total,
  }))
}
