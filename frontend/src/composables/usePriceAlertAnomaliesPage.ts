import { ref } from 'vue'

import { ApiError } from '@/api/http'
import { listAnomalies, reviewAnomaly } from '@/api/price-alert-anomalies.api'
import { mapAnomalyConflictPayload } from '@/api/price-alert-anomalies.mappers'
import { useAuthStore } from '@/stores/auth.store'
import type {
  AnomalyDecision,
  AnomalyDomain,
} from '@/types/price-alert-anomalies'

export type AnomalyTab = 'pending' | 'resolved'

const DEFAULT_ROWS = 10
const DECISION_LABELS: Record<AnomalyDecision, string> = {
  accepted: 'giá đúng',
  rejected: 'nhập sai',
}

function describeReviewError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 409) {
      const conflict = mapAnomalyConflictPayload(error.payload)
      if (conflict) {
        const by = conflict.reviewerName ? ` bởi ${conflict.reviewerName}` : ''
        const at = conflict.reviewedAtLabel
          ? ` lúc ${conflict.reviewedAtLabel}`
          : ''
        return `Điểm giá này đã được xử lý: ${conflict.statusLabel}${by}${at}.`
      }
      return 'Điểm giá này đã được xử lý.'
    }
    if (error.status === 403) {
      return 'Bạn không có quyền duyệt giá bất thường.'
    }
    if (error.status === 404) {
      return 'Điểm giá không còn tồn tại hoặc không thể duyệt riêng.'
    }
  }
  return 'Không thể xử lý yêu cầu. Vui lòng thử lại.'
}

export function usePriceAlertAnomaliesPage() {
  const authStore = useAuthStore()

  const tab = ref<AnomalyTab>('pending')
  const anomalies = ref<AnomalyDomain[]>([])
  const total = ref(0)
  const loading = ref(false)
  const generalError = ref<string | null>(null)
  const rows = ref(DEFAULT_ROWS)
  const first = ref(0)
  const rowsPerPageOptions = [10, 20, 30, 50]

  const confirmVisible = ref(false)
  const confirmTarget = ref<AnomalyDomain | null>(null)
  const confirmDecisionValue = ref<AnomalyDecision>('accepted')
  const isBusy = ref(false)
  const errorMessage = ref<string | null>(null)
  const successMessage = ref<string | null>(null)

  // Số thứ tự yêu cầu: phản hồi của yêu cầu cũ (đổi tab, đổi trang nhanh) bị bỏ qua.
  let requestSeq = 0

  async function fetchAnomalies() {
    const seq = ++requestSeq
    loading.value = true
    generalError.value = null
    try {
      const result = await listAnomalies(
        { status: tab.value, limit: rows.value, offset: first.value },
        authStore.accessToken,
      )
      if (seq !== requestSeq) {
        return
      }
      // Duyệt hết dòng cuối của trang cuối: lùi về trang còn dữ liệu rồi tải lại.
      if (result.items.length === 0 && result.total > 0 && first.value > 0) {
        first.value = Math.floor((result.total - 1) / rows.value) * rows.value
        await fetchAnomalies()
        return
      }
      anomalies.value = result.items
      total.value = result.total
    } catch {
      if (seq !== requestSeq) {
        return
      }
      anomalies.value = []
      total.value = 0
      generalError.value = 'Không thể tải danh sách giá bất thường.'
    } finally {
      if (seq === requestSeq) {
        loading.value = false
      }
    }
  }

  async function onPageChange(event: { first: number; rows: number }) {
    first.value = event.first
    rows.value = event.rows
    await fetchAnomalies()
  }

  async function setTab(next: AnomalyTab) {
    tab.value = next
    first.value = 0
    await fetchAnomalies()
  }

  function openConfirm(item: AnomalyDomain, decision: AnomalyDecision) {
    confirmTarget.value = item
    confirmDecisionValue.value = decision
    errorMessage.value = null
    successMessage.value = null
    confirmVisible.value = true
  }

  function closeConfirm() {
    // Đang gửi yêu cầu thì không đóng: Esc hay nút X không được làm mất hộp xác nhận.
    if (isBusy.value) {
      return
    }
    confirmVisible.value = false
    confirmTarget.value = null
  }

  async function confirmDecision() {
    const target = confirmTarget.value
    if (isBusy.value || !target) {
      return
    }
    isBusy.value = true
    errorMessage.value = null
    successMessage.value = null
    try {
      await reviewAnomaly(
        target.id,
        confirmDecisionValue.value,
        authStore.accessToken,
      )
      successMessage.value = `Đã ghi nhận ${DECISION_LABELS[confirmDecisionValue.value]} cho ${target.materialName} (kỳ ${target.deliveryMonthLabel}).`
    } catch (error) {
      errorMessage.value = describeReviewError(error)
    } finally {
      isBusy.value = false
      // Chỉ đóng nếu hộp xác nhận vẫn là của thẻ vừa xử lý.
      if (confirmTarget.value === target) {
        closeConfirm()
      }
    }
    // Tải lại danh sách cả khi lỗi 409 để người dùng thấy trạng thái mới nhất.
    await fetchAnomalies()
  }

  return {
    tab,
    anomalies,
    total,
    loading,
    generalError,
    rows,
    first,
    rowsPerPageOptions,
    confirmVisible,
    confirmTarget,
    confirmDecisionValue,
    isBusy,
    errorMessage,
    successMessage,
    fetchAnomalies,
    onPageChange,
    setTab,
    openConfirm,
    closeConfirm,
    confirmDecision,
  }
}
