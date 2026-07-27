export type CatalogStatus = 'active' | 'inactive'

export interface MaterialTypeDto {
  id: string
  code: string
  name: string
  status: CatalogStatus
  note: string | null
  created_at: string
  updated_at: string
}

export interface MaterialTypeDomain {
  id: string
  code: string
  name: string
  status: CatalogStatus
  note: string | null
  createdAt: string
  updatedAt: string
}

export interface MaterialTypePayload {
  code: string
  name: string
  status: CatalogStatus
  note: string | null
}

export interface MaterialDto {
  id: string
  code: string
  name: string
  material_type_id: string
  material_type_code: string
  material_type_name: string
  status: CatalogStatus
  note: string | null
  created_at: string
  updated_at: string
}

export interface MaterialDomain {
  id: string
  code: string
  name: string
  materialTypeId: string
  materialTypeCode: string
  materialTypeName: string
  status: CatalogStatus
  note: string | null
  createdAt: string
  updatedAt: string
}

export interface MaterialPayload {
  code: string
  name: string
  material_type_id: string
  status: CatalogStatus
  note: string | null
}

export interface CatalogListQueryParams {
  limit: number
  offset: number
  search?: string
  status?: CatalogStatus | ''
  material_type_id?: string
  sort_by: string
  sort_order: string
}

export interface MaterialTypeListDto {
  items: MaterialTypeDto[]
  total: number
}

export interface MaterialTypeListDomain {
  items: MaterialTypeDomain[]
  total: number
}

export interface MaterialListDto {
  items: MaterialDto[]
  total: number
}

export interface MaterialListDomain {
  items: MaterialDomain[]
  total: number
}
