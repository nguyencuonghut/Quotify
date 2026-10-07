import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AdminLayout from '@/layouts/AdminLayout.vue'
import PriceAlertSettingsPage from '@/pages/PriceAlertSettingsPage.vue'
import { router } from '@/router'
import { useAuthStore } from '@/stores/auth.store'

const settingsMock = vi.hoisted(() => ({ usePriceAlertSettingsPage: vi.fn() }))
const materialsMock = vi.hoisted(() => ({
  usePriceAlertMaterialThresholds: vi.fn(),
}))

vi.mock('@/composables/usePriceAlertSettingsPage', () => settingsMock)
vi.mock('@/composables/usePriceAlertMaterialThresholds', () => materialsMock)

function settingsState(overrides: Record<string, unknown> = {}) {
  const names = [
    'isEnabled',
    'anomalyEnabled',
    'referenceWorkingDays',
    'lightFromPercent',
    'mediumFromPercent',
    'largeOverPercent',
    'anomalyPercent',
    'anomalyLookbackDays',
    'maxTriggerDelayWorkingDays',
    'staffLookbackDays',
    'dedupeWindowDays',
    'immediateCapPerScan',
    'digestHourLocal',
    'referenceFallbackDays',
    'freshnessEnabled',
    'freshnessHourLocal',
  ]
  return {
    fields: Object.fromEntries(
      names.map((name) => [
        name,
        ref(['isEnabled', 'anomalyEnabled', 'freshnessEnabled'].includes(name) ? false : 5),
      ]),
    ),
    errors: ref({}),
    meta: ref({
      enabledSinceLabel: '10:31 06/10/2026',
      updatedAtLabel: '11:00 06/10/2026',
    }),
    loading: ref(false),
    generalError: ref(null),
    submitError: ref(null),
    successMessage: ref(null),
    isSaving: ref(false),
    canEdit: ref(true),
    fetchSettings: vi.fn(),
    submitSettings: vi.fn(),
    ...overrides,
  }
}

function materialsState(overrides: Record<string, unknown> = {}) {
  return {
    materials: ref([]),
    total: ref(0),
    loading: ref(false),
    generalError: ref(null),
    rows: ref(10),
    first: ref(0),
    rowsPerPageOptions: [10, 20, 30, 50],
    search: ref(''),
    dialogVisible: ref(false),
    target: ref(null),
    isBusy: ref(false),
    errorMessage: ref(null),
    successMessage: ref(null),
    fields: {
      lightFromPercent: ref(2.5),
      mediumFromPercent: ref(5),
      largeOverPercent: ref(10),
      anomalyPercent: ref(null),
    },
    errors: ref({}),
    fetchMaterials: vi.fn(),
    onPageChange: vi.fn(),
    onSearchInput: vi.fn(),
    sortField: ref(null),
    sortOrder: ref(1),
    onSort: vi.fn(),
    openEdit: vi.fn(),
    closeDialog: vi.fn(),
    saveOverride: vi.fn(),
    resetToDefault: vi.fn(),
    watchDialogVisible: ref(false),
    watchTarget: ref(null),
    watchEnabled: ref(true),
    watchInterval: ref(14),
    watchBusy: ref(false),
    watchError: ref(null),
    openWatchEdit: vi.fn(),
    closeWatchDialog: vi.fn(),
    saveWatch: vi.fn(),
    clearWatch: vi.fn(),
    ...overrides,
  }
}

function mountPage() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mount(PriceAlertSettingsPage, {
    global: {
      plugins: [pinia],
      stubs: {
        AdminLayout: { template: '<section><slot /></section>' },
        InputNumber: true,
        DataTable: { template: '<div><slot name="empty" /></div>' },
        Dialog: { template: '<aside><slot /><slot name="footer" /></aside>' },
      },
    },
  })
}

