import { computed, ref } from 'vue'

import { getMaterialFreshness } from '@/api/material-freshness.api'
import { MATERIAL_FRESHNESS_STATUS_LABELS } from '@/api/material-freshness.mappers'
import { useAuthStore } from '@/stores/auth.store'
import type {
  MaterialFreshness,
  MaterialFreshnessItem,
  MaterialFreshnessStatus,
} from '@/types/material-freshness'

export interface MaterialFreshnessCard {
  key: string
  label: string
  value: string
  detail: string
  icon: string
  tone: 'primary' | 'success' | 'warn'
}

// Thứ tự trạng thái khi sắp xếp và trong ô lọc: việc cần xử lý đứng trước.
const STATUS_ORDER: MaterialFreshnessStatus[] = [
  'overdue',
  'never',
  'on_time',
  'updated',
]

export const MATERIAL_FRESHNESS_STATUS_OPTIONS = STATUS_ORDER.map((status) => ({
  label: MATERIAL_FRESHNESS_STATUS_LABELS[status],
  value: status,
}))

const collator = new Intl.Collator('vi')

function compareRows(
  left: MaterialFreshnessItem,
  right: MaterialFreshnessItem,
): number {
  const byStatus =
    STATUS_ORDER.indexOf(left.status) - STATUS_ORDER.indexOf(right.status)
  if (byStatus !== 0) {
    return byStatus
  }
  if (left.status === 'updated') {
    const byCount = right.updateCount - left.updateCount
    if (byCount !== 0) {
      return byCount
    }
  } else if (left.status !== 'never') {
    const byAge = (right.ageDays ?? 0) - (left.ageDays ?? 0)
    if (byAge !== 0) {
      return byAge
    }
  }
  return collator.compare(left.materialName, right.materialName)
}

export type MaterialFreshnessSortField =
  | 'name'
  | 'type'
  | 'updateCount'
  | 'supplierCount'
  | 'lastReceivedDate'
  | 'ageDays'
  | 'interval'
  | 'status'
  | 'enterer'

// Cũng là danh sách ô chọn "Sắp xếp theo" cho màn hình nhỏ (không có tiêu đề cột để bấm).
export const MATERIAL_FRESHNESS_SORT_OPTIONS: {
  label: string
  value: MaterialFreshnessSortField
}[] = [
  { label: 'Vật tư', value: 'name' },
  { label: 'Loại', value: 'type' },
  { label: 'Số lần', value: 'updateCount' },
  { label: 'Số NCC', value: 'supplierCount' },
  { label: 'Nhận gần nhất', value: 'lastReceivedDate' },
  { label: 'Số ngày chưa có giá', value: 'ageDays' },
  { label: 'Chu kỳ', value: 'interval' },
  { label: 'Trạng thái', value: 'status' },
  { label: 'Người nhập gần nhất', value: 'enterer' },
]

const SORT_FIELDS = new Set<string>(
  MATERIAL_FRESHNESS_SORT_OPTIONS.map((option) => option.value),
)

// Giá trị của "Chưa rõ người nhập" trong ô lọc (không trùng id người dùng thật).
export const NO_ENTERER_VALUE = '__none__'

function sortValue(
  item: MaterialFreshnessItem,
  field: MaterialFreshnessSortField,
): string | number | null {
  switch (field) {
    case 'name':
      return item.materialName
    case 'type':
      return item.materialTypeName
    case 'updateCount':
      return item.updateCount
    case 'supplierCount':
      return item.supplierCount
    case 'lastReceivedDate':
      return item.lastReceivedDate
    case 'ageDays':
      return item.ageDays
    case 'interval':
      return item.expectedIntervalDays
    case 'status':
      return STATUS_ORDER.indexOf(item.status)
    case 'enterer':
      return item.lastEntererLabel
  }
}

