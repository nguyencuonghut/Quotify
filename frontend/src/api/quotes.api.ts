import { apiRequest, ApiError } from '@/api/http'
import { getApiBaseUrl } from '@/api/runtime'
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

type QuotesQueryFilterParams = Record<string, string | number | boolean | null | undefined>

function buildQuotesQueryString(params: QuotesQueryFilterParams): string {
  const queryParams: Record<string, string> = {}
  Object.keys(params).forEach((key) => {
    if (params[key] !== undefined && params[key] !== null && params[key] !== '') {
      const snakeKey = key.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`)
      queryParams[snakeKey] = String(params[key])
    }
  })

  return new URLSearchParams(queryParams).toString()
}

export function getQuotesList(
  params: Record<string, any>,
  accessToken?: string | null,
): Promise<{ items: QuoteFlattenedDomain[]; total: number }> {
  const searchParams = buildQuotesQueryString(params)
  const url = `/quotes${searchParams ? `?${searchParams}` : ''}`

  return apiRequest<{ items: QuoteFlattenedDto[]; total: number }>(url, {
    method: 'GET',
    accessToken,
  }).then((res) => ({
    items: Array.isArray(res.items) ? res.items.map(mapQuoteFlattenedDtoToDomain) : [],
    total: res.total,
  }))
}

function resolveExportFilename(contentDisposition: string | null): string {
  const match = contentDisposition?.match(/filename="([^"]+)"/)
  return match?.[1] ?? 'bao_gia.xlsx'
}

// Tôn trọng nguyên bộ lọc đang áp dụng trên trang (cùng tham số với
// `getQuotesList`), nhưng dùng `fetch` thô thay vì `apiRequest` — cùng quy
// ước với `downloadQuoteBackfillImportTemplate`/`downloadQuoteBackfillImportErrorFile`
// (`quote-backfill-imports.api.ts`), vì phản hồi là file nhị phân
// (application/vnd...spreadsheetml.sheet), không phải JSON.
export async function downloadQuotesExport(
  params: QuotesQueryFilterParams,
  accessToken?: string | null,
): Promise<void> {
  const searchParams = buildQuotesQueryString(params)
  const url = `/quotes/export${searchParams ? `?${searchParams}` : ''}`

  const headers = new Headers()
  if (accessToken) {
    headers.set('Authorization', `Bearer ${accessToken}`)
  }

  const response = await fetch(`${getApiBaseUrl()}${url}`, {
    headers,
    credentials: 'include',
  })
  if (!response.ok) {
    throw new ApiError(
      response.statusText || 'Không thể xuất file Excel.',
      response.status,
    )
  }

  const blob = await response.blob()
  const filename = resolveExportFilename(response.headers.get('content-disposition'))
  const downloadUrl = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = downloadUrl
  link.download = filename
  link.click()
  window.URL.revokeObjectURL(downloadUrl)
}
