import { mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('vue-router', async () => {
  const actual = await vi.importActual<typeof import('vue-router')>('vue-router')
  return {
    ...actual,
    useRoute: () => ({ path: '/' }),
    useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  }
})

import { useAuthStore } from '@/stores/auth.store'
import { useLayoutStore } from '@/stores/layout.store'

import AdminLayout from '@/layouts/AdminLayout.vue'

const routerLinkStub = defineComponent({
  props: ['to'],
  template: '<a :href="to"><slot /></a>',
})

let activeWrapper: VueWrapper | null = null

afterEach(() => {
  activeWrapper?.unmount()
  activeWrapper = null
})

beforeEach(() => {
  setActivePinia(createPinia())
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({ ok: true } as Response),
  )
})

function mountAdminLayout() {
  const authStore = useAuthStore()
  authStore.currentUser = {
    id: 'admin-1',
    email: 'admin@quotify.local',
    status: 'active',
    roles: [],
    permissions: ['dashboard.read', 'quotes.read', 'quotes.create'],
    lastLoginAt: null,
  }

  activeWrapper = mount(AdminLayout, {
    props: { title: 'Trang test' },
    global: {
      stubs: {
        RouterLink: routerLinkStub,
        Button: false,
        Menu: true,
        ThemeModeSwitch: true,
      },
    },
    slots: { default: '<div>Nội dung trang</div>' },
  })
  return activeWrapper
}

describe('AdminLayout', () => {
  it('shows a title on each nav link with the item label', () => {
    const wrapper = mountAdminLayout()

    const navLinks = wrapper.findAll('.admin-layout__nav-link')
    expect(navLinks.length).toBeGreaterThan(0)
    for (const link of navLinks) {
      const label = link.find('.admin-layout__nav-label').text()
      expect(link.attributes('title')).toBe(label)
    }
  })

  it('renders a skip-to-content link as the first element, targeting the main content', () => {
    const wrapper = mountAdminLayout()

    const skipLink = wrapper.find('.admin-layout__skip-link')
    expect(skipLink.exists()).toBe(true)
    expect(skipLink.element).toBe(wrapper.element.firstElementChild)
    expect(skipLink.attributes('href')).toBe('#admin-layout-main')

    const main = wrapper.find('main.admin-layout__content')
    expect(main.attributes('id')).toBe('admin-layout-main')
  })

  it('uses Vietnamese text for the mobile menu backdrop, sidebar toggle and logout item', () => {
    const layoutStore = useLayoutStore()
    layoutStore.mobileSidebarOpen = true

    const wrapper = mountAdminLayout()

    const backdrop = wrapper.find('.admin-layout__backdrop')
    expect(backdrop.attributes('aria-label')).toBe('Đóng menu')

    const sidebarToggle = wrapper.find('.admin-layout__sidebar-toggle')
    expect(sidebarToggle.attributes('aria-label')).toBe('Thu gọn sidebar')

    const vm = wrapper.vm as unknown as {
      profileMenuItems: Array<{ label: string }>
    }
    expect(vm.profileMenuItems.some((item) => item.label === 'Đăng xuất')).toBe(
      true,
    )
  })
})
