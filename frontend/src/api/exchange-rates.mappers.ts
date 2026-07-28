import type { ExchangeRateDomain, ExchangeRateDto } from '@/types/exchange-rates'

export function mapExchangeRateDtoToDomain(
  dto: ExchangeRateDto,
): ExchangeRateDomain {
  return {
    currency: dto.currency,
    rate: dto.rate !== null && dto.rate !== undefined ? Number(dto.rate) : null,
    source: dto.source,
    retrievedAt: dto.retrieved_at,
  }
}
