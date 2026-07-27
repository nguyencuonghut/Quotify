import type {
  ImportJobDto,
  ImportJobDomain,
  ExportJobDto,
  ExportJobDomain,
} from '@/types/jobs'
import { mapFileDtoToDomain } from './files.mappers'

export function mapImportJobDtoToDomain(dto: ImportJobDto): ImportJobDomain {
  return {
    id: dto.id,
    fileId: dto.file_id,
    status: dto.status,
    totalRows: dto.total_rows,
    processedRows: dto.processed_rows,
    failedRows: dto.failed_rows,
    errorSummary: dto.error_summary,
    errorsJson: dto.errors_json,
    createdById: dto.created_by_id,
    createdAt: new Date(dto.created_at),
    updatedAt: new Date(dto.updated_at),
    file: dto.file ? mapFileDtoToDomain(dto.file) : null,
  }
}

export function mapExportJobDtoToDomain(dto: ExportJobDto): ExportJobDomain {
  return {
    id: dto.id,
    status: dto.status,
    fileId: dto.file_id,
    filters: dto.filters,
    errorSummary: dto.error_summary,
    createdById: dto.created_by_id,
    createdAt: new Date(dto.created_at),
    updatedAt: new Date(dto.updated_at),
    file: dto.file ? mapFileDtoToDomain(dto.file) : null,
  }
}
