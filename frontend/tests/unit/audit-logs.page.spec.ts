import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { reactive, ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AdminLayout from '@/layouts/AdminLayout.vue'
import AuditLogsPage from '@/pages/AuditLogsPage.vue'
import { router } from '@/router'
import { useAuthStore } from '@/stores/auth.store'

const auditLogsPageMock = vi.hoisted(() => ({
  useAuditLogsPage: vi.fn(),
}))

vi.mock('@/composables/useAuditLogsPage', () => auditLogsPageMock)

function buildComposableState(overrides: Record<string, unknown> = {}) {
  return {
    auditLogs: ref([]),
    totalAuditLogs: ref(0),
    loading: ref(false),
    generalError: ref(null),
    rows: ref(10),
    first: ref(0),
    rowsPerPageOptions: [10, 20, 30, 50],
    filters: reactive({
      actorUserId: '',
      action: '',
      entityType: '',
      entityId: '',
      requestId: '',
      createdFrom: '',
      createdTo: '',
    }),
    selectedAuditLog: ref(null),
    metadataDialogVisible: ref(false),
    formattedMetadata: ref('{}'),
    fetchAuditLogs: vi.fn(),
    onPageChange: vi.fn(),
    applyFilters: vi.fn(),
    clearFilters: vi.fn(),
    openMetadataDialog: vi.fn(),
    ...overrides,
  }
}

describe('AuditLogsPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('renders empty state from the audit log table', () => {
    auditLogsPageMock.useAuditLogsPage.mockReturnValue(buildComposableState())

    const wrapper = mount(AuditLogsPage, {
      global: {
        stubs: {
          AdminLayout: {
            template: '<section><slot /></section>',
          },
          DataTable: {
            props: ['value', 'loading'],
            template:
              '<div><div v-if="loading">Đang tải</div><slot v-if="!value.length" name="empty" /><slot /></div>',
          },
          Dialog: {
            template: '<aside><slot /></aside>',
          },
          Select: true,
        },
      },
    })

    expect(wrapper.text()).toContain('Chưa có nhật ký audit phù hợp.')
  })

  it('renders loading state', () => {
    auditLogsPageMock.useAuditLogsPage.mockReturnValue(
      buildComposableState({
        loading: ref(true),
      }),
    )

    const wrapper = mount(AuditLogsPage, {
      global: {
        stubs: {
          AdminLayout: {
            template: '<section><slot /></section>',
          },
          DataTable: {
            props: ['value', 'loading'],
            template: '<div><div v-if="loading">Đang tải</div><slot /></div>',
          },
          Dialog: {
            template: '<aside><slot /></aside>',
          },
          Select: true,
        },
      },
    })

    expect(wrapper.text()).toContain('Đang tải')
  })

  it('renders error state without showing table empty state', () => {
    auditLogsPageMock.useAuditLogsPage.mockReturnValue(
      buildComposableState({
        generalError: ref('Không thể tải nhật ký audit.'),
      }),
    )

    const wrapper = mount(AuditLogsPage, {
      global: {
        stubs: {
          AdminLayout: {
            template: '<section><slot /></section>',
          },
          DataTable: {
            props: ['value', 'loading'],
            template:
              '<div><div v-if="loading">Đang tải</div><slot v-if="!value.length" name="empty" /><slot /></div>',
          },
          Dialog: {
            template: '<aside><slot /></aside>',
          },
          Select: true,
        },
      },
    })

    expect(wrapper.text()).toContain('Không thể tải nhật ký audit.')
    expect(wrapper.text()).not.toContain('Chưa có nhật ký audit phù hợp.')
  })

  it('registers audit log route with audit.read permission', () => {
    const auditRoute = router
      .getRoutes()
      .find((route) => route.name === 'audit-logs')

    expect(auditRoute?.path).toBe('/audit-logs')
    expect(auditRoute?.meta.requiredPermission).toBe('audit.read')
  })

  it('groups sidebar user and system navigation separately', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const authStore = useAuthStore()
    authStore.accessToken = 'access-token'
    authStore.currentUser = {
      id: 'user-1',
      email: 'admin@example.com',
      status: 'active',
      roles: ['admin'],
      permissions: [
        'dashboard.read',
        'users.read',
        'roles.read',
        'files.read',
        'backups.read',
        'audit.read',
      ],
      lastLoginAt: null,
      fullName: 'Admin',
      avatarUrl: null,
    }

    vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
    } as Response)

    const wrapper = mount(AdminLayout, {
      props: {
        title: 'Trang thử nghiệm',
      },
      global: {
        plugins: [pinia],
        stubs: {
          RouterLink: {
            props: ['to'],
            template: '<a :href="to"><slot /></a>',
          },
          Menu: true,
          ThemeModeSwitch: true,
        },
      },
    })

    const sections = wrapper.findAll('.admin-layout__nav-section')

    expect(sections).toHaveLength(3)
    expect(sections[1].text()).toContain('Người dùng')
    expect(sections[1].text()).toContain('Quản lý tài khoản')
    expect(sections[1].text()).toContain('Quản lý vai trò')
    expect(sections[1].text()).not.toContain('Nhật ký audit')
    expect(sections[2].text()).toContain('Hệ thống')
    expect(sections[2].text()).toContain('Quản lý tập tin')
    expect(sections[2].text()).toContain('Quản lý sao lưu')
    expect(sections[2].text()).toContain('Nhật ký audit')
  })

  it('shows sidebar audit link only when the user has audit.read', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const authStore = useAuthStore()
    authStore.accessToken = 'access-token'
    authStore.currentUser = {
      id: 'user-1',
      email: 'admin@example.com',
      status: 'active',
      roles: ['admin'],
      permissions: ['audit.read'],
      lastLoginAt: null,
      fullName: 'Admin',
      avatarUrl: null,
    }

    vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
    } as Response)

    const wrapper = mount(AdminLayout, {
      props: {
        title: 'Trang thử nghiệm',
      },
      global: {
        plugins: [pinia],
        stubs: {
          RouterLink: {
            props: ['to'],
            template: '<a :href="to"><slot /></a>',
          },
          Menu: true,
          ThemeModeSwitch: true,
        },
      },
    })

    expect(wrapper.text()).toContain('Nhật ký audit')
    expect(wrapper.find('a[href="/audit-logs"]').exists()).toBe(true)
  })

  it('hides sidebar audit link when the user lacks audit.read', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const authStore = useAuthStore()
    authStore.accessToken = 'access-token'
    authStore.currentUser = {
      id: 'user-1',
      email: 'user@example.com',
      status: 'active',
      roles: ['user'],
      permissions: ['dashboard.read'],
      lastLoginAt: null,
      fullName: 'User',
      avatarUrl: null,
    }

    vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
    } as Response)

    const wrapper = mount(AdminLayout, {
      props: {
        title: 'Trang thử nghiệm',
      },
      global: {
        plugins: [pinia],
        stubs: {
          RouterLink: {
            props: ['to'],
            template: '<a :href="to"><slot /></a>',
          },
          Menu: true,
          ThemeModeSwitch: true,
        },
      },
    })

    expect(wrapper.find('a[href="/audit-logs"]').exists()).toBe(false)
  })
})
