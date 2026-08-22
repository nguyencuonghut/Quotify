import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent } from 'vue'
import { describe, expect, it, vi } from 'vitest'

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

vi.mock('@/composables/useQuotesPage', async () => {
  const { ref } = await import('vue')
  return {
    useQuotesPage: () => ({
      items: ref([]),
      total: ref(0),
      isLoading: ref(false),
      isExporting: ref(false),
      errorMsg: ref(null),
      globalSearch: ref(''),
      supplierId: ref(null),
      materialId: ref(null),
      materialTypeId: ref(null),
      receivedDateStart: ref(null),
      receivedDateEnd: ref(null),
      deliveryMonth: ref(null),
      purchased: ref(null),
      limit: ref(10),
      offset: ref(0),
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
