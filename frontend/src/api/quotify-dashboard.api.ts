import { apiRequest } from '@/api/http'
import {
  mapEntryKpisDtoToDomain,
  mapPriceTrendsDtoToDomain,
} from '@/api/quotify-dashboard.mappers'
import type {
  QuotifyDashboardQuery,
  QuotifyEntryKpis,
  QuotifyEntryKpisDto,
  QuotifyPriceTrends,
  QuotifyPriceTrendsDto,
} from '@/types/quotify-dashboard'

function buildDashboardQuery(params: QuotifyDashboardQuery): string {
  const query = new URLSearchParams()

  if (params.materialId) {
    query.append('material_id', params.materialId)
  }
  if (params.deliveryMonth) {
    query.append('delivery_month', params.deliveryMonth)
  }
  if (params.receivedDateStart) {
    query.append('received_date_start', params.receivedDateStart)
  }
  if (params.receivedDateEnd) {
    query.append('received_date_end', params.receivedDateEnd)
  }
  if (params.supplierType) {
    query.append('supplier_type', params.supplierType)
  }

  const serialized = query.toString()
  return serialized ? `?${serialized}` : ''
}

export function getQuotifyEntryKpis(
  params: QuotifyDashboardQuery,
  accessToken?: string | null,
): Promise<QuotifyEntryKpis> {
  return apiRequest<QuotifyEntryKpisDto>(
    `/dashboard/quotify/entry-kpis${buildDashboardQuery(params)}`,
    { accessToken },
  ).then(mapEntryKpisDtoToDomain)
}

export function getQuotifyPriceTrends(
  params: QuotifyDashboardQuery,
  accessToken?: string | null,
): Promise<QuotifyPriceTrends> {
  return apiRequest<QuotifyPriceTrendsDto>(
    `/dashboard/quotify/price-trends${buildDashboardQuery(params)}`,
    { accessToken },
  ).then(mapPriceTrendsDtoToDomain)
}
