import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/http'
import { usePriceAlertSettingsPage } from '@/composables/usePriceAlertSettingsPage'
import { useAuthStore } from '@/stores/auth.store'
import type { PriceAlertSettingsDomain } from '@/types/price-alert-settings'

const apiMock = vi.hoisted(() => ({
  getPriceAlertSettings: vi.fn(),
  updatePriceAlertSettings: vi.fn(),
}))

vi.mock('@/api/price-alert-settings.api', () => apiMock)

function settings(
  overrides: Partial<PriceAlertSettingsDomain['values']> = {},
): PriceAlertSettingsDomain {
  return {
    values: {
      isEnabled: false,
      anomalyEnabled: false,
      referenceWorkingDays: 7,
      lightFromPercent: 2.5,
      mediumFromPercent: 5,
      largeOverPercent: 10,
      anomalyPercent: 30,
      anomalyLookbackDays: 30,
      maxTriggerDelayWorkingDays: 3,
      staffLookbackDays: 90,
      dedupeWindowDays: 14,
      immediateCapPerScan: 30,
      digestHourLocal: 8,
      referenceFallbackDays: 30,
      freshnessEnabled: false,
      freshnessHourLocal: 9,
      ...overrides,
    },
    enabledSinceLabel: null,
    updatedAtLabel: '10:31 06/10/2026',
  }
}

function login(permissions: string[]) {
  const auth = useAuthStore()
  auth.accessToken = 'token-1'
  auth.currentUser = {
    id: 'user-1',
    email: 'manager@example.com',
    status: 'active',
    roles: ['manager'],
    permissions,
    lastLoginAt: null,
    fullName: 'Quản lý',
    avatarUrl: null,
  }
}

