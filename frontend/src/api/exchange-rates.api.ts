import { apiRequest } from '@/api/http'
import { mapExchangeRateDtoToDomain } from '@/api/exchange-rates.mappers'
import type { ExchangeRateDomain, ExchangeRateDto } from '@/types/exchange-rates'

export function getUsdSellRateToday(
  accessToken?: string | null,
): Promise<ExchangeRateDomain> {
  return apiRequest<ExchangeRateDto>('/exchange-rates/usd-sell/today', {
    accessToken,
  }).then(mapExchangeRateDtoToDomain)
}

// Tỷ giá theo NGÀY BẤT KỲ trong quá khứ — dùng API JSON không chính thức của
// Vietcombank (khác nguồn với /usd-sell/today), có thể lỗi/không có dữ liệu
// cho một số ngày; luôn cần phương án nhập tay dự phòng ở tầng gọi.
export function getUsdSellRateForDate(
  date: string, // YYYY-MM-DD
  accessToken?: string | null,
): Promise<ExchangeRateDomain> {
  return apiRequest<ExchangeRateDto>(`/exchange-rates/usd-sell/by-date/${date}`, {
    accessToken,
  }).then(mapExchangeRateDtoToDomain)
}
