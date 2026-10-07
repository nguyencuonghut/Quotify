import { describe, expect, it } from 'vitest'

import {
  mapMaterialItemDtoToDomain,
  mapSettingsDtoToDomain,
  mapSettingsValuesToPayload,
} from '@/api/price-alert-settings.mappers'
import type {
  MaterialThresholdItemDto,
  PriceAlertSettingsDto,
} from '@/types/price-alert-settings'

const settingsDto: PriceAlertSettingsDto = {
  is_enabled: true,
  anomaly_enabled: false,
  reference_working_days: 7,
  light_from_percent: '2.50',
  medium_from_percent: '5.00',
  large_over_percent: '10.00',
  anomaly_percent: '30.00',
  anomaly_lookback_days: 30,
  max_trigger_delay_working_days: 3,
  staff_lookback_days: 90,
  dedupe_window_days: 14,
  immediate_cap_per_scan: 30,
  digest_hour_local: 8,
  reference_fallback_days: 30,
  freshness_enabled: true,
  freshness_hour_local: 10,
  enabled_since: '2026-10-06T03:31:20+00:00',
  updated_at: '2026-10-06T03:31:20+00:00',
}

describe('price alert settings mappers', () => {
  it('turns Decimal strings into numbers and dates into Vietnam time labels', () => {
    const domain = mapSettingsDtoToDomain(settingsDto)

    expect(domain.values).toMatchObject({
      isEnabled: true,
      anomalyEnabled: false,
      lightFromPercent: 2.5,
      mediumFromPercent: 5,
      largeOverPercent: 10,
      anomalyPercent: 30,
      referenceWorkingDays: 7,
      digestHourLocal: 8,
      freshnessEnabled: true,
      freshnessHourLocal: 10,
    })
    expect(domain.enabledSinceLabel).toBe('10:31 06/10/2026')
    expect(domain.updatedAtLabel).toBe('10:31 06/10/2026')
    expect(
      mapSettingsDtoToDomain({ ...settingsDto, enabled_since: null })
        .enabledSinceLabel,
    ).toBeNull()
  })

  it('builds the full PUT body with two-decimal percents', () => {
    const { values } = mapSettingsDtoToDomain(settingsDto)

    const payload = mapSettingsValuesToPayload({
      ...values,
      lightFromPercent: 2.5000000001,
      isEnabled: false,
    })

    expect(payload.light_from_percent).toBe(2.5)
    expect(payload.is_enabled).toBe(false)
    expect(Object.keys(payload).sort()).toEqual(
      [
        'is_enabled',
        'anomaly_enabled',
        'reference_working_days',
        'light_from_percent',
        'medium_from_percent',
        'large_over_percent',
        'anomaly_percent',
        'anomaly_lookback_days',
        'max_trigger_delay_working_days',
        'staff_lookback_days',
        'dedupe_window_days',
        'immediate_cap_per_scan',
        'digest_hour_local',
        'reference_fallback_days',
        'freshness_enabled',
        'freshness_hour_local',
      ].sort(),
    )
  })

  it('shows the effective thresholds and tells defaults from overrides', () => {
    const base: MaterialThresholdItemDto = {
      material_id: 'm1',
      code: 'LM3',
      name: 'Lúa mỳ 3',
      override: null,
      effective: {
        light_from_percent: '2.50',
        medium_from_percent: '5.00',
        large_over_percent: '10.00',
        anomaly_percent: '30.00',
      },
    }

    const plain = mapMaterialItemDtoToDomain(base)
    expect(plain).toMatchObject({
      hasOverride: false,
      lightLabel: '2,50%',
      anomalyLabel: '30,00%',
      anomalyIsDefault: true,
    })

    const custom = mapMaterialItemDtoToDomain({
      ...base,
      override: {
        light_from_percent: '1.00',
        medium_from_percent: '3.00',
        large_over_percent: '6.00',
        anomaly_percent: null,
      },
      effective: {
        ...base.effective,
        light_from_percent: '1.00',
        medium_from_percent: '3.00',
        large_over_percent: '6.00',
      },
    })
    expect(custom.hasOverride).toBe(true)
    expect(custom.override).toEqual({
      light: 1,
      medium: 3,
      large: 6,
      anomaly: null,
    })
    expect(custom.anomalyIsDefault).toBe(true)
    expect(custom.mediumLabel).toBe('3,00%')

    const withAnomaly = mapMaterialItemDtoToDomain({
      ...base,
      override: {
        light_from_percent: '1.00',
        medium_from_percent: '3.00',
        large_over_percent: '6.00',
        anomaly_percent: '45.00',
      },
      effective: { ...base.effective, anomaly_percent: '45.00' },
    })
    expect(withAnomaly.anomalyIsDefault).toBe(false)
    expect(withAnomaly.anomalyLabel).toBe('45,00%')
  })

  it('maps the watch-list config of a material with Vietnamese labels', () => {
    const base: MaterialThresholdItemDto = {
      material_id: 'm1',
      code: 'LM3',
      name: 'Lúa mỳ 3',
      override: null,
      effective: {
        light_from_percent: '2.50',
        medium_from_percent: '5.00',
        large_over_percent: '10.00',
        anomaly_percent: '30.00',
      },
    }

    const none = mapMaterialItemDtoToDomain(base)
    expect(none.freshness).toBeNull()
    expect(none.watchLabel).toBe('Chưa đặt')
    expect(none.intervalLabel).toBe('—')

    const watched = mapMaterialItemDtoToDomain({
      ...base,
      freshness: { is_watched: true, expected_interval_days: 14 },
    })
    expect(watched.freshness).toEqual({
      isWatched: true,
      expectedIntervalDays: 14,
    })
    expect(watched.watchLabel).toBe('Có')
    expect(watched.intervalLabel).toBe('14')

    const off = mapMaterialItemDtoToDomain({
      ...base,
      freshness: { is_watched: false, expected_interval_days: 7 },
    })
    expect(off.watchLabel).toBe('Không')
    expect(off.intervalLabel).toBe('7')
  })
})
