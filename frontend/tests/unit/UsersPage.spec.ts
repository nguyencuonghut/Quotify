import { mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import { defineComponent, ref } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useAuthStore } from '@/stores/auth.store'

const usersPageMock = vi.hoisted(() => ({
  fetchUsers: vi.fn(),
  fetchRoles: vi.fn(),
  openCreateDialog: vi.fn(),
  openEditDialog: vi.fn(),
  openDeleteDialog: vi.fn(),
  submitDelete: vi.fn(),
}))

const users = ref<Record<string, unknown>[]>([])

vi.mock('@/composables/useUsersPage', () => ({
  useUsersPage: () => ({
    users,
    totalUsers: ref(0),
    loading: ref(false),
    roles: ref([]),
    lazyParams: ref({ limit: 10, offset: 0, search: '', status_filter: null }),
    generalError: ref(null),
    submitError: ref(null),
    createDialogVisible: ref(false),
    editDialogVisible: ref(false),
    deleteDialogVisible: ref(false),
    selectedUser: ref(null),
    isDeleting: ref(false),
    ...usersPageMock,
  }),
}))

import UsersPage from '@/pages/UsersPage.vue'

const passthroughStub = defineComponent({
  template: '<div><slot /></div>',
})

// Nút Sửa/Xóa nằm trong `<Column><template #body="{ data }">`, CHỈ thực sự
// render khi DataTable xử lý và gọi slot `#body` cho từng dòng — stub tối
// giản kiểu passthrough (chỉ render `<slot/>` mặc định) sẽ để lộ nguyên các
// `<Column>` chưa qua xử lý, không có dữ liệu dòng nào để bấm nút. Dùng
// DataTable + Column THẬT (không stub) để có ít nhất 1 dòng render đúng,
// đủ để test hành vi disable/title trên nút thao tác.
let activeWrapper: VueWrapper | null = null

afterEach(() => {
  activeWrapper?.unmount()
  activeWrapper = null
})

function mountUsersPage() {
  activeWrapper = mount(UsersPage, {
    global: {
      // DataTable thật render `paginator` bên trong, cần plugin PrimeVue
      // (đọc `$primevue.config`) — không cài thì mất khi render Paginator
      // (lỗi thật gặp ngày 22/08/2026 khi viết test này).
      plugins: [PrimeVue],
      stubs: {
        AdminLayout: passthroughStub,
        Button: false,
        Column: false,
        DataTable: false,
        Dialog: true,
        FileUpload: true,
        InputText: true,
        MultiSelect: true,
        ProgressBar: true,
        Select: true,
        Tag: true,
      },
    },
  })
  return activeWrapper
}

describe('UsersPage row action permissions', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    users.value = [
      {
        id: 'user-2',
        email: 'other-user@quotify.local',
        fullName: 'Người dùng khác',
        status: 'active',
        roles: ['buyer'],
        lastLoginAt: null,
        avatarUrl: null,
      },
    ]
  })

  it('disables (not hides) the edit button with an explanatory title when the user lacks users.update', () => {
    const authStore = useAuthStore()
    authStore.currentUser = {
      id: 'admin-1',
      email: 'admin@quotify.local',
      status: 'active',
      roles: [],
      permissions: [],
      lastLoginAt: null,
    }

    const wrapper = mountUsersPage()

    const editButton = wrapper.find('[data-testid="users-page-edit-user"]')
    expect(editButton.exists()).toBe(true)
    expect(editButton.attributes('disabled')).toBeDefined()
    expect(editButton.attributes('title')).toBe('Bạn không có quyền chỉnh sửa tài khoản.')
  })

  it('enables the edit button with the normal title when the user has users.update', () => {
    const authStore = useAuthStore()
    authStore.currentUser = {
      id: 'admin-1',
      email: 'admin@quotify.local',
      status: 'active',
      roles: [],
      permissions: ['users.update'],
      lastLoginAt: null,
    }

    const wrapper = mountUsersPage()

    const editButton = wrapper.find('[data-testid="users-page-edit-user"]')
    expect(editButton.attributes('disabled')).toBeUndefined()
    expect(editButton.attributes('title')).toBe('Chỉnh sửa')
  })
})
