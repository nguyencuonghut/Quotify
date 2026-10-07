import type {
  MaterialThresholdDomain,
  MaterialThresholdItemDto,
  MaterialThresholdListDomain,
  MaterialThresholdListDto,
  PriceAlertSettingsDomain,
  PriceAlertSettingsDto,
  PriceAlertSettingsUpdatePayload,
  PriceAlertSettingsValues,
} from '@/types/price-alert-settings'

const TIMEZONE = import.meta.env.VITE_APP_TIMEZONE || 'Asia/Ho_Chi_Minh'

const dateTimeFormatter = new Intl.DateTimeFormat('vi-VN', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
  timeZone: TIMEZONE,
})
const percentFormatter = new Intl.NumberFormat('vi-VN', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

function formatPercent(value: number): string {
  return `${percentFormatter.format(value)}%`
}

function formatDateTime(value: string | null): string | null {
  if (!value) {
    return null
  }
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : dateTimeFormatter.format(date)
}

export function mapSettingsDtoToDomain(
  dto: PriceAlertSettingsDto,
): PriceAlertSettingsDomain {
  return {
    values: {
      isEnabled: dto.is_enabled,
      anomalyEnabled: dto.anomaly_enabled,
      referenceWorkingDays: dto.reference_working_days,
      lightFromPercent: Number(dto.light_from_percent),
      mediumFromPercent: Number(dto.medium_from_percent),
      largeOverPercent: Number(dto.large_over_percent),
      anomalyPercent: Number(dto.anomaly_percent),
      anomalyLookbackDays: dto.anomaly_lookback_days,
      maxTriggerDelayWorkingDays: dto.max_trigger_delay_working_days,
      staffLookbackDays: dto.staff_lookback_days,
      dedupeWindowDays: dto.dedupe_window_days,
      immediateCapPerScan: dto.immediate_cap_per_scan,
      digestHourLocal: dto.digest_hour_local,
      referenceFallbackDays: dto.reference_fallback_days,
    },
    enabledSinceLabel: formatDateTime(dto.enabled_since),
    updatedAtLabel: formatDateTime(dto.updated_at) ?? '',
  }
}

/** Làm tròn hai chữ số thập phân: backend nhận Decimal tối đa hai chữ số. */
function round2(value: number): number {
  return Math.round(value * 100) / 100
}

export function mapSettingsValuesToPayload(
  values: PriceAlertSettingsValues,
): PriceAlertSettingsUpdatePayload {
  return {
    is_enabled: values.isEnabled,
    anomaly_enabled: values.anomalyEnabled,
    reference_working_days: values.referenceWorkingDays,
    light_from_percent: round2(values.lightFromPercent),
    medium_from_percent: round2(values.mediumFromPercent),
    large_over_percent: round2(values.largeOverPercent),
    anomaly_percent: round2(values.anomalyPercent),
    anomaly_lookback_days: values.anomalyLookbackDays,
    max_trigger_delay_working_days: values.maxTriggerDelayWorkingDays,
    staff_lookback_days: values.staffLookbackDays,
    dedupe_window_days: values.dedupeWindowDays,
    immediate_cap_per_scan: values.immediateCapPerScan,
    digest_hour_local: values.digestHourLocal,
    reference_fallback_days: values.referenceFallbackDays,
  }
}

export function mapMaterialItemDtoToDomain(
  dto: MaterialThresholdItemDto,
): MaterialThresholdDomain {
  const effective = {
    light: Number(dto.effective.light_from_percent),
    medium: Number(dto.effective.medium_from_percent),
    large: Number(dto.effective.large_over_percent),
    anomaly: Number(dto.effective.anomaly_percent),
  }
  const override = dto.override
    ? {
        light: Number(dto.override.light_from_percent),
        medium: Number(dto.override.medium_from_percent),
        large: Number(dto.override.large_over_percent),
        anomaly:
          dto.override.anomaly_percent === null
            ? null
            : Number(dto.override.anomaly_percent),
      }
    : null
  const freshness = dto.freshness
    ? {
        isWatched: dto.freshness.is_watched,
        expectedIntervalDays: dto.freshness.expected_interval_days,
      }
    : null
  return {
    materialId: dto.material_id,
    code: dto.code,
    name: dto.name,
    freshness,
    watchLabel: freshness === null ? 'Chưa đặt' : freshness.isWatched ? 'Có' : 'Không',
    intervalLabel: freshness === null ? '—' : String(freshness.expectedIntervalDays),
    hasOverride: override !== null,
    override,
    effective,
    lightLabel: formatPercent(effective.light),
    mediumLabel: formatPercent(effective.medium),
    largeLabel: formatPercent(effective.large),
    anomalyLabel: formatPercent(effective.anomaly),
    anomalyIsDefault: override === null || override.anomaly === null,
  }
}

export function mapMaterialListDtoToDomain(
  dto: MaterialThresholdListDto,
): MaterialThresholdListDomain {
  return {
    items: dto.items.map(mapMaterialItemDtoToDomain),
    total: dto.total,
  }
}
