export interface FileDto {
  id: string
  filename: string
  content_type: string
  size_bytes: number
  is_public: boolean
  uploaded_by_id: string | null
  created_at: string
  url: string
}

export interface FileDomain {
  id: string
  filename: string
  contentType: string
  sizeBytes: number
  isPublic: boolean
  uploadedById: string | null
  createdAt: Date
  url: string
}

export interface FileListQueryParams {
  limit: number
  offset: number
  search?: string
}
