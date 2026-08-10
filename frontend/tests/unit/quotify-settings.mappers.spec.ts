import { describe, expect, it } from 'vitest'

import { mapExchangeRateDtoToDomain } from '@/api/exchange-rates.mappers'
import { mapQuotifySettingsDtoToDomain } from '@/api/quotify-settings.mappers'
import type { ExchangeRateDto } from '@/types/exchange-rates'
import type { QuotifySettingsDto } from '@/types/quotify-settings'

describe('quotify settings mappers', () => {
  it('maps settings dto to frontend domain fields', () => {
    const dto: QuotifySettingsDto = {
      id: 'settings-1',
      import_tax_rate_percent: '5.00',
      processing_cost_vnd_per_kg: '200.00',
      updated_by_id: 'user-1',
      created_at: '2026-07-28T01:00:00+00:00',
      updated_at: '2026-07-28T02:00:00+00:00',
    }

    expect(mapQuotifySettingsDtoToDomain(dto)).toEqual({
      id: 'settings-1',
      importTaxRatePercent: '5.00',
      processingCostVndPerKg: '200.00',
      updatedById: 'user-1',
      createdAt: '2026-07-28T01:00:00+00:00',
      updatedAt: '2026-07-28T02:00:00+00:00',
    })
  })

  it('maps usd sell rate dto to frontend domain fields', () => {
    const dto: ExchangeRateDto = {
      currency: 'USD',
      rate: '26100.00',
      source: 'Vietcombank USD bán ra',
      retrieved_at: '2026-07-28T08:06:00+07:00',
    }

    expect(mapExchangeRateDtoToDomain(dto)).toEqual({
      currency: 'USD',
      rate: '26100.00',
      source: 'Vietcombank USD bán ra',
      retrievedAt: '2026-07-28T08:06:00+07:00',
    })
  })
})
