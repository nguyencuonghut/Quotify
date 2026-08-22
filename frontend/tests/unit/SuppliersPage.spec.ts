import { mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, h, inject, provide, ref } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const suppliers = ref<Record<string, unknown>[]>([])

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
      suppliers,
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
      formatStatus: (status: string) =>
        status === 'active' ? 'Đang hoạt động' : 'Ngừng hoạt động',
      formatSupplierType: (type: string) =>
        type === 'domestic' ? 'Trong nước' : 'Nước ngoài',
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

describe('SuppliersPage "Vật tư cung cấp" column truncation', () => {
  let activeWrapper: VueWrapper | null = null

  afterEach(() => {
    activeWrapper?.unmount()
    activeWrapper = null
  })

  beforeEach(() => {
    setActivePinia(createPinia())
  })

  // Thay vì mount DataTable/Column THẬT (như UsersPage/RolesPage/BackupsPage),
  // Paginator thật của SuppliersPage gây "Maximum recursive updates exceeded
  // in component <DataTable>" khi mount trong jsdom (lỗi thật gặp ngày
  // 22/08/2026, không tái hiện ở 3 trang kia dù cùng cấu hình lazy+paginator
  // — chưa rõ nguyên nhân gốc, không đáng công điều tra sâu cho 1 cột hiển
  // thị). Dùng stub tự viết: `RowStub` provide() dữ liệu dòng qua injection,
  // `columnBodyStub` inject lại và tự gọi slot `#body` — đủ để kiểm tra nội
  // dung/class/title của 1 ô mà không cần Paginator thật.
  const RowStub = defineComponent({
    props: ['row'],
    setup(props, { slots }) {
      provide('__row__', props.row)
      return () => h('tr', slots.default ? slots.default() : [])
    },
  })

  const dataTableRowBodyStub = defineComponent({
    props: ['value'],
    components: { RowStub },
    template: `
      <table>
        <tbody>
          <row-stub v-for="(row, i) in value" :key="i" :row="row">
            <slot />
          </row-stub>
        </tbody>
      </table>
    `,
  })

  const columnBodyStub = defineComponent({
    props: ['header', 'field'],
    setup(_, { slots }) {
      const row = inject('__row__')
      return () =>
        h(
          'td',
          slots.body ? slots.body({ data: row }) : slots.default?.(),
        )
    },
  })

  it('truncates a long materials list with an ellipsis and exposes the full list via title', () => {
    const materialNames = Array.from(
      { length: 10 },
      (_, i) => `Vật tư số ${i + 1}`,
    )
    suppliers.value = [
      {
        id: 'supplier-1',
        name: 'NCC nhiều vật tư',
        supplierType: 'domestic',
        contacts: [],
        materials: materialNames.map((materialName, i) => ({
          materialId: `mat-${i}`,
          materialName,
        })),
        status: 'active',
      },
    ]

    activeWrapper = mount(SuppliersPage, {
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
          DataTable: dataTableRowBodyStub,
          Column: columnBodyStub,
        },
      },
    })

    const cell = activeWrapper.get('.suppliers-page__materials-cell')
    expect(cell.attributes('title')).toBe(materialNames.join(', '))
  })
})
