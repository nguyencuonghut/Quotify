export type MaterialFreshnessStatus =
  | 'updated'
  | 'on_time'
  | 'overdue'
  | 'never'

export interface MaterialFreshnessItemDto {
  material_id: string
  material_code: string
  material_name: string
  material_type_id: string
  material_type_name: string
  is_watched: boolean
  expected_interval_days: number | null
  update_count: number
  supplier_count: number
  last_received_date: string | null
  age_days: number | null
  status: MaterialFreshnessStatus
  last_enterer_id: string | null
  last_enterer_label: string | null
}

export interface MaterialFreshnessSummaryDto {
  watched_count: number
  updated_count: number
  on_time_count: number
  overdue_count: number
  unwatched_updated_count: number
}

export interface MaterialFreshnessDto {
  week_start: string
  week_end: string
  as_of_date: string
  summary: MaterialFreshnessSummaryDto
  items: MaterialFreshnessItemDto[]
}

export interface MaterialFreshnessItem {
  materialId: string
  materialCode: string
  materialName: string
  materialTypeId: string
  materialTypeName: string
  isWatched: boolean
  expectedIntervalDays: number | null
  updateCount: number
  supplierCount: number
  lastReceivedDate: string | null
  ageDays: number | null
  status: MaterialFreshnessStatus
  lastEntererId: string | null
  lastEntererLabel: string | null
}

export interface MaterialFreshnessSummary {
  watchedCount: number
  updatedCount: number
  onTimeCount: number
  overdueCount: number
  unwatchedUpdatedCount: number
}

export interface MaterialFreshness {
  weekStart: string
  weekEnd: string
  asOfDate: string
  summary: MaterialFreshnessSummary
  items: MaterialFreshnessItem[]
}