// Giá trị thiếu luôn nằm cuối, cả khi sắp giảm dần.
function compareByField(
  field: MaterialFreshnessSortField,
  order: 1 | -1,
): (left: MaterialFreshnessItem, right: MaterialFreshnessItem) => number {
  return (left, right) => {
    const a = sortValue(left, field)
    const b = sortValue(right, field)
    if (a === null && b === null) {
      return compareRows(left, right)
    }
    if (a === null) {
      return 1
    }
    if (b === null) {
      return -1
    }
    const result =
      typeof a === 'number' && typeof b === 'number'
        ? a - b
        : collator.compare(String(a), String(b))
    return result === 0 ? compareRows(left, right) : result * order
  }
}

// Bỏ dấu và chữ hoa/thường để gõ "ngo hat" vẫn tìm được "Ngô hạt".
function fold(text: string): string {
  return text
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .toLowerCase()
}

function matchesSearch(item: MaterialFreshnessItem, needle: string): boolean {
  return [
    item.materialName,
    item.materialCode,
    item.materialTypeName,
    item.lastEntererLabel ?? '',
  ].some((text) => fold(text).includes(needle))
}

export function useMaterialFreshness() {
  const authStore = useAuthStore()

  const data = ref<MaterialFreshness | null>(null)
  const isLoading = ref(false)
  const errorMessage = ref<string | null>(null)
  const statusFilter = ref<MaterialFreshnessStatus | null>(null)
  const typeFilter = ref<string | null>(null)
  const entererFilter = ref<string | null>(null)
  const searchText = ref('')
  const sortField = ref<MaterialFreshnessSortField | null>(null)
  const sortOrder = ref<1 | -1>(1)

  const items = computed(() => data.value?.items ?? [])
  const rows = computed(() => {
    const needle = fold(searchText.value.trim())
    const filtered = items.value
      .filter(
        (item) => !statusFilter.value || item.status === statusFilter.value,
      )
      .filter(
        (item) => !typeFilter.value || item.materialTypeId === typeFilter.value,
      )
      .filter(
        (item) =>
          !entererFilter.value ||
          (item.lastEntererId ?? NO_ENTERER_VALUE) === entererFilter.value,
      )
      .filter((item) => !needle || matchesSearch(item, needle))
    return filtered.sort(
      sortField.value
        ? compareByField(sortField.value, sortOrder.value)
        : compareRows,
    )
  })
  const typeOptions = computed(() => {
    const byId = new Map<string, string>()
    for (const item of items.value) {
      byId.set(item.materialTypeId, item.materialTypeName)
    }
    return [...byId.entries()]
      .map(([value, label]) => ({ label, value }))
      .sort((left, right) => collator.compare(left.label, right.label))
  })
  const entererOptions = computed(() => {
    const byValue = new Map<string, string>()
    for (const item of items.value) {
      if (item.lastEntererId === null) {
        byValue.set(NO_ENTERER_VALUE, 'Chưa rõ người nhập')
      } else {
        byValue.set(
          item.lastEntererId,
          item.lastEntererLabel ?? 'Không xác định',
        )
      }
    }
    return [...byValue.entries()]
      .map(([value, label]) => ({ label, value }))
      .sort((left, right) =>
        left.value === NO_ENTERER_VALUE
          ? -1
          : right.value === NO_ENTERER_VALUE
            ? 1
            : collator.compare(left.label, right.label),
      )
  })
  const hasActiveFilters = computed(
    () =>
      statusFilter.value !== null ||
      typeFilter.value !== null ||
      entererFilter.value !== null ||
      searchText.value.trim() !== '',
  )
  const isEmpty = computed(
    () => data.value !== null && items.value.length === 0,
  )
  const hasNoMatches = computed(
    () => items.value.length > 0 && rows.value.length === 0,
  )

  const summaryCards = computed<MaterialFreshnessCard[]>(() => {
    const summary = data.value?.summary
    if (!summary) {
      return []
    }
    return [
      {
        key: 'watched',
        label: 'Đang theo dõi',
        value: String(summary.watchedCount),
        detail: 'vật tư trong danh sách theo dõi',
        icon: 'pi pi-eye',
        tone: 'primary',
      },
      {
        key: 'updated',
        label: 'Đã cập nhật',
        value: `${summary.updatedCount} / ${summary.watchedCount}`,
        detail:
          summary.unwatchedUpdatedCount > 0
            ? `+${summary.unwatchedUpdatedCount} vật tư không theo dõi cũng có giá mới`
            : 'trong tuần đã chọn',
        icon: 'pi pi-check-circle',
        tone: 'success',
      },
      {
        key: 'on_time',
        label: 'Đúng hạn',
        value: String(summary.onTimeCount),
        detail: 'chưa có giá mới nhưng còn trong chu kỳ',
        icon: 'pi pi-clock',
        tone: 'primary',
      },
      {
        key: 'overdue',
        label: 'Quá hạn',
        value: String(summary.overdueCount),
        detail: 'gồm cả vật tư chưa từng có giá',
        icon: 'pi pi-exclamation-triangle',
        tone: summary.overdueCount > 0 ? 'warn' : 'success',
      },
    ]
  })

  // Mỗi lần gọi `load` nhận một số thứ tự; phản hồi của lần gọi cũ hơn bị bỏ qua để không ghi đè
  // dữ liệu của tuần mới chọn (người dùng đổi tuần nhanh, mạng chậm).
  let latestRequest = 0

  async function load(weekStart: string | null) {
    const request = ++latestRequest
    isLoading.value = true
    errorMessage.value = null
    try {
      const response = await getMaterialFreshness(
        weekStart,
        authStore.accessToken,
      )
      if (request !== latestRequest) {
        return
      }
      data.value = response
      // Tuần mới có thể không còn loại vật tư đang lọc: bỏ bộ lọc đó để ô chọn và danh sách
      // không lệch nhau (ô chọn hiện "Tất cả" nhưng danh sách vẫn bị lọc).
      if (
        typeFilter.value !== null &&
        !response.items.some((item) => item.materialTypeId === typeFilter.value)
      ) {
        typeFilter.value = null
      }
      if (
        entererFilter.value !== null &&
        !response.items.some(
          (item) =>
            (item.lastEntererId ?? NO_ENTERER_VALUE) === entererFilter.value,
        )
      ) {
        entererFilter.value = null
      }
    } catch {
      if (request !== latestRequest) {
        return
      }
      data.value = null
      errorMessage.value = 'Không thể tải độ mới của giá theo vật tư.'
    } finally {
      if (request === latestRequest) {
        isLoading.value = false
      }
    }
  }

  function resetFilters() {
    statusFilter.value = null
    typeFilter.value = null
    entererFilter.value = null
    searchText.value = ''
  }

  // Sắp xếp phía client (dưới 200 dòng). Cột lạ hoặc bỏ sắp xếp thì về thứ tự mặc định.
  function onSort(event: { sortField?: unknown; sortOrder?: number | null }) {
    const field = event.sortField
    sortField.value =
      typeof field === 'string' && SORT_FIELDS.has(field)
        ? (field as MaterialFreshnessSortField)
        : null
    // Bỏ sắp xếp (hoặc cột lạ) thì cũng quên chiều, để cột chọn kế tiếp bắt đầu từ tăng dần.
    sortOrder.value = sortField.value && event.sortOrder === -1 ? -1 : 1
  }

  return {
    data,
    rows,
    isLoading,
    errorMessage,
    statusFilter,
    typeFilter,
    entererFilter,
    searchText,
    sortField,
    sortOrder,
    sortOptions: MATERIAL_FRESHNESS_SORT_OPTIONS,
    entererOptions,
    onSort,
    statusOptions: MATERIAL_FRESHNESS_STATUS_OPTIONS,
    typeOptions,
    hasActiveFilters,
    isEmpty,
    hasNoMatches,
    summaryCards,
    load,
    resetFilters,
  }
}
