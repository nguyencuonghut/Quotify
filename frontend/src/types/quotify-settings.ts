export interface QuotifySettingsDto {
  id: string
  conversion_cost_vnd_per_kg: string
  updated_by_id: string | null
  created_at: string
  updated_at: string
}

export interface QuotifySettingsDomain {
  id: string
  conversionCostVndPerKg: string
  updatedById: string | null
  createdAt: string
  updatedAt: string
}

export interface ConversionCostUpdatePayload {
  conversion_cost_vnd_per_kg: string
}
