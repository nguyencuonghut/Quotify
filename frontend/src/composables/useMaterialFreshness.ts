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

export function useMaterialFreshness() {
  const authStore = useAuthStore()

  const data = ref<MaterialFreshness | null>(null)
  const isLoading = ref(false)
  const errorMessage = ref<string | null>(null)
  const statusFilter = ref<MaterialFreshnessStatus | null>(null)
  const typeFilter = ref<string | null>(null)

  const items = computed(() => data.value?.items ?? [])
  const rows = computed(() =>
    items.value
      .filter(
        (item) => !statusFilter.value || item.status === statusFilter.value,
      )
      .filter(
        (item) => !typeFilter.value || item.materialTypeId === typeFilter.value,
      )
      .sort(compareRows),
  )
  const typeOptions = computed(() => {
    const byId = new Map<string, string>()
    for (const item of items.value) {
      byId.set(item.materialTypeId, item.materialTypeName)
    }
    return [...byId.entries()]
      .map(([value, label]) => ({ label, value }))
      .sort((left, right) => collator.compare(left.label, right.label))
  })
  const hasActiveFilters = computed(
    () => statusFilter.value !== null || typeFilter.value !== null,
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
  }

  return {
    data,
    rows,
    isLoading,
    errorMessage,
    statusFilter,
    typeFilter,
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
