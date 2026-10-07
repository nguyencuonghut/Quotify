import type {
  MaterialFreshness,
  MaterialFreshnessDto,
  MaterialFreshnessItem,
  MaterialFreshnessItemDto,
  MaterialFreshnessStatus,
} from '@/types/material-freshness'

export const MATERIAL_FRESHNESS_STATUS_LABELS: Record<
  MaterialFreshnessStatus,
  string
> = {
  updated: 'Đã cập nhật',
  on_time: 'Đúng hạn',
  overdue: 'Quá hạn',
  never: 'Chưa có giá',
}

export type MaterialFreshnessSeverity = 'success' | 'info' | 'warn' | 'danger'

export function getFreshnessStatusSeverity(
  status: MaterialFreshnessStatus,
): MaterialFreshnessSeverity {
  switch (status) {
    case 'updated':
      return 'success'
    case 'on_time':
      return 'info'
    case 'overdue':
      return 'danger'
    default:
      return 'warn'
  }
}

// Ngày thuần (YYYY-MM-DD) được đổi bằng cách tách chuỗi, không qua `Date`, để không bị lệch múi giờ.
export function formatFreshnessDate(value: string | null): string {
  if (!value) {
    return '—'
  }
  const [year, month, day] = value.split('-')
  return year && month && day ? `${day}/${month}/${year}` : value
}

export function formatFreshnessAge(ageDays: number | null): string {
  if (ageDays === null) {
    return '—'
  }
  return ageDays === 0 ? 'Hôm nay' : `${ageDays} ngày`
}

export function formatFreshnessInterval(days: number | null): string {
  return days === null ? '—' : `${days} ngày`
}

function mapItem(dto: MaterialFreshnessItemDto): MaterialFreshnessItem {
  return {
    materialId: dto.material_id,
    materialCode: dto.material_code,
    materialName: dto.material_name,
    materialTypeId: dto.material_type_id,
    materialTypeName: dto.material_type_name,
    isWatched: dto.is_watched,
    expectedIntervalDays: dto.expected_interval_days,
    updateCount: dto.update_count,
    supplierCount: dto.supplier_count,
    lastReceivedDate: dto.last_received_date,
    ageDays: dto.age_days,
    status: dto.status,
    lastEntererId: dto.last_enterer_id,
    lastEntererLabel: dto.last_enterer_label,
  }
}

export function mapMaterialFreshnessDtoToDomain(
  dto: MaterialFreshnessDto,
): MaterialFreshness {
  return {
    weekStart: dto.week_start,
    weekEnd: dto.week_end,
    asOfDate: dto.as_of_date,
    summary: {
      watchedCount: dto.summary.watched_count,
      updatedCount: dto.summary.updated_count,
      onTimeCount: dto.summary.on_time_count,
      overdueCount: dto.summary.overdue_count,
      unwatchedUpdatedCount: dto.summary.unwatched_updated_count,
    },
    items: Array.isArray(dto.items) ? dto.items.map(mapItem) : [],
  }
}
