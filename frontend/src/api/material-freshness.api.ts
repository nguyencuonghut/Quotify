import { apiRequest } from '@/api/http'
import { mapMaterialFreshnessDtoToDomain } from '@/api/material-freshness.mappers'
import type {
  MaterialFreshness,
  MaterialFreshnessDto,
} from '@/types/material-freshness'

// `weekStart` là ngày YYYY-MM-DD bất kỳ trong tuần cần xem; bỏ trống thì backend dùng tuần hiện tại.
export function getMaterialFreshness(
  weekStart: string | null,
  accessToken?: string | null,
): Promise<MaterialFreshness> {
  const query = weekStart ? `?week_start=${encodeURIComponent(weekStart)}` : ''
  return apiRequest<MaterialFreshnessDto>(
    `/dashboard/quotify/material-freshness${query}`,
    {
      accessToken,
    },
  ).then(mapMaterialFreshnessDtoToDomain)
}
