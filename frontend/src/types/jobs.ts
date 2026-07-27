import type { FileDto, FileDomain } from './files'

export interface RowError {
  row: number
  email: string
  errors: string[]
}

export interface ImportJobDto {
  id: string
  file_id: string
  status: string
  total_rows: number
  processed_rows: number
  failed_rows: number
  error_summary: string | null
  errors_json: RowError[] | null
  created_by_id: string | null
  created_at: string
  updated_at: string
  file?: FileDto | null
}

export interface ImportJobDomain {
  id: string
  fileId: string
  status: string
  totalRows: number
  processedRows: number
  failedRows: number
  errorSummary: string | null
  errorsJson: RowError[] | null
  createdById: string | null
  createdAt: Date
  updatedAt: Date
  file?: FileDomain | null
}

export interface ExportJobDto {
  id: string
  status: string
  file_id: string | null
  filters: Record<string, unknown> | null
  error_summary: string | null
  created_by_id: string | null
  created_at: string
  updated_at: string
  file?: FileDto | null
}

export interface ExportJobDomain {
  id: string
  status: string
  fileId: string | null
  filters: Record<string, unknown> | null
  errorSummary: string | null
  createdById: string | null
  createdAt: Date
  updatedAt: Date
  file?: FileDomain | null
}
