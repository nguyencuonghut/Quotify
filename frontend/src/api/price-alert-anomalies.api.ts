import { apiRequest } from '@/api/http'
import {
  mapAnomalyListDtoToDomain,
  mapAnomalyReviewDtoToDomain,
} from '@/api/price-alert-anomalies.mappers'
import type {
  AnomalyDecision,
  AnomalyListDomain,
  AnomalyListDto,
  AnomalyListQueryParams,
  AnomalyReviewDomain,
  AnomalyReviewDto,
} from '@/types/price-alert-anomalies'

export function listAnomalies(
  params: AnomalyListQueryParams,
  accessToken?: string | null,
): Promise<AnomalyListDomain> {
  const query = new URLSearchParams()
  query.append('status', params.status)
  query.append('limit', String(params.limit))
  query.append('offset', String(params.offset))
  if (params.materialId) {
    query.append('material_id', params.materialId)
  }

  return apiRequest<AnomalyListDto>(
    `/price-alerts/anomalies?${query.toString()}`,
    {
      accessToken,
    },
  ).then(mapAnomalyListDtoToDomain)
}

export function reviewAnomaly(
  id: string,
  decision: AnomalyDecision,
  accessToken?: string | null,
): Promise<AnomalyReviewDomain> {
  return apiRequest<AnomalyReviewDto>(`/price-alerts/anomalies/${id}/review`, {
    method: 'POST',
    body: JSON.stringify({ decision }),
    accessToken,
  }).then(mapAnomalyReviewDtoToDomain)
}
