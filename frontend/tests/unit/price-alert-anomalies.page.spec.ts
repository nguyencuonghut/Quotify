import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AdminLayout from '@/layouts/AdminLayout.vue'
import PriceAlertAnomaliesPage from '@/pages/PriceAlertAnomaliesPage.vue'
import { router } from '@/router'
import { useAuthStore } from '@/stores/auth.store'
import type { AnomalyDomain } from '@/types/price-alert-anomalies'

const composableMock = vi.hoisted(() => ({
  usePriceAlertAnomaliesPage: vi.fn(),
}))

vi.mock('@/composables/usePriceAlertAnomaliesPage', () => composableMock)

function item(overrides: Partial<AnomalyDomain> = {}): AnomalyDomain {
  return {
    id: 'event-1',
    materialId: 'material-1',
    materialName: 'Threonine',
    deliveryMonthLabel: '11/2026',
    receivedDateLabel: '15/09/2026',
    priceLabel: '970',
    medianLabel: '25.600',
    percentLabel: '▼96,21%',
    direction: 'down',
    referenceLabel: '25.600 · 25.435',
    lowConfidence: true,
    quoteId: 'quote-1',
    enteredByName: 'Hồng',
    status: 'pending',
    statusLabel: 'Chờ duyệt',
    statusSeverity: 'warn',
    isPending: true,
    attachedCount: 2,
    ageLabel: '3 ngày làm việc',
    createdAtLabel: '10:00 15/09/2026',
    reviewerLabel: null,
    ...overrides,
  }
}

function state(overrides: Record<string, unknown> = {}) {
  return {
    tab: ref('pending'),
    anomalies: ref([item()]),
    total: ref(1),
    loading: ref(false),
    generalError: ref(null),
    rows: ref(10),
    first: ref(0),
    rowsPerPageOptions: [10, 20, 30, 50],
    confirmVisible: ref(false),
    confirmTarget: ref(null),
    confirmDecisionValue: ref('accepted'),
    isBusy: ref(false),
    errorMessage: ref(null),
    successMessage: ref(null),
    fetchAnomalies: vi.fn(),
    onPageChange: vi.fn(),
    setTab: vi.fn(),
    openConfirm: vi.fn(),
    closeConfirm: vi.fn(),
    confirmDecision: vi.fn(),
    ...overrides,
  }
}

function mountPage() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const authStore = useAuthStore()
  authStore.currentUser = {
    id: 'user-1',
    email: 'manager@example.com',
    status: 'active',
    roles: ['manager'],
    permissions: ['price_alerts.receive_all'],
    lastLoginAt: null,
    fullName: 'Quản lý',
    avatarUrl: null,
  }
  return mount(PriceAlertAnomaliesPage, {
    global: {
      plugins: [pinia],
      stubs: {
        AdminLayout: { template: '<section><slot /></section>' },
        DataTable: { template: '<div><slot name="empty" /></div>' },
        Dialog: {
          props: ['visible'],
          template: '<aside><slot /><slot name="footer" /></aside>',
        },
      },
    },
  })
}

