import { apiRequest } from '@/api/http'
import {
  mapSupplierDtoToDomain,
  mapSupplierListDtoToDomain,
  mapSupplierLookupDtoToDomain,
} from '@/api/suppliers.mappers'
import type {
  SupplierDomain,
  SupplierDto,
  SupplierListDomain,
  SupplierListDto,
  SupplierListQueryParams,
  SupplierLookupDto,
  SupplierPayload,
} from '@/types/suppliers'

function buildSupplierQuery(params: SupplierListQueryParams): string {
  const query = new URLSearchParams()
  query.append('limit', String(params.limit))
  query.append('offset', String(params.offset))
  if (params.search) {
    query.append('search', params.search)
  }
  if (params.supplier_type) {
    query.append('supplier_type', params.supplier_type)
  }
  if (params.status) {
    query.append('status', params.status)
  }
  query.append('sort_by', params.sort_by)
  query.append('sort_order', params.sort_order)
  return query.toString()
}

export function listSuppliers(
  params: SupplierListQueryParams,
  accessToken?: string | null,
): Promise<SupplierListDomain> {
  return apiRequest<SupplierListDto>(`/suppliers?${buildSupplierQuery(params)}`, {
    accessToken,
  }).then(mapSupplierListDtoToDomain)
}

export function lookupSuppliersByMaterial(
  materialId: string,
  accessToken?: string | null,
): Promise<SupplierDomain[]> {
  return apiRequest<SupplierLookupDto>(`/suppliers/lookup?material_id=${materialId}`, {
    accessToken,
  }).then(mapSupplierLookupDtoToDomain)
}

export function createSupplier(
  payload: SupplierPayload,
  accessToken?: string | null,
): Promise<SupplierDomain> {
  return apiRequest<SupplierDto>('/suppliers', {
    method: 'POST',
    body: JSON.stringify(payload),
    accessToken,
  }).then(mapSupplierDtoToDomain)
}

export function getSupplier(
  supplierId: string,
  accessToken?: string | null,
): Promise<SupplierDomain> {
  return apiRequest<SupplierDto>(`/suppliers/${supplierId}`, {
    accessToken,
  }).then(mapSupplierDtoToDomain)
}

export function updateSupplier(

  supplierId: string,
  payload: SupplierPayload,
  accessToken?: string | null,
): Promise<SupplierDomain> {
  return apiRequest<SupplierDto>(`/suppliers/${supplierId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
    accessToken,
  }).then(mapSupplierDtoToDomain)
}

export function deleteSupplier(
  supplierId: string,
  accessToken?: string | null,
): Promise<void> {
  return apiRequest<void>(`/suppliers/${supplierId}`, {
    method: 'DELETE',
    accessToken,
  })
}
