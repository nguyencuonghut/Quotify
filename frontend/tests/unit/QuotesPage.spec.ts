import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref } from 'vue'
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'

const quotesPageMock = vi.hoisted(() => ({
  loadQuotesData: vi.fn(),
  exportQuotes: vi.fn(),
  handlePageChange: vi.fn(),
  handleSortChange: vi.fn(),
  resetFilters: vi.fn(),
}))

const backfillImportMock = vi.hoisted(() => ({
  openImportDialog: vi.fn(),
  handleImportUpload: vi.fn(),
  downloadTemplate: vi.fn(),
  downloadErrorFile: vi.fn(),
}))

const lookupApiMock = vi.hoisted(() => ({
  lookupActiveSuppliers: vi.fn().mockResolvedValue([]),
  listMaterialsLookup: vi.fn().mockResolvedValue([]),
  listMaterialTypesLookup: vi.fn().mockResolvedValue([]),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock('@/api/suppliers.api', () => ({
  lookupActiveSuppliers: lookupApiMock.lookupActiveSuppliers,
}))

vi.mock('@/api/materials.api', () => ({
  listMaterialsLookup: lookupApiMock.listMaterialsLookup,
  listMaterialTypesLookup: lookupApiMock.listMaterialTypesLookup,
}))

// Refs dùng chung ở module-level (không tạo mới mỗi lần gọi `useQuotesPage()`)
// — để test đọc lại đúng giá trị component đã gán vào sau khi khôi phục từ
// `quotes-view.store`, cùng pattern với refs chung ở `QuoteDetailPage.spec.ts`.
const globalSearch = ref<string>('')
const supplierId = ref<string | null>(null)
const materialId = ref<string | null>(null)
const materialTypeId = ref<string | null>(null)
const receivedDateStart = ref<Date | null>(null)
const receivedDateEnd = ref<Date | null>(null)
const deliveryMonth = ref<Date | null>(null)
const purchased = ref<boolean | null>(null)
const cancelled = ref<boolean | null>(null)
const limit = ref<number>(10)
const offset = ref<number>(0)
const sortField = ref<string>('received_date')
const sortOrder = ref<string>('desc')

vi.mock('@/composables/useQuotesPage', async () => {
  const { ref } = await import('vue')
  return {
    useQuotesPage: () => ({
      items: ref([]),
      total: ref(0),
      isLoading: ref(false),
      isExporting: ref(false),
      errorMsg: ref(null),
      globalSearch,
      supplierId,
      materialId,
      materialTypeId,
      receivedDateStart,
      receivedDateEnd,
      deliveryMonth,
      purchased,
      cancelled,
      limit,
      offset,
      sortField,
      sortOrder,
      ...quotesPageMock,
    }),
  }
})

vi.mock('@/composables/useQuoteBackfillImport', async () => {
  const { ref } = await import('vue')
  return {
    useQuoteBackfillImport: () => ({
      importDialogVisible: ref(false),
      importJob: ref(null),
      importError: ref(null),
      uploadingImport: ref(false),
      ...backfillImportMock,
    }),
  }
})

import QuotesPage from '@/pages/QuotesPage.vue'

const passthroughStub = defineComponent({
  template: '<div><slot /></div>',
})

// `tests/setup.ts` stub DataTable mặc định không gọi slot `#empty` — override
// riêng cho test này (xem MaterialsPage.spec.ts để biết lý do đầy đủ).
const dataTableStubWithEmptySlot = {
  props: ['value'],
  template: `
    <div>
      <slot />
      <div data-testid="row-count">{{ value?.length ?? 0 }}</div>
      <div v-if="!value || value.length === 0"><slot name="empty" /></div>
    </div>
  `,
}

function mountQuotesPage() {
  return mount(QuotesPage, {
    global: {
      stubs: {
        AdminLayout: passthroughStub,
        Button: true,
        Checkbox: true,
        Dialog: true,
        FileUpload: true,
        InputText: true,
        ProgressBar: true,
        Select: true,
        DatePicker: true,
        DataTable: dataTableStubWithEmptySlot,
      },
    },
  })
}

describe('QuotesPage empty state', () => {
  it('shows a Vietnamese empty-state message in the desktop table when there are no quotes', async () => {
    setActivePinia(createPinia())

    const wrapper = mountQuotesPage()
    await wrapper.vm.$nextTick()

    // Scope riêng vào bảng DESKTOP (`.quotes-page__table-wrapper`) — bản
    // mobile card list (`.quotes-page__mobile-lines`) đã có sẵn thông điệp
    // rỗng riêng; jsdom không áp dụng CSS media query nên `wrapper.text()`
    // trên toàn trang sẽ "ăn gian" match được message của bản mobile dù
    // bảng desktop chưa có `#empty` — phải assert đúng phạm vi DataTable
    // desktop để test thực sự khoá đúng hành vi.
    const desktopTableWrapper = wrapper.get('.quotes-page__table-wrapper')
    expect(desktopTableWrapper.text()).toContain('Chưa có dữ liệu báo giá phù hợp')
  })
})

describe('QuotesPage restores view state after navigating back from quote detail', () => {
  let activeWrapper: ReturnType<typeof mountQuotesPage> | null = null

  beforeEach(() => {
    setActivePinia(createPinia())
    window.sessionStorage.clear()
    globalSearch.value = ''
    supplierId.value = null
    materialId.value = null
    materialTypeId.value = null
    receivedDateStart.value = null
    receivedDateEnd.value = null
    deliveryMonth.value = null
    purchased.value = null
    cancelled.value = null
    limit.value = 10
    offset.value = 0
    sortField.value = 'received_date'
    sortOrder.value = 'desc'
  })

  afterEach(() => {
    activeWrapper?.unmount()
    activeWrapper = null
  })

  it('re-applies the filter/pagination/sort snapshot saved in quotes-view.store on mount', async () => {
    const { useQuotesViewStore } = await import('@/stores/quotes-view.store')
    // Mô phỏng: người dùng đã lọc + chuyển trang trước khi click vào 1 dòng
    // để xem chi tiết — snapshot này được lưu lại bởi lượt mount TRƯỚC đó.
    useQuotesViewStore().save({
      globalSearch: 'Tân Long',
      supplierId: 'supplier-1',
      materialId: null,
      materialTypeId: null,
      receivedDateStart: '2026-05-11',
      receivedDateEnd: null,
      deliveryMonth: null,
      purchased: true,
      cancelled: null,
      limit: 20,
      offset: 40,
      sortField: 'price_converted_vnd_per_kg',
      sortOrder: 'asc',
    })

    activeWrapper = mountQuotesPage()
    await activeWrapper.vm.$nextTick()

    expect(globalSearch.value).toBe('Tân Long')
    expect(supplierId.value).toBe('supplier-1')
    expect(receivedDateStart.value).toEqual(new Date(2026, 4, 11))
    expect(purchased.value).toBe(true)
    expect(limit.value).toBe(20)
    expect(offset.value).toBe(40)
    expect(sortField.value).toBe('price_converted_vnd_per_kg')
    expect(sortOrder.value).toBe('asc')
  })

  it('keeps default filters when there is no saved snapshot (first visit)', async () => {
    activeWrapper = mountQuotesPage()
    await activeWrapper.vm.$nextTick()

    expect(globalSearch.value).toBe('')
    expect(purchased.value).toBeNull()
    expect(offset.value).toBe(0)
  })
})
