import { apiRequest, ApiError } from '@/api/http'
import { getApiBaseUrl } from '@/api/runtime'
import { mapImportJobDtoToDomain } from '@/api/jobs.mappers'
import type { ImportJobDomain, ImportJobDto } from '@/types/jobs'

export function importQuoteBackfill(
  file: File,
  accessToken?: string | null,
): Promise<ImportJobDomain> {
  const formData = new FormData()
  formData.append('file', file)

  return apiRequest<ImportJobDto>('/quote-backfill-imports', {
    method: 'POST',
    body: formData,
    accessToken,
  }).then(mapImportJobDtoToDomain)
}

export function getQuoteBackfillImportJob(
  jobId: string,
  accessToken?: string | null,
): Promise<ImportJobDomain> {
  return apiRequest<ImportJobDto>(`/quote-backfill-imports/${jobId}`, {
    accessToken,
  }).then(mapImportJobDtoToDomain)
}

export async function downloadQuoteBackfillImportTemplate(
  accessToken?: string | null,
) {
  await downloadQuoteBackfillImportFile(
    '/quote-backfill-imports/template',
    accessToken,
  )
}

export async function downloadQuoteBackfillImportErrorFile(
  jobId: string,
  accessToken?: string | null,
) {
  await downloadQuoteBackfillImportFile(
    `/quote-backfill-imports/${jobId}/error-file`,
    accessToken,
  )
}

async function downloadQuoteBackfillImportFile(
  path: string,
  accessToken?: string | null,
) {
  const headers = new Headers()
  if (accessToken) {
    headers.set('Authorization', `Bearer ${accessToken}`)
  }

  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    headers,
    credentials: 'include',
  })
  if (!response.ok) {
    throw new ApiError(
      response.statusText || 'Không thể tải file import.',
      response.status,
    )
  }

  const blob = await response.blob()
  const filename = resolveFilename(response.headers.get('content-disposition'))
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  window.URL.revokeObjectURL(url)
}

function resolveFilename(contentDisposition: string | null) {
  const match = contentDisposition?.match(/filename="([^"]+)"/)
  return match?.[1] ?? 'quote-backfill-import.csv'
}
