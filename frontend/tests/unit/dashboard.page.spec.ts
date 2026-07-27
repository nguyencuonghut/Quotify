import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'

import DashboardPage from '@/pages/DashboardPage.vue'
import { useAuthStore } from '@/stores/auth.store'

describe('DashboardPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders the operational dashboard overview and permitted quick actions', () => {
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

    const wrapper = mount(DashboardPage, {
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

    expect(wrapper.text()).toContain('Bảng điều khiển')
    expect(wrapper.text()).toContain('Tổng quan vận hành')
    expect(wrapper.text()).toContain('Quản lý tài khoản')
    expect(wrapper.text()).toContain('Nhật ký audit')
    expect(wrapper.text()).toContain('Trạng thái vận hành')
    expect(wrapper.get('[data-testid="row-count"]').text()).toBe('5')
  })
})
