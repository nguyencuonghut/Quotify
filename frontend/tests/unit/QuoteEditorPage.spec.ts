import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

function buildLine(materialId: string) {
  return {
    materialId,
    priceOriginal: 100,
    currency: 'VND',
    unit: 'KG',
    deliveryMonth: '2026-08',
    exchangeRate: null,
    exchangeRateManualReason: null,
    rateSourceMode: null,
    autoRateFetched: null,
    isRateLoading: false,
  }
}

const quoteEditorMock = vi.hoisted(() => ({
  initSettings: vi.fn(),
  fetchUsdRateToday: vi.fn(),
  addLine: vi.fn(),
  removeLine: vi.fn((index: number) => {
    lines.value.splice(index, 1)
  }),
  duplicateLine: vi.fn(),
  loadVersionData: vi.fn(),
  getLinePreviewPrice: vi.fn(() => null),
  validateForm: vi.fn(() => true),
  prepareCreatePayload: vi.fn(),
  prepareUpdatePayload: vi.fn(),
}))

const lines = ref<ReturnType<typeof buildLine>[]>([])

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}))

vi.mock('@/api/suppliers.api', () => ({
  lookupActiveSuppliers: vi.fn().mockResolvedValue([]),
}))

vi.mock('@/api/quotes.api', () => ({
  getQuote: vi.fn(),
  createQuote: vi.fn(),
  updateDraft: vi.fn(),
  createVersion: vi.fn(),
}))

vi.mock('@/composables/useQuoteEditor', () => ({
  useQuoteEditor: () => ({
    supplierId: ref(null),
    receivedDate: ref('2026-08-22'),
    isBackfilled: ref(false),
    correctionReason: ref(null),
    lines,
    supplierMaterials: ref([]),
    isSupplierLoading: ref(false),
    isSubmitting: ref(false),
    errorMsg: ref(null),
    ...quoteEditorMock,
  }),
}))

import QuoteEditorPage from '@/pages/QuoteEditorPage.vue'

const passthroughStub = defineComponent({
  template: '<div><slot /></div>',
})

// Dialog thật của PrimeVue cần plugin `app.use(PrimeVue)` (đọc `$primevue`
// khi render) — không có trong `mount()` trần, nên dùng stub nhẹ tương tự
// quy ước `tests/setup.ts` (xem DataTable): chỉ render nội dung + slot
// `#footer` khi `visible` là true, đủ để bấm nút xác nhận/huỷ trong test.
const dialogStubWithFooterSlot = {
  props: ['visible'],
  template: `
    <div v-if="visible">
      <slot />
      <slot name="footer" />
    </div>
  `,
}

function mountQuoteEditorPage() {
  return mount(QuoteEditorPage, {
    global: {
      stubs: {
        AdminLayout: passthroughStub,
        Button: false,
        Select: true,
        DatePicker: true,
        InputNumber: true,
        InputText: true,
        Textarea: true,
        ExchangeRateField: true,
        Dialog: dialogStubWithFooterSlot,
      },
    },
  })
}

describe('QuoteEditorPage line removal confirmation', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    lines.value = [buildLine('material-1'), buildLine('material-2')]
    quoteEditorMock.removeLine.mockClear()
  })

  it('does not remove the line immediately on click — asks for confirmation first', async () => {
    const wrapper = mountQuoteEditorPage()

    await wrapper.find('[aria-label="Xóa dòng"]').trigger('click')

    expect(quoteEditorMock.removeLine).not.toHaveBeenCalled()
    expect(lines.value).toHaveLength(2)
  })

  it('removes the line only after confirming in the dialog', async () => {
    const wrapper = mountQuoteEditorPage()

    await wrapper.find('[aria-label="Xóa dòng"]').trigger('click')
    await wrapper.find('[data-testid="quote-editor-confirm-remove-line"]').trigger('click')

    expect(quoteEditorMock.removeLine).toHaveBeenCalledWith(0)
    expect(lines.value).toHaveLength(1)
  })

  it('keeps the line if the user cancels the confirmation', async () => {
    const wrapper = mountQuoteEditorPage()

    await wrapper.find('[aria-label="Xóa dòng"]').trigger('click')
    await wrapper.find('[data-testid="quote-editor-cancel-remove-line"]').trigger('click')

    expect(quoteEditorMock.removeLine).not.toHaveBeenCalled()
    expect(lines.value).toHaveLength(2)
  })
})
