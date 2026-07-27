import { apiRequest } from '@/api/http'
import { mapFileDtoToDomain } from '@/api/files.mappers'
import type { FileDomain, FileDto, FileListQueryParams } from '@/types/files'

export function listFiles(
  params: FileListQueryParams,
  accessToken?: string | null,
): Promise<{ items: FileDomain[]; total: number }> {
  const query = new URLSearchParams()
  query.append('limit', String(params.limit))
  query.append('offset', String(params.offset))
  if (params.search) {
    query.append('search', params.search)
  }

  return apiRequest<{ items: FileDto[]; total: number }>(
    `/files?${query.toString()}`,
    {
      accessToken,
    },
  ).then((dto) => ({
    items: dto.items.map(mapFileDtoToDomain),
    total: dto.total,
  }))
}

export function uploadFile(
  file: File,
  isPublic: boolean,
  accessToken?: string | null,
): Promise<FileDomain> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('is_public', String(isPublic))

  return apiRequest<FileDto>('/files/upload', {
    method: 'POST',
    body: formData,
    accessToken,
  }).then(mapFileDtoToDomain)
}

export function deleteFile(
  fileId: string,
  accessToken?: string | null,
): Promise<void> {
  return apiRequest<void>(`/files/${fileId}`, {
    method: 'DELETE',
    accessToken,
  })
}
