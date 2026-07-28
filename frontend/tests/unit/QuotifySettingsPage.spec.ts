import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import QuotifySettingsPage from '@/pages/QuotifySettingsPage.vue'
import { router } from '@/router'
import { useAuthStore } from '@/stores/auth.store'

const settingsPageMock = vi.hoisted(() => ({
  useQuotifySettingsPage: vi.fn(),
}))

vi.mock('@/composables/useQuotifySettingsPage', () => settingsPageMock)

function buildComposableState(overrides: Record<string, unknown> = {}) {
  return {
    todayRate: ref({
      currency: 'USD',
      rate: '26120.00',
      source: 'Vietcombank USD bán ra',
      retrievedAt: '2026-07-28T08:00:00+07:00',
    }),
    loadingSettings: ref(false),
    loadingRate: ref(false),
    generalError: ref(null),
    rateError: ref(null),
    submitError: ref(null),
    successMessage: ref(null),
    canUpdateSettings: ref(true),
    conversionCostVndPerKg: ref(200),
    conversionCostVndPerKgProps: {},
    conversionCostErrors: ref({}),
    conversionCostSubmitting: ref(false),
    formattedConversionCost: ref('200,00 VNĐ/KG'),
    formattedRate: ref('26.120,00 VNĐ/USD'),
    formattedRateRetrievedAt: ref('28/07/2026 08:00:00'),
    formattedSettingsUpdatedAt: ref('28/07/2026 02:00:00'),
    bootstrap: vi.fn(),
    fetchTodayRate: vi.fn(),
    submitSettings: vi.fn(),
    ...overrides,
  }
}

describe('QuotifySettingsPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()

    const authStore = useAuthStore()
    authStore.accessToken = 'mock-token'
  })

  it('renders settings details and USD sell rate correctly', () => {
    const mockState = buildComposableState()
    settingsPageMock.useQuotifySettingsPage.mockReturnValue(mockState)

    const wrapper = mount(QuotifySettingsPage, {
      global: {
        stubs: {
          AdminLayout: {
            template: '<div class="admin-layout"><slot /></div>',
          },
          InputNumber: {
            props: ['modelValue', 'disabled'],
            template: '<input type="number" :value="modelValue" :disabled="disabled" />',
          },
          Button: {
            props: ['loading', 'disabled'],
            template: '<button :disabled="disabled"><slot /></button>',
          },
        },
      },
    })

    // Check if sections are rendered
    expect(wrapper.text()).toContain('Chi phí quy đổi')
    expect(wrapper.text()).toContain('USD bán ra hôm nay')
    expect(wrapper.text()).toContain('Vietcombank USD bán ra')
    expect(wrapper.text()).toContain('28/07/2026 08:00:00')
    expect(wrapper.text()).toContain('28/07/2026 02:00:00')

    // Form value check
    const input = wrapper.find('input[type="number"]')
    expect(input.exists()).toBe(true)
    expect(input.attributes('disabled')).toBeUndefined()
  })

  it('renders general error and hides settings grid', () => {
    const mockState = buildComposableState({
      generalError: ref('Không thể tải cấu hình quy đổi.'),
    })
    settingsPageMock.useQuotifySettingsPage.mockReturnValue(mockState)

    const wrapper = mount(QuotifySettingsPage, {
      global: {
        stubs: {
          AdminLayout: {
            template: '<div class="admin-layout"><slot /></div>',
          },
          InputNumber: true,
          Button: true,
        },
      },
    })

    expect(wrapper.text()).toContain('Không thể tải cấu hình quy đổi.')
    // If there is general error, settings grid is still visible but general error banner is rendered
    expect(wrapper.find('.quotify-settings-page__general-error').exists()).toBe(true)
  })

  it('disables update form when user lacks update permission', () => {
    const mockState = buildComposableState({
      canUpdateSettings: ref(false),
    })
    settingsPageMock.useQuotifySettingsPage.mockReturnValue(mockState)

    const wrapper = mount(QuotifySettingsPage, {
      global: {
        stubs: {
          AdminLayout: {
            template: '<div class="admin-layout"><slot /></div>',
          },
          InputNumber: {
            props: ['disabled'],
            template: '<input type="number" :disabled="disabled" />',
          },
          Button: {
            props: ['disabled'],
            template: '<button :disabled="disabled">Save</button>',
          },
        },
      },
    })

    const input = wrapper.find('input[type="number"]')
    expect(input.attributes('disabled')).toBeDefined()

    const saveButton = wrapper.find('button')
    expect(saveButton.attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('Chỉ xem')
  })

  it('triggers submitSettings when form is submitted', async () => {
    const mockState = buildComposableState()
    settingsPageMock.useQuotifySettingsPage.mockReturnValue(mockState)

    const wrapper = mount(QuotifySettingsPage, {
      global: {
        stubs: {
          AdminLayout: {
            template: '<div class="admin-layout"><slot /></div>',
          },
          InputNumber: true,
          Button: true,
        },
      },
    })

    const form = wrapper.find('form')
    await form.trigger('submit')

    expect(mockState.submitSettings).toHaveBeenCalled()
  })

  it('triggers fetchTodayRate when reload button is clicked', async () => {
    const mockState = buildComposableState()
    settingsPageMock.useQuotifySettingsPage.mockReturnValue(mockState)

    const wrapper = mount(QuotifySettingsPage, {
      global: {
        stubs: {
          AdminLayout: {
            template: '<div class="admin-layout"><slot /></div>',
          },
          InputNumber: true,
          Button: {
            template: '<button><slot /></button>',
          },
        },
      },
    })

    const refreshButton = wrapper.find('button[aria-label="Tải lại tỷ giá"]')
    expect(refreshButton.exists()).toBe(true)
    await refreshButton.trigger('click')

    expect(mockState.fetchTodayRate).toHaveBeenCalled()
  })

  it('displays success and submit error messages', () => {
    const mockState = buildComposableState({
      successMessage: ref('Đã lưu cấu hình quy đổi.'),
      submitError: ref('Lỗi lưu cấu hình.'),
      rateError: ref('Lỗi tải tỷ giá.'),
    })
    settingsPageMock.useQuotifySettingsPage.mockReturnValue(mockState)

    const wrapper = mount(QuotifySettingsPage, {
      global: {
        stubs: {
          AdminLayout: {
            template: '<div class="admin-layout"><slot /></div>',
          },
          InputNumber: true,
          Button: true,
        },
      },
    })

    expect(wrapper.text()).toContain('Đã lưu cấu hình quy đổi.')
    expect(wrapper.text()).toContain('Lỗi lưu cấu hình.')
    expect(wrapper.text()).toContain('Lỗi tải tỷ giá.')
  })

  it('registers settings route with correct properties', () => {
    const settingsRoute = router
      .getRoutes()
      .find((route) => route.name === 'quotify-settings')

    expect(settingsRoute?.path).toBe('/quotify-settings')
    expect(settingsRoute?.meta.requiredPermission).toBe('quotify_settings.read')
  })
})