describe('usePriceAlertSettingsPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    login(['price_alerts.manage'])
    vi.clearAllMocks()
    apiMock.getPriceAlertSettings.mockResolvedValue(settings())
  })

  it('loads the settings into the form fields', async () => {
    const page = usePriceAlertSettingsPage()

    await page.fetchSettings()

    expect(apiMock.getPriceAlertSettings).toHaveBeenCalledWith('token-1')
    expect(page.fields.lightFromPercent.value).toBe(2.5)
    expect(page.fields.anomalyPercent.value).toBe(30)
    expect(page.fields.isEnabled.value).toBe(false)
    expect(page.meta.value?.updatedAtLabel).toBe('10:31 06/10/2026')
    expect(page.generalError.value).toBeNull()
    expect(page.canEdit.value).toBe(true)
  })

  it('sends the whole body when saving and shows the saved state', async () => {
    apiMock.updatePriceAlertSettings.mockResolvedValue({
      ...settings({ isEnabled: true, mediumFromPercent: 6 }),
      enabledSinceLabel: '10:31 06/10/2026',
    })
    const page = usePriceAlertSettingsPage()
    await page.fetchSettings()

    page.fields.isEnabled.value = true
    page.fields.mediumFromPercent.value = 6
    await page.submitSettings()
    await flushPromises()

    const [payload, token] = apiMock.updatePriceAlertSettings.mock.calls[0]
    expect(token).toBe('token-1')
    expect(payload).toMatchObject({
      is_enabled: true,
      medium_from_percent: 6,
      light_from_percent: 2.5,
      large_over_percent: 10,
      anomaly_percent: 30,
      digest_hour_local: 8,
      freshness_enabled: false,
      freshness_hour_local: 9,
    })
    expect(page.successMessage.value).toBe('Đã lưu cấu hình thông báo giá.')
    expect(page.meta.value?.enabledSinceLabel).toBe('10:31 06/10/2026')
    expect(page.submitError.value).toBeNull()
  })

  it('refuses thresholds that do not rise and never calls the server', async () => {
    const page = usePriceAlertSettingsPage()
    await page.fetchSettings()

    page.fields.mediumFromPercent.value = 2
    await page.submitSettings()
    await flushPromises()

    expect(apiMock.updatePriceAlertSettings).not.toHaveBeenCalled()
    expect(page.errors.value.mediumFromPercent).toBe(
      'Ngưỡng phải tăng dần: Nhẹ < Trung bình < Lớn < Bất thường.',
    )
  })

  it('refuses an anomaly threshold that is not above the Large threshold', async () => {
    const page = usePriceAlertSettingsPage()
    await page.fetchSettings()

    page.fields.anomalyPercent.value = 10
    await page.submitSettings()
    await flushPromises()

    expect(apiMock.updatePriceAlertSettings).not.toHaveBeenCalled()
    expect(page.errors.value.mediumFromPercent).toBe(
      'Ngưỡng phải tăng dần: Nhẹ < Trung bình < Lớn < Bất thường.',
    )
  })

  it('refuses an anomaly threshold above what the server accepts (999,99)', async () => {
    const page = usePriceAlertSettingsPage()
    await page.fetchSettings()

    page.fields.anomalyPercent.value = 1000
    await page.submitSettings()
    await flushPromises()

    expect(apiMock.updatePriceAlertSettings).not.toHaveBeenCalled()
    expect(page.errors.value.anomalyPercent).toBe(
      'Ngưỡng giá bất thường không được vượt quá 999,99%.',
    )
  })

  it('says a cleared number is required, not just invalid', async () => {
    const page = usePriceAlertSettingsPage()
    await page.fetchSettings()
    ;(page.fields.lightFromPercent as { value: unknown }).value = null
    await page.submitSettings()
    await flushPromises()

    expect(page.errors.value.lightFromPercent).toBe(
      'Ngưỡng Nhẹ là bắt buộc và phải là số hợp lệ.',
    )
  })

  it('also refuses values outside the allowed ranges', async () => {
    const page = usePriceAlertSettingsPage()
    await page.fetchSettings()

    page.fields.digestHourLocal.value = 24
    page.fields.immediateCapPerScan.value = 0
    await page.submitSettings()
    await flushPromises()

    expect(apiMock.updatePriceAlertSettings).not.toHaveBeenCalled()
    expect(page.errors.value.digestHourLocal).toBeTruthy()
    expect(page.errors.value.immediateCapPerScan).toBeTruthy()
  })

  it.each([
    [422, 'Cấu hình không hợp lệ. Kiểm tra thứ tự ngưỡng và phạm vi giá trị.'],
    [403, 'Bạn không có quyền sửa cấu hình thông báo giá.'],
    [500, 'Không thể lưu cấu hình. Vui lòng thử lại.'],
  ])(
    'shows a fixed message for status %s and never the server detail',
    async (status, text) => {
      apiMock.updatePriceAlertSettings.mockRejectedValue(
        new ApiError('secret detail', status, { detail: 'secret detail' }),
      )
      const page = usePriceAlertSettingsPage()
      await page.fetchSettings()

      page.fields.mediumFromPercent.value = 6
      await page.submitSettings()
      await flushPromises()

      expect(page.submitError.value).toBe(text)
      expect(page.successMessage.value).toBeNull()
    },
  )

  it('keeps a load failure as a fixed message and blocks editing without the permission', async () => {
    apiMock.getPriceAlertSettings.mockRejectedValue(new Error('boom'))
    const failing = usePriceAlertSettingsPage()
    await failing.fetchSettings()
    expect(failing.generalError.value).toBe(
      'Không thể tải cấu hình thông báo giá.',
    )

    login(['quotes.read'])
    const readOnly = usePriceAlertSettingsPage()
    expect(readOnly.canEdit.value).toBe(false)
    await readOnly.submitSettings()
    await flushPromises()
    expect(apiMock.updatePriceAlertSettings).not.toHaveBeenCalled()
    expect(readOnly.submitError.value).toBe(
      'Bạn không có quyền sửa cấu hình thông báo giá.',
    )
  })

  it('ignores a second save while one is running', async () => {
    let finish: (value: unknown) => void = () => undefined
    apiMock.updatePriceAlertSettings.mockReturnValue(
      new Promise((resolve) => (finish = resolve)),
    )
    const page = usePriceAlertSettingsPage()
    await page.fetchSettings()
    page.fields.mediumFromPercent.value = 6

    const first = page.submitSettings()
    await flushPromises()
    await page.submitSettings()
    finish(settings({ mediumFromPercent: 6 }))
    await first
    await flushPromises()

    expect(apiMock.updatePriceAlertSettings).toHaveBeenCalledTimes(1)
  })

  it('saves the freshness switch and hour with the rest of the form', async () => {
    const page = usePriceAlertSettingsPage()
    await page.fetchSettings()

    page.fields.freshnessEnabled.value = true
    page.fields.freshnessHourLocal.value = 10
    await page.submitSettings()
    await flushPromises()

    const [payload] = apiMock.updatePriceAlertSettings.mock.calls[0]
    expect(payload).toMatchObject({ freshness_enabled: true, freshness_hour_local: 10 })
  })

  it.each([24, -1, 9.5, null])(
    'refuses the freshness hour %s with a Vietnamese message and does not call the server',
    async (hour) => {
      const page = usePriceAlertSettingsPage()
      await page.fetchSettings()

      page.fields.freshnessHourLocal.value = hour as number
      await page.submitSettings()
      await flushPromises()

      expect(apiMock.updatePriceAlertSettings).not.toHaveBeenCalled()
      expect(page.errors.value.freshnessHourLocal).toMatch(/Giờ nhắc cập nhật giá/)
    },
  )
})
