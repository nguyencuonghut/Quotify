export interface QuotifySettingsDto {
  id: string
  import_tax_rate_percent: string
  processing_cost_vnd_per_kg: string
  updated_by_id: string | null
  created_at: string
  updated_at: string
}

export interface QuotifySettingsDomain {
  id: string
  importTaxRatePercent: string
  processingCostVndPerKg: string
  updatedById: string | null
  createdAt: string
  updatedAt: string
}

export interface QuotifySettingsUpdatePayload {
  import_tax_rate_percent: string
  processing_cost_vnd_per_kg: string
}
