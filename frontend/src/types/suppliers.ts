import type { CatalogStatus } from '@/types/materials'

export type SupplierType = 'domestic' | 'international'

export interface SupplierContactDto {
  id: string
  name: string
  title: string | null
  email: string | null
  phone: string | null
  status: CatalogStatus
  created_at: string
  updated_at: string
}

export interface SupplierMaterialDto {
  material_id: string
  material_code: string
  material_name: string
}

export interface SupplierDto {
  id: string
  code: string
  name: string
  supplier_type: SupplierType[]
  status: CatalogStatus
  tax_code: string | null
  address: string | null
  note: string | null
  contacts: SupplierContactDto[]
  materials: SupplierMaterialDto[]
  created_at: string
  updated_at: string
}

export interface SupplierContactDomain {
  id: string
  name: string
  title: string | null
  email: string | null
  phone: string | null
  status: CatalogStatus
  createdAt: string
  updatedAt: string
}

export interface SupplierMaterialDomain {
  materialId: string
  materialCode: string
  materialName: string
}

export interface SupplierDomain {
  id: string
  code: string
  name: string
  supplierType: SupplierType[]
  status: CatalogStatus
  taxCode: string | null
  address: string | null
  note: string | null
  contacts: SupplierContactDomain[]
  materials: SupplierMaterialDomain[]
  createdAt: string
  updatedAt: string
}

export interface SupplierContactPayload {
  name: string
  title: string | null
  email: string | null
  phone: string | null
  status: CatalogStatus
}

export interface SupplierPayload {
  code: string
  name: string
  supplier_type: SupplierType[]
  status: CatalogStatus
  tax_code: string | null
  address: string | null
  note: string | null
  contacts: SupplierContactPayload[]
  material_ids: string[]
}

export interface SupplierListQueryParams {
  limit: number
  offset: number
  search?: string
  supplier_type?: SupplierType | ''
  status?: CatalogStatus | ''
  sort_by: string
  sort_order: string
}

export interface SupplierListDto {
  items: SupplierDto[]
  total: number
}

export interface SupplierListDomain {
  items: SupplierDomain[]
  total: number
}

export interface SupplierLookupDto {
  items: SupplierDto[]
}
