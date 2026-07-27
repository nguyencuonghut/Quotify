import type { FileDomain, FileDto } from '@/types/files'

export function mapFileDtoToDomain(dto: FileDto): FileDomain {
  return {
    id: dto.id,
    filename: dto.filename,
    contentType: dto.content_type,
    sizeBytes: dto.size_bytes,
    isPublic: dto.is_public,
    uploadedById: dto.uploaded_by_id,
    createdAt: new Date(dto.created_at),
    url: dto.url,
  }
}
