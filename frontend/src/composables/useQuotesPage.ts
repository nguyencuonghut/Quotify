import { ref, computed } from 'vue'
import { getQuotesList } from '@/api/quotes.api'
import type { QuoteFlattenedDomain } from '@/types/quotes'

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

export function useQuotesPage(accessToken: string | null) {
  const items = ref<QuoteFlattenedDomain[]>([])
  const total = ref<number>(0)
  const isLoading = ref<boolean>(false)
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
  const sortField = ref<string>('created_at')
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
      const res = await getQuotesList(queryParams.value, accessToken)
      items.value = res.items
      total.value = res.total
    } catch (err: unknown) {
      errorMsg.value =
        err instanceof Error ? err.message : 'Lỗi khi tải danh sách báo giá.'
    } finally {
      isLoading.value = false
    }
  }

  const handlePageChange = (event: QuotesPageChangeEvent) => {
    limit.value = event.rows
    offset.value = event.first
    loadQuotesData()
  }

  const handleSortChange = (event: QuotesSortChangeEvent) => {
    sortField.value =
      typeof event.sortField === 'string' ? event.sortField : 'created_at'
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
    handlePageChange,
    handleSortChange,
    resetFilters,
  }
}
