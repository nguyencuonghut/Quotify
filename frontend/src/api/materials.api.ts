import { apiRequest } from '@/api/http'
import {
  mapMaterialDtoToDomain,
  mapMaterialListDtoToDomain,
  mapMaterialTypeDtoToDomain,
  mapMaterialTypeListDtoToDomain,
} from '@/api/materials.mappers'
import type {
  CatalogListQueryParams,
  MaterialDomain,
  MaterialDto,
  MaterialListDto,
  MaterialListDomain,
  MaterialPayload,
  MaterialTypeDomain,
  MaterialTypeDto,
  MaterialTypeListDto,
  MaterialTypeListDomain,
  MaterialTypePayload,
} from '@/types/materials'

function buildCatalogQuery(params: CatalogListQueryParams): string {
  const query = new URLSearchParams()
  query.append('limit', String(params.limit))
  query.append('offset', String(params.offset))
  if (params.search) {
    query.append('search', params.search)
  }
  if (params.status) {
    query.append('status', params.status)
  }
  if (params.material_type_id) {
    query.append('material_type_id', params.material_type_id)
  }
  query.append('sort_by', params.sort_by)
  query.append('sort_order', params.sort_order)
  return query.toString()
}

export function listMaterialTypes(
  params: CatalogListQueryParams,
  accessToken?: string | null,
): Promise<MaterialTypeListDomain> {
  return apiRequest<MaterialTypeListDto>(
    `/material-types?${buildCatalogQuery(params)}`,
    { accessToken },
  ).then(mapMaterialTypeListDtoToDomain)
}

export function listMaterialTypesLookup(
  accessToken?: string | null,
): Promise<MaterialTypeDomain[]> {
  return apiRequest<MaterialTypeListDto>(
    '/material-types?limit=100&sort_by=code&sort_order=asc',
    { accessToken },
  ).then((dto) => dto.items.map(mapMaterialTypeDtoToDomain))
}

export function createMaterialType(
  payload: MaterialTypePayload,
  accessToken?: string | null,
): Promise<MaterialTypeDomain> {
  return apiRequest<MaterialTypeDto>('/material-types', {
    method: 'POST',
    body: JSON.stringify(payload),
    accessToken,
  }).then(mapMaterialTypeDtoToDomain)
}

export function updateMaterialType(
  materialTypeId: string,
  payload: MaterialTypePayload,
  accessToken?: string | null,
): Promise<MaterialTypeDomain> {
  return apiRequest<MaterialTypeDto>(`/material-types/${materialTypeId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
    accessToken,
  }).then(mapMaterialTypeDtoToDomain)
}

export function deleteMaterialType(
  materialTypeId: string,
  accessToken?: string | null,
): Promise<void> {
  return apiRequest<void>(`/material-types/${materialTypeId}`, {
    method: 'DELETE',
    accessToken,
  })
}

export function listMaterials(
  params: CatalogListQueryParams,
  accessToken?: string | null,
): Promise<MaterialListDomain> {
  return apiRequest<MaterialListDto>(`/materials?${buildCatalogQuery(params)}`, {
    accessToken,
  }).then(mapMaterialListDtoToDomain)
}

export function listMaterialsLookup(
  accessToken?: string | null,
  search = '',
): Promise<MaterialDomain[]> {
  const params: CatalogListQueryParams = {
    limit: 100,
    offset: 0,
    search,
    status: 'active',
    sort_by: 'code',
    sort_order: 'asc',
  }
  return apiRequest<MaterialListDto>(`/materials?${buildCatalogQuery(params)}`, {
    accessToken,
  }).then((dto) => dto.items.map(mapMaterialDtoToDomain))
}

export function createMaterial(
  payload: MaterialPayload,
  accessToken?: string | null,
): Promise<MaterialDomain> {
  return apiRequest<MaterialDto>('/materials', {
    method: 'POST',
    body: JSON.stringify(payload),
    accessToken,
  }).then(mapMaterialDtoToDomain)
}

export function updateMaterial(
  materialId: string,
  payload: MaterialPayload,
  accessToken?: string | null,
): Promise<MaterialDomain> {
  return apiRequest<MaterialDto>(`/materials/${materialId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
    accessToken,
  }).then(mapMaterialDtoToDomain)
}

export function deleteMaterial(
  materialId: string,
  accessToken?: string | null,
): Promise<void> {
  return apiRequest<void>(`/materials/${materialId}`, {
    method: 'DELETE',
    accessToken,
  })
}