describe('PriceAlertSettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    settingsMock.usePriceAlertSettingsPage.mockReturnValue(settingsState())
    materialsMock.usePriceAlertMaterialThresholds.mockReturnValue(
      materialsState(),
    )
  })

  it('loads both parts on mount and explains what turning the feature on does', () => {
    const settings = settingsState()
    const materials = materialsState()
    settingsMock.usePriceAlertSettingsPage.mockReturnValue(settings)
    materialsMock.usePriceAlertMaterialThresholds.mockReturnValue(materials)

    const wrapper = mountPage()

    expect(settings.fetchSettings).toHaveBeenCalledTimes(1)
    expect(materials.fetchMaterials).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain(
      'Mỗi lần bật lại, hệ thống bắt đầu quét từ thời điểm bật',
    )
    expect(wrapper.text()).toContain('Bật gần nhất lúc 10:31 06/10/2026')
    expect(wrapper.text()).toContain('Cập nhật lần cuối 11:00 06/10/2026')
  })

  it('toggles the two flags through the form fields', async () => {
    const settings = settingsState()
    settingsMock.usePriceAlertSettingsPage.mockReturnValue(settings)

    const wrapper = mountPage()
    await wrapper.get('[data-testid="toggle-enabled"]').setValue(true)
    await wrapper.get('[data-testid="toggle-anomaly"]').setValue(true)

    expect(settings.fields.isEnabled.value).toBe(true)
    expect(settings.fields.anomalyEnabled.value).toBe(true)
  })

  it('submits the form from the save button', async () => {
    const settings = settingsState()
    settingsMock.usePriceAlertSettingsPage.mockReturnValue(settings)

    const wrapper = mountPage()
    await wrapper.get('[data-testid="settings-form"]').trigger('submit')

    expect(settings.submitSettings).toHaveBeenCalledTimes(1)
  })

  it('locks saving without the permission or while saving, and explains why', () => {
    settingsMock.usePriceAlertSettingsPage.mockReturnValue(
      settingsState({ canEdit: ref(false) }),
    )
    const readOnly = mountPage().get('[data-testid="settings-save"]')
    expect(readOnly.attributes('disabled')).toBeDefined()
    expect(readOnly.attributes('title')).toContain('không có quyền')

    settingsMock.usePriceAlertSettingsPage.mockReturnValue(
      settingsState({ isSaving: ref(true) }),
    )
    expect(
      mountPage().get('[data-testid="settings-save"]').attributes('disabled'),
    ).toBeDefined()
  })

  it('shows save results inline and the field errors', () => {
    settingsMock.usePriceAlertSettingsPage.mockReturnValue(
      settingsState({
        successMessage: ref('Đã lưu cấu hình thông báo giá.'),
        submitError: ref('Không thể lưu cấu hình. Vui lòng thử lại.'),
        errors: ref({
          mediumFromPercent:
            'Ngưỡng phải tăng dần: Nhẹ < Trung bình < Lớn < Bất thường.',
        }),
      }),
    )

    const wrapper = mountPage()

    expect(
      wrapper.get('[data-testid="settings-success"]').attributes('role'),
    ).toBe('status')
    expect(
      wrapper.get('[data-testid="settings-error"]').attributes('role'),
    ).toBe('alert')
    expect(wrapper.text()).toContain('Ngưỡng phải tăng dần')
  })

  it('hides the form when the settings cannot be loaded', () => {
    settingsMock.usePriceAlertSettingsPage.mockReturnValue(
      settingsState({
        generalError: ref('Không thể tải cấu hình thông báo giá.'),
      }),
    )

    const wrapper = mountPage()

    expect(wrapper.text()).toContain('Không thể tải cấu hình thông báo giá.')
    expect(wrapper.find('[data-testid="settings-form"]').exists()).toBe(false)
  })

  it('offers a retry when the settings could not be loaded', async () => {
    const settings = settingsState({
      generalError: ref('Không thể tải cấu hình thông báo giá.'),
    })
    settingsMock.usePriceAlertSettingsPage.mockReturnValue(settings)

    const wrapper = mountPage()
    await wrapper.get('[data-testid="settings-retry"]').trigger('click')

    expect(settings.fetchSettings).toHaveBeenCalledTimes(2)
  })

  it('searches materials through the composable and shows the empty state', async () => {
    const materials = materialsState()
    materialsMock.usePriceAlertMaterialThresholds.mockReturnValue(materials)

    const wrapper = mountPage()
    await wrapper.get('[data-testid="material-search"]').setValue('lúa')

    expect(materials.search.value).toBe('lúa')
    expect(materials.onSearchInput).toHaveBeenCalled()
    expect(wrapper.text()).toContain('Không có vật tư phù hợp.')
  })

  it('shows the material dialog actions: reset only when an override exists, save, errors', async () => {
    const materials = materialsState({
      dialogVisible: ref(true),
      target: ref({ name: 'Lúa mỳ 3', hasOverride: true }),
      errorMessage: ref('Không thể lưu ngưỡng. Vui lòng thử lại.'),
    })
    materialsMock.usePriceAlertMaterialThresholds.mockReturnValue(materials)

    const wrapper = mountPage()
    await wrapper.get('[data-testid="material-reset"]').trigger('click')
    await wrapper.get('[data-testid="material-save"]').trigger('click')

    expect(materials.resetToDefault).toHaveBeenCalledTimes(1)
    expect(materials.saveOverride).toHaveBeenCalledTimes(1)
    expect(wrapper.get('[data-testid="material-error"]').text()).toContain(
      'Không thể lưu ngưỡng',
    )

    materialsMock.usePriceAlertMaterialThresholds.mockReturnValue(
      materialsState({
        dialogVisible: ref(true),
        target: ref({ name: 'Ngô hạt', hasOverride: false }),
      }),
    )
    expect(mountPage().find('[data-testid="material-reset"]').exists()).toBe(
      false,
    )
  })

  it('shows the watch dialog with its fields, save, and clear only when a config exists', async () => {
    const materials = materialsState({
      watchDialogVisible: ref(true),
      watchTarget: ref({
        name: 'Ngô hạt',
        freshness: { isWatched: true, expectedIntervalDays: 7 },
      }),
      watchError: ref('Chu kỳ phải là số nguyên từ 1 đến 365 ngày.'),
    })
    materialsMock.usePriceAlertMaterialThresholds.mockReturnValue(materials)

    const wrapper = mountPage()
    await wrapper.get('[data-testid="watch-save"]').trigger('click')
    await wrapper.get('[data-testid="watch-clear"]').trigger('click')
    await wrapper.get('[data-testid="watch-cancel"]').trigger('click')

    expect(materials.saveWatch).toHaveBeenCalledTimes(1)
    expect(materials.clearWatch).toHaveBeenCalledTimes(1)
    expect(materials.closeWatchDialog).toHaveBeenCalledTimes(1)
    expect(wrapper.get('[data-testid="watch-error"]').attributes('role')).toBe(
      'alert',
    )
    expect(wrapper.get('[data-testid="watch-error"]').text()).toContain(
      'từ 1 đến 365 ngày',
    )
    expect(wrapper.find('[input-id="watch-enabled"]').exists()).toBe(true)
    expect(wrapper.find('[input-id="watch-interval"]').exists()).toBe(true)

    materialsMock.usePriceAlertMaterialThresholds.mockReturnValue(
      materialsState({
        watchDialogVisible: ref(true),
        watchTarget: ref({ name: 'Ngô hạt', freshness: null }),
      }),
    )
    expect(mountPage().find('[data-testid="watch-clear"]').exists()).toBe(false)
  })

  it('disables the controls and the buttons while a watch save is running', () => {
    materialsMock.usePriceAlertMaterialThresholds.mockReturnValue(
      materialsState({
        watchDialogVisible: ref(true),
        watchTarget: ref({ name: 'Ngô hạt', freshness: null }),
        watchBusy: ref(true),
      }),
    )

    const wrapper = mountPage()

    expect(
      wrapper.get('[data-testid="watch-save"]').attributes('disabled'),
    ).toBeDefined()
    expect(
      wrapper.get('[data-testid="watch-cancel"]').attributes('disabled'),
    ).toBeDefined()
  })

  it('has a reminder card whose switch and hour are bound, with a note that the master switch gates it', async () => {
    const settings = settingsState()
    settingsMock.usePriceAlertSettingsPage.mockReturnValue(settings)

    const wrapper = mountPage()
    await wrapper.get('[data-testid="toggle-freshness"]').setValue(true)

    expect(wrapper.text()).toContain('Nhắc cập nhật giá')
    expect(settings.fields.freshnessEnabled.value).toBe(true)
    expect(wrapper.find('[input-id="price-alert-freshness-hour"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="freshness-master-note"]').text()).toContain(
      'công tắc tổng',
    )
    expect(wrapper.text()).toContain('tối đa 5 lần')
  })

  it('hides the master-switch warning once the master switch is on', () => {
    const settings = settingsState()
    settings.fields.isEnabled.value = true
    settingsMock.usePriceAlertSettingsPage.mockReturnValue(settings)

    expect(mountPage().find('[data-testid="freshness-master-note"]').exists()).toBe(false)
  })

  it('registers the route guarded by price_alerts.manage', () => {
    const route = router
      .getRoutes()
      .find((r) => r.name === 'price-alert-settings')

    expect(route?.path).toBe('/price-alert-settings')
    expect(route?.meta.requiredPermission).toBe('price_alerts.manage')
    expect(route?.meta.requiresAuth).toBe(true)
  })

  it.each([
    [['price_alerts.manage'], true],
    [['price_alerts.receive_all'], false],
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

      expect(wrapper.text().includes('Thông báo giá')).toBe(visible)
    },
  )
})
