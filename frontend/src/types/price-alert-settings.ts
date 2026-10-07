export interface PriceAlertSettingsDto {
  is_enabled: boolean
  anomaly_enabled: boolean
  reference_working_days: number
  light_from_percent: string
  medium_from_percent: string
  large_over_percent: string
  anomaly_percent: string
  anomaly_lookback_days: number
  max_trigger_delay_working_days: number
  staff_lookback_days: number
  dedupe_window_days: number
  immediate_cap_per_scan: number
  digest_hour_local: number
  reference_fallback_days: number
  enabled_since: string | null
  updated_at: string
}

/** Giá trị form cấu hình chung (số thật, đã đổi từ chuỗi Decimal của API). */
export interface PriceAlertSettingsValues {
  isEnabled: boolean
  anomalyEnabled: boolean
  referenceWorkingDays: number
  lightFromPercent: number
  mediumFromPercent: number
  largeOverPercent: number
  anomalyPercent: number
  anomalyLookbackDays: number
  maxTriggerDelayWorkingDays: number
  staffLookbackDays: number
  dedupeWindowDays: number
  immediateCapPerScan: number
  digestHourLocal: number
  referenceFallbackDays: number
}

export interface PriceAlertSettingsDomain {
  values: PriceAlertSettingsValues
  enabledSinceLabel: string | null
  updatedAtLabel: string
}

/** Thân PUT: backend yêu cầu gửi đủ mọi trường. */
export type PriceAlertSettingsUpdatePayload = Omit<
  PriceAlertSettingsDto,
  | 'enabled_since'
  | 'updated_at'
  | 'light_from_percent'
  | 'medium_from_percent'
  | 'large_over_percent'
  | 'anomaly_percent'
> & {
  light_from_percent: number
  medium_from_percent: number
  large_over_percent: number
  anomaly_percent: number
}

export interface ThresholdsDto {
  light_from_percent: string
  medium_from_percent: string
  large_over_percent: string
  anomaly_percent: string | null
}

export interface MaterialFreshnessConfigDto {
  is_watched: boolean
  expected_interval_days: number
}

export interface MaterialFreshnessConfig {
  isWatched: boolean
  expectedIntervalDays: number
}

export interface MaterialFreshnessUpdatePayload {
  is_watched: boolean
  expected_interval_days: number
}

export interface MaterialThresholdItemDto {
  material_id: string
  code: string
  name: string
  override: ThresholdsDto | null
  effective: Required<{ [K in keyof ThresholdsDto]: string }>
  freshness?: MaterialFreshnessConfigDto | null
}

export interface MaterialThresholdListDto {
  items: MaterialThresholdItemDto[]
  total: number
}

export interface Thresholds {
  light: number
  medium: number
  large: number
  anomaly: number | null
}

export interface MaterialThresholdDomain {
  materialId: string
  code: string
  name: string
  hasOverride: boolean
  override: Thresholds | null
  effective: Thresholds & { anomaly: number }
  freshness: MaterialFreshnessConfig | null
  watchLabel: string
  intervalLabel: string
  lightLabel: string
  mediumLabel: string
  largeLabel: string
  anomalyLabel: string
  /** Ngưỡng bất thường có đang dùng mặc định dù vật tư có ghi đè ba ngưỡng đầu. */
  anomalyIsDefault: boolean
}

export interface MaterialThresholdListDomain {
  items: MaterialThresholdDomain[]
  total: number
}

export interface MaterialThresholdListQuery {
  limit: number
  offset: number
  search?: string
}

export interface MaterialThresholdUpdatePayload {
  light_from_percent: number
  medium_from_percent: number
  large_over_percent: number
  anomaly_percent: number | null
}
