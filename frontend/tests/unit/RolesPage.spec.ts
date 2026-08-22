import { mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import { defineComponent, ref } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useAuthStore } from '@/stores/auth.store'

const rolesPageMock = vi.hoisted(() => ({
  fetchRoles: vi.fn(),
  fetchPermissions: vi.fn(),
  openCreateDialog: vi.fn(),
  openEditDialog: vi.fn(),
  openDeleteDialog: vi.fn(),
  submitDelete: vi.fn(),
}))

const roles = ref<Record<string, unknown>[]>([])

vi.mock('@/composables/useRolesPage', () => ({
  useRolesPage: () => ({
    roles,
    totalRoles: ref(0),
    loading: ref(false),
    permissions: ref([]),
    lazyParams: ref({ limit: 10, offset: 0, search: '' }),
    generalError: ref(null),
    submitError: ref(null),
    createDialogVisible: ref(false),
    editDialogVisible: ref(false),
    deleteDialogVisible: ref(false),
    selectedRole: ref(null),
    isDeleting: ref(false),
    ...rolesPageMock,
  }),
}))

import RolesPage from '@/pages/RolesPage.vue'

const passthroughStub = defineComponent({
  template: '<div><slot /></div>',
})

let activeWrapper: VueWrapper | null = null

afterEach(() => {
  activeWrapper?.unmount()
  activeWrapper = null
})

// jsdom không implement `window.matchMedia` — Paginator thật của DataTable
// (dropdown chọn số dòng/trang, dùng nội bộ 1 component kiểu Select) gọi
// `matchMedia` lúc mount để theo dõi responsive breakpoint, nếu không có
// sẽ throw ngay khi mount (lỗi thật gặp ngày 22/08/2026 khi viết test này).
beforeEach(() => {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }))
})

function mountRolesPage() {
  activeWrapper = mount(RolesPage, {
    global: {
      plugins: [PrimeVue],
      stubs: {
        AdminLayout: passthroughStub,
        Button: false,
        Column: false,
        DataTable: false,
        Dialog: true,
        InputText: true,
        MultiSelect: true,
        Tag: true,
      },
    },
  })
  return activeWrapper
}

function setPermissions(permissions: string[]) {
  const authStore = useAuthStore()
  authStore.currentUser = {
    id: 'admin-1',
    email: 'admin@quotify.local',
    status: 'active',
    roles: [],
    permissions,
    lastLoginAt: null,
  }
}

describe('RolesPage row action permissions and system-role guard', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    roles.value = [
      {
        id: 'role-1',
        name: 'Thu mua',
        description: 'Vai trò thu mua',
        isSystem: false,
        permissions: ['quotes.read'],
      },
    ]
  })

  it('disables the edit button with an explanatory title when the user lacks roles.update', () => {
    setPermissions([])

    const wrapper = mountRolesPage()

    const editButton = wrapper.find('[data-testid="roles-page-edit-role"]')
    expect(editButton.exists()).toBe(true)
    expect(editButton.attributes('disabled')).toBeDefined()
    expect(editButton.attributes('title')).toBe('Bạn không có quyền chỉnh sửa vai trò.')
  })

  it('enables the edit button when the user has roles.update', () => {
    setPermissions(['roles.update'])

    const wrapper = mountRolesPage()

    const editButton = wrapper.find('[data-testid="roles-page-edit-role"]')
    expect(editButton.attributes('disabled')).toBeUndefined()
    expect(editButton.attributes('title')).toBe('Chỉnh sửa')
  })

  it('disables the delete button with an explanatory title for a system role even with roles.delete', () => {
    setPermissions(['roles.delete'])
    roles.value = [
      {
        id: 'role-system',
        name: 'Admin',
        description: 'Vai trò hệ thống',
        isSystem: true,
        permissions: [],
      },
    ]

    const wrapper = mountRolesPage()

    const deleteButton = wrapper.find('[data-testid="roles-page-delete-role"]')
    expect(deleteButton.attributes('disabled')).toBeDefined()
    expect(deleteButton.attributes('title')).toBe('Vai trò hệ thống không thể xóa.')
  })

  it('disables the delete button with a permission explanation when lacking roles.delete on a non-system role', () => {
    setPermissions([])

    const wrapper = mountRolesPage()

    const deleteButton = wrapper.find('[data-testid="roles-page-delete-role"]')
    expect(deleteButton.attributes('disabled')).toBeDefined()
    expect(deleteButton.attributes('title')).toBe('Bạn không có quyền xóa vai trò.')
  })
})
