import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent } from 'vue'
import { describe, expect, it, vi } from 'vitest'

const suppliersPageMock = vi.hoisted(() => ({
  fetchSuppliers: vi.fn(),
  fetchMaterialsLookup: vi.fn(),
  openCreateDialog: vi.fn(),
  openEditDialog: vi.fn(),
  openDeleteDialog: vi.fn(),
  submitDelete: vi.fn(),
  addContact: vi.fn(),
  removeContact: vi.fn(),
}))

const catalogImportMock = vi.hoisted(() => ({
  openImportDialog: vi.fn(),
  handleImportUpload: vi.fn(),
  downloadTemplate: vi.fn(),
  downloadErrorFile: vi.fn(),
}))

vi.mock('@/composables/useSuppliersPage', async () => {
  const { ref } = await import('vue')
  return {
    catalogStatusOptions: [
      { label: 'Đang hoạt động', value: 'active' },
      { label: 'Ngừng hoạt động', value: 'inactive' },
    ],
    statusFilterOptions: [
      { label: 'Đang hoạt động', value: 'active' },
      { label: 'Ngừng hoạt động', value: 'inactive' },
    ],
    supplierTypeFilterOptions: [
      { label: 'Trong nước', value: 'domestic' },
      { label: 'Nước ngoài', value: 'international' },
    ],
    supplierTypeOptions: [
      { label: 'Trong nước', value: 'domestic' },
      { label: 'Nước ngoài', value: 'international' },
    ],
    useSuppliersPage: () => ({
      suppliers: ref([]),
      materials: ref([]),
      totalSuppliers: ref(0),
      loading: ref(false),
      generalError: ref(null),
      submitError: ref(null),
      selectedSupplier: ref(null),
      createDialogVisible: ref(false),
      editDialogVisible: ref(false),
      deleteDialogVisible: ref(false),
      isDeleting: ref(false),
      createContacts: ref([]),
      editContacts: ref([]),
      createMaterialIds: ref([]),
      editMaterialIds: ref([]),
      lazyParams: ref({ limit: 10, offset: 0, search: '', supplier_type: null, status: null }),
      ...suppliersPageMock,
    }),
  }
})

vi.mock('@/composables/useCatalogImport', async () => {
  const { ref } = await import('vue')
  return {
    useCatalogImport: () => ({
      importDialogVisible: ref(false),
      importJob: ref(null),
      importError: ref(null),
      uploadingImport: ref(false),
      fileAccept: ref('.csv'),
      fileFormatLabel: ref('CSV'),
      ...catalogImportMock,
    }),
  }
})

import SuppliersPage from '@/pages/SuppliersPage.vue'

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

function mountSuppliersPage() {
  return mount(SuppliersPage, {
    global: {
      stubs: {
        AdminLayout: passthroughStub,
        Button: true,
        FileUpload: true,
        InputText: true,
        MultiSelect: true,
        ProgressBar: true,
        Select: true,
        Tag: true,
        Textarea: true,
        Dialog: true,
        DataTable: dataTableStubWithEmptySlot,
      },
    },
  })
}

describe('SuppliersPage empty state', () => {
  it('shows a Vietnamese empty-state message in the desktop table when there are no suppliers', () => {
    setActivePinia(createPinia())

    const wrapper = mountSuppliersPage()

    expect(wrapper.text()).toContain('Không tìm thấy nhà cung cấp phù hợp')
  })
})
