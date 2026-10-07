import { describe, expect, it } from 'vitest'

import {
  MATERIAL_FRESHNESS_STATUS_LABELS,
  formatFreshnessAge,
  formatFreshnessDate,
  formatFreshnessInterval,
  getFreshnessStatusSeverity,
  mapMaterialFreshnessDtoToDomain,
} from '@/api/material-freshness.mappers'
import type { MaterialFreshnessDto } from '@/types/material-freshness'

function dto(): MaterialFreshnessDto {
  return {
    week_start: '2026-10-05',
    week_end: '2026-10-11',
    as_of_date: '2026-10-07',
    summary: {
      watched_count: 3,
      updated_count: 1,
      on_time_count: 1,
      overdue_count: 1,
      unwatched_updated_count: 2,
    },
    items: [
      {
        material_id: 'm-1',
        material_code: 'NGO',
        material_name: 'Ngô hạt',
        material_type_id: 't-1',
        material_type_name: 'Nguyên liệu',
        is_watched: true,
        expected_interval_days: 7,
        update_count: 3,
        supplier_count: 2,
        last_received_date: '2026-10-06',
        age_days: 1,
        status: 'updated',
        last_enterer_id: 'u-1',
        last_enterer_label: 'Nguyễn Văn A',
      },
      {
        material_id: 'm-2',
        material_code: 'BAO',
        material_name: 'Bao bì 25kg',
        material_type_id: 't-2',
        material_type_name: 'Bao bì',
        is_watched: true,
        expected_interval_days: 30,
        update_count: 0,
        supplier_count: 0,
        last_received_date: null,
        age_days: null,
        status: 'never',
        last_enterer_id: null,
        last_enterer_label: null,
      },
    ],
  }
}

describe('material freshness mappers', () => {
  it('maps the DTO to the camelCase domain model', () => {
    const domain = mapMaterialFreshnessDtoToDomain(dto())

    expect(domain.weekStart).toBe('2026-10-05')
    expect(domain.weekEnd).toBe('2026-10-11')
    expect(domain.asOfDate).toBe('2026-10-07')
    expect(domain.summary).toEqual({
      watchedCount: 3,
      updatedCount: 1,
      onTimeCount: 1,
      overdueCount: 1,
      unwatchedUpdatedCount: 2,
    })
    expect(domain.items[0]).toEqual({
      materialId: 'm-1',
      materialCode: 'NGO',
      materialName: 'Ngô hạt',
      materialTypeId: 't-1',
      materialTypeName: 'Nguyên liệu',
      isWatched: true,
      expectedIntervalDays: 7,
      updateCount: 3,
      supplierCount: 2,
      lastReceivedDate: '2026-10-06',
      ageDays: 1,
      status: 'updated',
      lastEntererId: 'u-1',
      lastEntererLabel: 'Nguyễn Văn A',
    })
    expect(domain.items[1].lastReceivedDate).toBeNull()
    expect(domain.items[1].ageDays).toBeNull()
  })

  it('tolerates a missing items list', () => {
    const broken = {
      ...dto(),
      items: undefined,
    } as unknown as MaterialFreshnessDto

    expect(mapMaterialFreshnessDtoToDomain(broken).items).toEqual([])
  })

  it('labels every status in Vietnamese', () => {
    expect(MATERIAL_FRESHNESS_STATUS_LABELS).toEqual({
      updated: 'Đã cập nhật',
      on_time: 'Đúng hạn',
      overdue: 'Quá hạn',
      never: 'Chưa có giá',
    })
  })

  it('colours the status tags by urgency', () => {
    expect(getFreshnessStatusSeverity('updated')).toBe('success')
    expect(getFreshnessStatusSeverity('on_time')).toBe('info')
    expect(getFreshnessStatusSeverity('overdue')).toBe('danger')
    expect(getFreshnessStatusSeverity('never')).toBe('warn')
  })

  it('formats dates, ages and intervals without timezone shifts', () => {
    expect(formatFreshnessDate('2026-10-06')).toBe('06/10/2026')
    expect(formatFreshnessDate(null)).toBe('—')
    expect(formatFreshnessAge(0)).toBe('Hôm nay')
    expect(formatFreshnessAge(1)).toBe('1 ngày')
    expect(formatFreshnessAge(16)).toBe('16 ngày')
    expect(formatFreshnessAge(null)).toBe('—')
    expect(formatFreshnessInterval(14)).toBe('14 ngày')
    expect(formatFreshnessInterval(null)).toBe('—')
  })
})
