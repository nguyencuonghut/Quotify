import { mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useAuthStore } from '@/stores/auth.store'

const quoteDetailMock = vi.hoisted(() => ({
  loadQuote: vi.fn(),
  handleConfirm: vi.fn(),
  handleDeleteDraftVersion: vi.fn(),
  handleTogglePurchase: vi.fn(),
  handleUploadSourceFile: vi.fn(),
  getSourceFileDownloadUrl: vi.fn(),
  loadNote: vi.fn(),
  handleUpdateNote: vi.fn(),
  handleUpdateNoteRevision: vi.fn(),
  handleDeleteNoteRevision: vi.fn(),
}))

// Refs dùng chung, MUTATE trực tiếp `.value` ở từng test trước khi mount —
// đơn giản hơn nhiều so với reset module/mock lại theo từng test, và vẫn
// đúng ngữ nghĩa reactive vì đây là ref thật của Vue.
const quote = ref<Record<string, unknown> | null>(null)
const isLoading = ref(false)
const activeVersion = ref<Record<string, unknown> | null>(null)
const sortedVersions = ref<Record<string, unknown>[]>([])
const note = ref<Record<string, unknown> | null>(null)

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { quoteId: 'quote-1' } }),
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock('@/composables/useQuoteDetail', () => ({
  useQuoteDetail: () => ({
    quote,
    activeVersionId: ref(null),
    isLoading,
    errorMsg: ref(null),
    isConfirming: ref(false),
    isFileUploading: ref(false),
    sortedVersions,
    activeVersion,
    note,
    isSavingNote: ref(false),
    noteErrorMsg: ref(null),
    ...quoteDetailMock,
  }),
}))

import QuoteDetailPage from '@/pages/QuoteDetailPage.vue'

const passthroughStub = defineComponent({
  template: '<div><slot /></div>',
})

// Các `ref` mock ở trên là module-level, DÙNG CHUNG cho mọi test trong file
// — nếu không unmount wrapper cũ trước khi test tiếp theo mount 1 instance
// mới, instance cũ vẫn còn subscribe vào các ref đó, có thể gây tương tác
// chéo giữa các test (lỗi thật gặp khi viết test này ngày 22/08/2026: test
// đứng riêng thì pass, chạy chung file lại fail ngẫu nhiên). Theo dõi
// wrapper đang active + unmount trong `afterEach` để mỗi test luôn bắt đầu
// từ 1 instance sạch.
let activeWrapper: VueWrapper | null = null

afterEach(() => {
  activeWrapper?.unmount()
  activeWrapper = null
})

function mountQuoteDetailPage() {
  activeWrapper = mount(QuoteDetailPage, {
    global: {
      stubs: {
        AdminLayout: passthroughStub,
        Button: true,
        DataTable: true,
        Column: true,
        FileUpload: true,
        Checkbox: true,
        Dialog: true,
        Message: true,
        Editor: true,
        DatePicker: true,
        InputText: true,
        Select: true,
      },
    },
  })
  return activeWrapper
}

describe('QuoteDetailPage loading state', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    quote.value = null
    isLoading.value = false
    activeVersion.value = null
    sortedVersions.value = []
  })

  it('shows a loading indicator while the quote is being fetched', () => {
    isLoading.value = true

    const wrapper = mountQuoteDetailPage()

    expect(wrapper.find('.quote-detail-page__loading').exists()).toBe(true)
  })

  it('does not show the loading indicator once the quote has loaded', () => {
    isLoading.value = false
    quote.value = {
      id: 'quote-1',
      supplierId: 'supplier-1',
      supplierName: 'Supplier A',
      supplierCode: 'SUPA',
      createdById: 'user-1',
      createdAt: '2026-08-01T00:00:00Z',
      updatedAt: '2026-08-01T00:00:00Z',
      versions: [],
    }

    const wrapper = mountQuoteDetailPage()

    expect(wrapper.find('.quote-detail-page__loading').exists()).toBe(false)
  })
})

// Dialog thật của PrimeVue cần plugin `app.use(PrimeVue)` khi render (đọc
// `$primevue`) — không có trong `mount()` trần. Dùng stub nhẹ chỉ render
// nội dung + slot `#footer` khi `visible` là true, đủ để bấm nút xác
// nhận/huỷ trong test (cùng quy ước với `QuoteEditorPage.spec.ts`).
const dialogStubWithFooterSlot = {
  props: ['visible'],
  template: `
    <div v-if="visible">
      <slot />
      <slot name="footer" />
    </div>
  `,
}

function mountQuoteDetailPageForRevisionActions() {
  activeWrapper = mount(QuoteDetailPage, {
    global: {
      stubs: {
        AdminLayout: passthroughStub,
        Button: false,
        DataTable: true,
        Column: true,
        FileUpload: true,
        Checkbox: true,
        Dialog: dialogStubWithFooterSlot,
        Message: true,
        Editor: true,
        DatePicker: true,
        InputText: true,
        Select: true,
      },
    },
  })
  return activeWrapper
}

describe('QuoteDetailPage note revision deletion', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    const authStore = useAuthStore()
    authStore.currentUser = {
      id: 'user-1',
      email: 'admin@quotify.local',
      status: 'active',
      roles: ['admin'],
      permissions: ['quote_notes.update'],
      lastLoginAt: null,
    }

    quote.value = {
      id: 'quote-1',
      supplierId: 'supplier-1',
      supplierName: 'Supplier A',
      supplierCode: 'SUPA',
      createdById: 'user-1',
      createdAt: '2026-08-01T00:00:00Z',
      updatedAt: '2026-08-01T00:00:00Z',
      versions: [],
    }
    isLoading.value = false
    activeVersion.value = null
    sortedVersions.value = []
    note.value = {
      id: 'note-1',
      quoteId: 'quote-1',
      createdAt: '2026-08-01T00:00:00Z',
      updatedAt: '2026-08-01T00:00:00Z',
      revisions: [
        {
          id: 'revision-1',
          revisionNumber: 1,
          content: '<p>Ghi chú thị trường</p>',
          authorId: 'user-1',
          authorName: 'Người dùng A',
          authorAvatarUrl: null,
          createdAt: '2026-08-01T00:00:00Z',
        },
      ],
    }
    quoteDetailMock.handleDeleteNoteRevision.mockClear()
  })

  it('does not delete the revision immediately on click — asks for confirmation via a themed dialog, not window.confirm', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm')

    const wrapper = mountQuoteDetailPageForRevisionActions()
    await wrapper.find('[title="Xóa"]').trigger('click')

    expect(confirmSpy).not.toHaveBeenCalled()
    expect(quoteDetailMock.handleDeleteNoteRevision).not.toHaveBeenCalled()

    confirmSpy.mockRestore()
  })

  it('deletes the revision only after confirming in the dialog', async () => {
    const wrapper = mountQuoteDetailPageForRevisionActions()

    await wrapper.find('[title="Xóa"]').trigger('click')
    await wrapper.find('[data-testid="quote-detail-confirm-delete-revision"]').trigger('click')

    expect(quoteDetailMock.handleDeleteNoteRevision).toHaveBeenCalledWith('quote-1', 'revision-1')
  })

  it('keeps the revision if the user cancels the confirmation', async () => {
    const wrapper = mountQuoteDetailPageForRevisionActions()

    await wrapper.find('[title="Xóa"]').trigger('click')
    await wrapper.find('[data-testid="quote-detail-cancel-delete-revision"]').trigger('click')

    expect(quoteDetailMock.handleDeleteNoteRevision).not.toHaveBeenCalled()
  })
})
