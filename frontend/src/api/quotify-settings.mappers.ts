import type {
  QuotifySettingsDomain,
  QuotifySettingsDto,
} from '@/types/quotify-settings'

export function mapQuotifySettingsDtoToDomain(
  dto: QuotifySettingsDto,
): QuotifySettingsDomain {
  return {
    id: dto.id,
    conversionCostVndPerKg: dto.conversion_cost_vnd_per_kg,
    updatedById: dto.updated_by_id,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  }
}
