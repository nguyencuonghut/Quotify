import { apiRequest, ApiError } from '@/api/http'
import { getApiBaseUrl } from '@/api/runtime'
import { mapImportJobDtoToDomain } from '@/api/jobs.mappers'
import type { ImportJobDomain, ImportJobDto } from '@/types/jobs'

export type CatalogImportEntityType =
  | 'material_types'
  | 'materials'
  | 'suppliers'

export function importCatalog(
  entityType: CatalogImportEntityType,
  file: File,
  accessToken?: string | null,
): Promise<ImportJobDomain> {
  const formData = new FormData()
  formData.append('file', file)

  return apiRequest<ImportJobDto>(`/catalog-imports/${entityType}`, {
    method: 'POST',
    body: formData,
    accessToken,
  }).then(mapImportJobDtoToDomain)
}

export function getCatalogImportJob(
  jobId: string,
  accessToken?: string | null,
): Promise<ImportJobDomain> {
  return apiRequest<ImportJobDto>(`/catalog-imports/${jobId}`, {
    accessToken,
  }).then(mapImportJobDtoToDomain)
}

export async function downloadCatalogImportTemplate(
  entityType: CatalogImportEntityType,
  accessToken?: string | null,
) {
  await downloadCatalogImportFile(
    `/catalog-imports/templates/${entityType}`,
    accessToken,
  )
}

export async function downloadCatalogImportErrorFile(
  jobId: string,
  accessToken?: string | null,
) {
  await downloadCatalogImportFile(
    `/catalog-imports/${jobId}/error-file`,
    accessToken,
  )
}

async function downloadCatalogImportFile(
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
  return match?.[1] ?? 'catalog-import.csv'
}
