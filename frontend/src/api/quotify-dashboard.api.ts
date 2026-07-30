import { apiRequest } from '@/api/http'
import {
  mapEntryKpisDtoToDomain,
  mapPriceTrendsDtoToDomain,
  mapWeeklyEntryActivityDtoToDomain,
} from '@/api/quotify-dashboard.mappers'
import type {
  QuotifyDashboardQuery,
  QuotifyEntryKpis,
  QuotifyEntryKpisDto,
  QuotifyPriceTrends,
  QuotifyPriceTrendsDto,
  QuotifyWeeklyEntryActivity,
  QuotifyWeeklyEntryActivityDto,
  QuotifyWeeklyEntryActivityQuery,
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

function buildWeeklyEntryActivityQuery(
  params: QuotifyWeeklyEntryActivityQuery,
): string {
  const query = new URLSearchParams()

  if (params.weekStart) {
    query.append('week_start', params.weekStart)
  }
  if (params.userId) {
    query.append('user_id', params.userId)
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

export function getQuotifyWeeklyEntryActivity(
  params: QuotifyWeeklyEntryActivityQuery,
  accessToken?: string | null,
): Promise<QuotifyWeeklyEntryActivity> {
  return apiRequest<QuotifyWeeklyEntryActivityDto>(
    `/dashboard/quotify/weekly-entry-activity${buildWeeklyEntryActivityQuery(params)}`,
    { accessToken },
  ).then(mapWeeklyEntryActivityDtoToDomain)
}
