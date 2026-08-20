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
  MaterialLookupDto,
  MaterialPayload,
  MaterialTypeDomain,
  MaterialTypeDto,
  MaterialTypeListDto,
  MaterialTypeListDomain,
  MaterialTypeLookupDto,
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

// Toàn bộ loại vật tư active, không phân trang — dùng cho dropdown lọc/gán
// loại vật tư. KHÔNG dùng `listMaterialTypes` (bị giới hạn `limit<=100` của
// bảng quản trị) — cùng nhóm bug với dropdown NCC ở QuoteEditorPage.vue.
export function listMaterialTypesLookup(
  accessToken?: string | null,
): Promise<MaterialTypeDomain[]> {
  return apiRequest<MaterialTypeLookupDto>('/material-types/lookup', { accessToken }).then(
    (dto) => dto.items.map(mapMaterialTypeDtoToDomain),
  )
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

// Toàn bộ vật tư active, không phân trang — dùng cho dropdown chọn vật tư
// (vd. bộ lọc, form gán vật tư cho NCC). KHÔNG dùng `listMaterials` (bị giới
// hạn `limit<=100` của bảng quản trị) — cùng nhóm bug với dropdown NCC ở
// QuoteEditorPage.vue (NCC xếp sau vị trí 100 theo tên "biến mất" khỏi
// dropdown dù đang active).
export function listMaterialsLookup(accessToken?: string | null): Promise<MaterialDomain[]> {
  return apiRequest<MaterialLookupDto>('/materials/lookup', { accessToken }).then((dto) =>
    dto.items.map(mapMaterialDtoToDomain),
  )
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
