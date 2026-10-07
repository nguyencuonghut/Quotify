import { apiRequest } from '@/api/http'
import {
  mapMaterialItemDtoToDomain,
  mapMaterialListDtoToDomain,
  mapSettingsDtoToDomain,
} from '@/api/price-alert-settings.mappers'
import type {
  MaterialFreshnessUpdatePayload,
  MaterialThresholdDomain,
  MaterialThresholdItemDto,
  MaterialThresholdListDomain,
  MaterialThresholdListDto,
  MaterialThresholdListQuery,
  MaterialThresholdUpdatePayload,
  PriceAlertSettingsDomain,
  PriceAlertSettingsDto,
  PriceAlertSettingsUpdatePayload,
} from '@/types/price-alert-settings'

export function getPriceAlertSettings(
  accessToken?: string | null,
): Promise<PriceAlertSettingsDomain> {
  return apiRequest<PriceAlertSettingsDto>('/price-alert-settings', {
    accessToken,
  }).then(mapSettingsDtoToDomain)
}

export function updatePriceAlertSettings(
  payload: PriceAlertSettingsUpdatePayload,
  accessToken?: string | null,
): Promise<PriceAlertSettingsDomain> {
  return apiRequest<PriceAlertSettingsDto>('/price-alert-settings', {
    method: 'PUT',
    body: JSON.stringify(payload),
    accessToken,
  }).then(mapSettingsDtoToDomain)
}

export function listMaterialThresholds(
  params: MaterialThresholdListQuery,
  accessToken?: string | null,
): Promise<MaterialThresholdListDomain> {
  const query = new URLSearchParams()
  query.append('limit', String(params.limit))
  query.append('offset', String(params.offset))
  if (params.search) {
    query.append('search', params.search)
  }
  if (params.sort) {
    query.append('sort', params.sort)
    query.append('order', params.order ?? 'asc')
  }
  return apiRequest<MaterialThresholdListDto>(
    `/price-alert-settings/materials?${query.toString()}`,
    { accessToken },
  ).then(mapMaterialListDtoToDomain)
}

interface MaterialThresholdPutDto {
  material_id: string
  override: MaterialThresholdItemDto['override']
  effective: MaterialThresholdItemDto['effective']
}

/** PUT trả về chỉ gồm ghi đè và ngưỡng hiệu lực; ghép lại với dòng đang có để dựng nhãn. */
export function putMaterialThreshold(
  current: MaterialThresholdDomain,
  payload: MaterialThresholdUpdatePayload,
  accessToken?: string | null,
): Promise<MaterialThresholdDomain> {
  return apiRequest<MaterialThresholdPutDto>(
    `/price-alert-settings/materials/${current.materialId}`,
    { method: 'PUT', body: JSON.stringify(payload), accessToken },
  ).then((dto) =>
    mapMaterialItemDtoToDomain({
      material_id: dto.material_id,
      code: current.code,
      name: current.name,
      override: dto.override,
      effective: dto.effective,
    }),
  )
}

export function putMaterialFreshness(
  materialId: string,
  payload: MaterialFreshnessUpdatePayload,
  accessToken?: string | null,
): Promise<void> {
  return apiRequest<unknown>(`/price-alert-settings/materials/${materialId}/freshness`, {
    method: 'PUT',
    body: JSON.stringify(payload),
    accessToken,
  }).then(() => undefined)
}

export function deleteMaterialFreshness(
  materialId: string,
  accessToken?: string | null,
): Promise<void> {
  return apiRequest<void>(`/price-alert-settings/materials/${materialId}/freshness`, {
    method: 'DELETE',
    accessToken,
  })
}

export function deleteMaterialThreshold(
  materialId: string,
  accessToken?: string | null,
): Promise<void> {
  return apiRequest<void>(`/price-alert-settings/materials/${materialId}`, {
    method: 'DELETE',
    accessToken,
  })
}
