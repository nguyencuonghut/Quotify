import type { ExchangeRateDomain, ExchangeRateDto } from '@/types/exchange-rates'

export function mapExchangeRateDtoToDomain(
  dto: ExchangeRateDto,
): ExchangeRateDomain {
  return {
    currency: dto.currency,
    rate: dto.rate,
    source: dto.source,
    retrievedAt: dto.retrieved_at,
  }
}
