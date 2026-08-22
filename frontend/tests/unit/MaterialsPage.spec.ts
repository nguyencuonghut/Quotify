import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent } from 'vue'
import { describe, expect, it, vi } from 'vitest'

const materialsPageMock = vi.hoisted(() => ({
  fetchMaterials: vi.fn(),
  fetchMaterialTypesLookup: vi.fn(),
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

vi.mock('@/composables/useMaterialsPage', async () => {
  const { ref } = await import('vue')
  return {
    useMaterialsPage: () => ({
      materials: ref([]),
      materialTypes: ref([]),
      totalMaterials: ref(0),
      loading: ref(false),
      generalError: ref(null),
      submitError: ref(null),
      selectedMaterial: ref(null),
      createDialogVisible: ref(false),
      editDialogVisible: ref(false),
      deleteDialogVisible: ref(false),
      isDeleting: ref(false),
      lazyParams: ref({ limit: 10, search: '', material_type_id: null, status: null }),
      ...materialsPageMock,
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

import MaterialsPage from '@/pages/MaterialsPage.vue'

const passthroughStub = defineComponent({
  template: '<div><slot /></div>',
})

// `tests/setup.ts` stub DataTable mặc định (dùng chung cho mọi test) CHỈ
// render <slot/> mặc định (Column) + số dòng — không gọi slot có tên
// `#empty`, nên không thể phát hiện thiếu empty-state qua stub đó. Override
// riêng cho test này bằng 1 stub tương tự nhưng có thêm nhánh render
// `#empty` khi `value` rỗng, để thực sự khoá lại hành vi mong muốn.
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

function mountMaterialsPage() {
  return mount(MaterialsPage, {
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

describe('MaterialsPage empty state', () => {
  it('shows a Vietnamese empty-state message in the desktop table when there are no materials', () => {
    setActivePinia(createPinia())

    const wrapper = mountMaterialsPage()

    expect(wrapper.text()).toContain('Không tìm thấy vật tư phù hợp')
  })
})
