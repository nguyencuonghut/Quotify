import { apiRequest } from '@/api/http'
import {
  mapImportJobDtoToDomain,
  mapExportJobDtoToDomain,
} from '@/api/jobs.mappers'
import type {
  ImportJobDomain,
  ImportJobDto,
  ExportJobDomain,
  ExportJobDto,
} from '@/types/jobs'

export function importUsers(
  file: File,
  accessToken?: string | null,
): Promise<ImportJobDomain> {
  const formData = new FormData()
  formData.append('file', file)

  return apiRequest<ImportJobDto>('/users/import', {
    method: 'POST',
    body: formData,
    accessToken,
  }).then(mapImportJobDtoToDomain)
}

export function listImportJobs(
  params: { limit: number; offset: number },
  accessToken?: string | null,
): Promise<{ items: ImportJobDomain[]; total: number }> {
  const query = new URLSearchParams()
  query.append('limit', String(params.limit))
  query.append('offset', String(params.offset))

  return apiRequest<{ items: ImportJobDto[]; total: number }>(
    `/users/import/jobs?${query.toString()}`,
    {
      accessToken,
    },
  ).then((dto) => ({
    items: dto.items.map(mapImportJobDtoToDomain),
    total: dto.total,
  }))
}

export function getImportJob(
  jobId: string,
  accessToken?: string | null,
): Promise<ImportJobDomain> {
  return apiRequest<ImportJobDto>(`/users/import/jobs/${jobId}`, {
    accessToken,
  }).then(mapImportJobDtoToDomain)
}

export function exportUsers(
  filters: { search?: string; status?: string },
  accessToken?: string | null,
): Promise<ExportJobDomain> {
  return apiRequest<ExportJobDto>('/users/export', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(filters),
    accessToken,
  }).then(mapExportJobDtoToDomain)
}

export function listExportJobs(
  params: { limit: number; offset: number },
  accessToken?: string | null,
): Promise<{ items: ExportJobDomain[]; total: number }> {
  const query = new URLSearchParams()
  query.append('limit', String(params.limit))
  query.append('offset', String(params.offset))

  return apiRequest<{ items: ExportJobDto[]; total: number }>(
    `/users/export/jobs?${query.toString()}`,
    {
      accessToken,
    },
  ).then((dto) => ({
    items: dto.items.map(mapExportJobDtoToDomain),
    total: dto.total,
  }))
}

export function getExportJob(
  jobId: string,
  accessToken?: string | null,
): Promise<ExportJobDomain> {
  return apiRequest<ExportJobDto>(`/users/export/jobs/${jobId}`, {
    accessToken,
  }).then(mapExportJobDtoToDomain)
}
