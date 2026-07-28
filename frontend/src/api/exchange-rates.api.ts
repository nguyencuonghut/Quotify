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