describe('PriceAlertAnomaliesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows each card with its evidence and review buttons for a pending point', () => {
    composableMock.usePriceAlertAnomaliesPage.mockReturnValue(state())

    const wrapper = mountPage()
    const cards = wrapper.get('[data-testid="anomaly-cards"]')

    expect(cards.text()).toContain('Threonine')
    expect(cards.text()).toContain('Kỳ giao hàng 11/2026')
    expect(cards.text()).toContain('▼96,21%')
    expect(cards.text()).toContain('Giá gần đây: 25.600 · 25.435')
    expect(cards.text()).toContain('Độ tin cậy thấp')
    expect(cards.text()).toContain('Hồng')
    expect(cards.text()).toContain('Giá đúng')
    expect(cards.text()).toContain('Nhập sai')
    expect(cards.get('a').attributes('href')).toBe('/quotes/quote-1')
  })

  it('asks the composable to confirm with the chosen decision', async () => {
    const mocked = state()
    composableMock.usePriceAlertAnomaliesPage.mockReturnValue(mocked)

    const wrapper = mountPage()
    const buttons = wrapper
      .get('[data-testid="anomaly-cards"]')
      .findAll('button')
    await buttons.find((b) => b.text() === 'Giá đúng')!.trigger('click')
    await buttons.find((b) => b.text() === 'Nhập sai')!.trigger('click')

    expect(mocked.openConfirm).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({ id: 'event-1' }),
      'accepted',
    )
    expect(mocked.openConfirm).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({ id: 'event-1' }),
      'rejected',
    )
  })

  it('shows no buttons for a point that was already handled, and who handled it', () => {
    composableMock.usePriceAlertAnomaliesPage.mockReturnValue(
      state({
        tab: ref('resolved'),
        anomalies: ref([
          item({
            isPending: false,
            status: 'accepted',
            statusLabel: 'Đã xác nhận giá đúng',
            statusSeverity: 'success',
            reviewerLabel: 'Tony · 13:24 05/10/2026',
          }),
        ]),
      }),
    )

    const cards = mountPage().get('[data-testid="anomaly-cards"]')

    expect(cards.text()).toContain('Đã xác nhận giá đúng')
    expect(cards.text()).toContain('Tony · 13:24 05/10/2026')
    expect(cards.findAll('button')).toHaveLength(0)
  })

  it('disables the review buttons while a request is running', () => {
    composableMock.usePriceAlertAnomaliesPage.mockReturnValue(
      state({ isBusy: ref(true) }),
    )

    const buttons = mountPage()
      .get('[data-testid="anomaly-cards"]')
      .findAll('button')

    expect(buttons.length).toBe(2)
    for (const button of buttons) {
      expect(button.attributes('disabled')).toBeDefined()
    }
  })

  it('confirms through the dialog and shows what the decision means', async () => {
    const mocked = state({
      confirmVisible: ref(true),
      confirmTarget: ref(item()),
      confirmDecisionValue: ref('rejected'),
    })
    composableMock.usePriceAlertAnomaliesPage.mockReturnValue(mocked)

    const wrapper = mountPage()

    expect(
      wrapper.get('[data-testid="anomaly-confirm-text"]').text(),
    ).toContain('Phiếu báo giá không bị thay đổi')
    await wrapper.get('[data-testid="anomaly-confirm"]').trigger('click')
    expect(mocked.confirmDecision).toHaveBeenCalledTimes(1)
  })

  it('shows success and error messages inline and the empty states', () => {
    composableMock.usePriceAlertAnomaliesPage.mockReturnValue(
      state({
        anomalies: ref([]),
        total: ref(0),
        successMessage: ref('Đã ghi nhận giá đúng cho Threonine (kỳ 11/2026).'),
        errorMessage: ref('Bạn không có quyền duyệt giá bất thường.'),
      }),
    )

    const wrapper = mountPage()

    expect(
      wrapper.get('[data-testid="anomalies-success"]').attributes('role'),
    ).toBe('status')
    expect(
      wrapper.get('[data-testid="anomalies-error"]').attributes('role'),
    ).toBe('alert')
    expect(wrapper.text()).toContain('Không có điểm giá nào đang chờ duyệt.')
  })

  it('switches tabs through the composable and hides the table on a load error', async () => {
    const mocked = state({
      generalError: ref('Không thể tải danh sách giá bất thường.'),
    })
    composableMock.usePriceAlertAnomaliesPage.mockReturnValue(mocked)

    const wrapper = mountPage()
    await wrapper.get('[data-testid="anomalies-tab-resolved"]').trigger('click')

    expect(mocked.setTab).toHaveBeenCalledWith('resolved')
    expect(wrapper.text()).toContain('Không thể tải danh sách giá bất thường.')
    expect(wrapper.find('[data-testid="anomaly-cards"]').exists()).toBe(false)
  })

  it('registers the route guarded by price_alerts.receive_all', () => {
    const route = router
      .getRoutes()
      .find((r) => r.name === 'price-alert-anomalies')

    expect(route?.path).toBe('/price-alert-anomalies')
    expect(route?.meta.requiredPermission).toBe('price_alerts.receive_all')
    expect(route?.meta.requiresAuth).toBe(true)
  })

  it.each([
    [['price_alerts.receive_all'], true],
    [['quotes.read'], false],
  ])(
    'shows the sidebar link only with the permission %j',
    (permissions, visible) => {
      const pinia = createPinia()
      setActivePinia(pinia)
      const authStore = useAuthStore()
      authStore.accessToken = 'access-token'
      authStore.currentUser = {
        id: 'user-1',
        email: 'user@example.com',
        status: 'active',
        roles: ['manager'],
        permissions,
        lastLoginAt: null,
        fullName: 'Người dùng',
        avatarUrl: null,
      }
      vi.spyOn(global, 'fetch').mockResolvedValue({ ok: true } as Response)

      const wrapper = mount(AdminLayout, {
        props: { title: 'Trang thử nghiệm' },
        global: {
          plugins: [pinia, router],
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

      expect(wrapper.text().includes('Giá bất thường')).toBe(visible)
    },
  )
})
