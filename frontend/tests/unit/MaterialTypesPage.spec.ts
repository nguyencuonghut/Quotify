import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent } from 'vue'
import { describe, expect, it, vi } from 'vitest'

const materialTypesPageMock = vi.hoisted(() => ({
  fetchMaterialTypes: vi.fn(),
  openCreateDialog: vi.fn(),
  openEditDialog: vi.fn(),
  openDeleteDialog: vi.fn(),
  submitDelete: vi.fn(),
}))

const catalogImportMock = vi.hoisted(() => ({
  openImportDialog: vi.fn(),
  handleImportUpload: vi.fn(),
  downloadTemplate: vi.fn(),
  downloadErrorFile: vi.fn(),
}))

vi.mock('@/composables/useMaterialTypesPage', async () => {
  const { ref } = await import('vue')
  return {
    catalogStatusOptions: [
      { label: 'Đang hoạt động', value: 'active' },
      { label: 'Ngừng hoạt động', value: 'inactive' },
    ],
    useMaterialTypesPage: () => ({
      materialTypes: ref([]),
      totalMaterialTypes: ref(0),
      loading: ref(false),
      generalError: ref(null),
      submitError: ref(null),
      selectedMaterialType: ref(null),
      createDialogVisible: ref(false),
      editDialogVisible: ref(false),
      deleteDialogVisible: ref(false),
      isDeleting: ref(false),
      lazyParams: ref({ limit: 10, offset: 0, search: '', status: null }),
      ...materialTypesPageMock,
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

import MaterialTypesPage from '@/pages/MaterialTypesPage.vue'

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

function mountMaterialTypesPage() {
  return mount(MaterialTypesPage, {
    global: {
      stubs: {
        AdminLayout: passthroughStub,
        Button: true,
        FileUpload: true,
        InputText: true,
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

describe('MaterialTypesPage empty state', () => {
  it('shows a Vietnamese empty-state message in the desktop table when there are no material types', () => {
    setActivePinia(createPinia())

    const wrapper = mountMaterialTypesPage()

    expect(wrapper.text()).toContain('Không tìm thấy loại vật tư phù hợp')
  })
})
