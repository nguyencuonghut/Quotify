import { ref, computed } from 'vue'
import { ApiError } from '@/api/http'
import { downloadQuotesExport, getQuotesList } from '@/api/quotes.api'
import type { QuoteFlattenedDomain } from '@/types/quotes'

// Lỗi 401 chỉ tới đây khi cơ chế tự refresh token ở tầng http.ts (xem
// `setUnauthorizedHandler` trong main.ts) cũng đã thất bại thật sự (refresh
// token cũng hết hạn/không hợp lệ) — không nên hiện nguyên văn message tiếng
// Anh từ backend lên UI.
function describeError(err: unknown, fallback: string): string {
  if (err instanceof ApiError && err.status === 401) {
    return 'Phiên đăng nhập đã hết hạn, vui lòng tải lại trang.'
  }
  return err instanceof Error ? err.message : fallback
}

type QuoteListQueryParams = Record<string, string | number | boolean | null>

interface QuotesPageChangeEvent {
  first: number
  rows: number
}

interface QuotesSortChangeEvent {
  sortField?: string | ((item: unknown) => string)
  sortOrder?: number | null
}

function toDateInputValue(value: Date | null): string | null {
  if (!value) {
    return null
  }

  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function useQuotesPage(getAccessToken: () => string | null) {
  const items = ref<QuoteFlattenedDomain[]>([])
  const total = ref<number>(0)
  const isLoading = ref<boolean>(false)
  const isExporting = ref<boolean>(false)
  const errorMsg = ref<string | null>(null)

  // Filters
  const globalSearch = ref<string>('')
  const supplierId = ref<string | null>(null)
  const materialId = ref<string | null>(null)
  const materialTypeId = ref<string | null>(null)
  const receivedDateStart = ref<Date | null>(null)
  const receivedDateEnd = ref<Date | null>(null)
  const deliveryMonth = ref<Date | null>(null)
  const purchased = ref<boolean | null>(null)

  // Pagination & Sorting
  const limit = ref<number>(10)
  const offset = ref<number>(0)
  // Mặc định sort theo "Ngày nhận" gần nhất — khớp với cột "Ngày nhận" trong
  // bảng (field `received_date`) và với sort-field ban đầu của DataTable
  // (xem QuotesPage.vue) để mũi tên sort hiện đúng cột ngay từ lần tải đầu.
  // Tie-break theo `Quote.sequence_number`/`line_order` (backend
  // `QuoteQueryService`) đảm bảo các dòng cùng nhà cung cấp, cùng ngày nhận
  // vẫn đứng liền kề nhau theo đúng thứ tự nhập thực tế — theo phản hồi
  // người dùng ngày 20/08/2026.
  const sortField = ref<string>('received_date')
  const sortOrder = ref<string>('desc')

  const queryParams = computed(() => {
    const params: QuoteListQueryParams = {
      limit: limit.value,
      offset: offset.value,
      sortBy: sortField.value,
      sortOrder: sortOrder.value,
    }

    if (globalSearch.value.trim()) {
      params.globalSearch = globalSearch.value.trim()
    }
    if (supplierId.value) {
      params.supplierId = supplierId.value
    }
    if (materialId.value) {
      params.materialId = materialId.value
    }
    if (materialTypeId.value) {
      params.materialTypeId = materialTypeId.value
    }
    const receivedDateStartValue = toDateInputValue(receivedDateStart.value)
    const receivedDateEndValue = toDateInputValue(receivedDateEnd.value)
    const deliveryMonthValue = toDateInputValue(deliveryMonth.value)

    if (receivedDateStartValue) {
      params.receivedDateStart = receivedDateStartValue
    }
    if (receivedDateEndValue) {
      params.receivedDateEnd = receivedDateEndValue
    }
    if (deliveryMonthValue) {
      params.deliveryMonth = deliveryMonthValue
    }
    if (purchased.value !== null) {
      params.purchased = purchased.value
    }

    return params
  })

  const loadQuotesData = async () => {
    isLoading.value = true
    errorMsg.value = null
    try {
      const res = await getQuotesList(queryParams.value, getAccessToken())
      items.value = res.items
      total.value = res.total
    } catch (err: unknown) {
      errorMsg.value = describeError(err, 'Lỗi khi tải danh sách báo giá.')
    } finally {
      isLoading.value = false
    }
  }

  const exportQuotes = async () => {
    isExporting.value = true
    errorMsg.value = null
    try {
      await downloadQuotesExport(queryParams.value, getAccessToken())
    } catch (err: unknown) {
      errorMsg.value = describeError(err, 'Không thể xuất file Excel.')
    } finally {
      isExporting.value = false
    }
  }

  const handlePageChange = (event: QuotesPageChangeEvent) => {
    limit.value = event.rows
    offset.value = event.first
    loadQuotesData()
  }

  const handleSortChange = (event: QuotesSortChangeEvent) => {
    sortField.value =
      typeof event.sortField === 'string' ? event.sortField : 'received_date'
    sortOrder.value = event.sortOrder === 1 ? 'asc' : 'desc'
    loadQuotesData()
  }

  const resetFilters = () => {
    globalSearch.value = ''
    supplierId.value = null
    materialId.value = null
    materialTypeId.value = null
    receivedDateStart.value = null
    receivedDateEnd.value = null
    deliveryMonth.value = null
    purchased.value = null
    offset.value = 0
    loadQuotesData()
  }

  return {
    items,
    total,
    isLoading,
    isExporting,
    errorMsg,
    globalSearch,
    supplierId,
    materialId,
    materialTypeId,
    receivedDateStart,
    receivedDateEnd,
    deliveryMonth,
    purchased,
    limit,
    offset,
    sortField,
    sortOrder,
    loadQuotesData,
    exportQuotes,
    handlePageChange,
    handleSortChange,
    resetFilters,
  }
}
