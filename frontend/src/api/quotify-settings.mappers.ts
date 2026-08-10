import type {
  QuotifySettingsDomain,
  QuotifySettingsDto,
} from '@/types/quotify-settings'

export function mapQuotifySettingsDtoToDomain(
  dto: QuotifySettingsDto,
): QuotifySettingsDomain {
  return {
    id: dto.id,
    importTaxRatePercent: dto.import_tax_rate_percent,
    processingCostVndPerKg: dto.processing_cost_vnd_per_kg,
    updatedById: dto.updated_by_id,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  }
}
