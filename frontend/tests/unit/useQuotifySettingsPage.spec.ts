import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useQuotifySettingsPage } from '@/composables/useQuotifySettingsPage'
import { useAuthStore } from '@/stores/auth.store'
import { usePermissionStore } from '@/stores/permission.store'

const settingsApiMock = vi.hoisted(() => ({
  getQuotifySettings: vi.fn(),
  updateConversionCost: vi.fn(),
}))

const ratesApiMock = vi.hoisted(() => ({
  getUsdSellRateToday: vi.fn(),
}))

vi.mock('@/api/quotify-settings.api', () => settingsApiMock)
vi.mock('@/api/exchange-rates.api', () => ratesApiMock)

describe('useQuotifySettingsPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()

    const authStore = useAuthStore()
    authStore.accessToken = 'mock-access-token'

    const permissionStore = usePermissionStore()
    // Default cho phép update settings trong test
    permissionStore.permissions = ['quotify_settings.read', 'quotify_settings.update']
  })

  it('initializes state correctly', () => {
    const page = useQuotifySettingsPage()
    expect(page.settings.value).toBeNull()
    expect(page.todayRate.value).toBeNull()
    expect(page.loadingSettings.value).toBe(false)
    expect(page.loadingRate.value).toBe(false)
    expect(page.generalError.value).toBeNull()
    expect(page.rateError.value).toBeNull()
    expect(page.submitError.value).toBeNull()
    expect(page.successMessage.value).toBeNull()
    expect(page.canUpdateSettings.value).toBe(true)
  })

  it('fetches settings successfully and populates form', async () => {
    const mockSettings = {
      id: 'settings-1',
      conversionCostVndPerKg: '250.50',
      updatedById: 'user-1',
      createdAt: '2026-07-28T01:00:00+00:00',
      updatedAt: '2026-07-28T02:00:00+00:00',
    }
    settingsApiMock.getQuotifySettings.mockResolvedValue(mockSettings)

    const page = useQuotifySettingsPage()
    await page.bootstrap() // bootstrap calls fetchSettings and fetchTodayRate

    expect(settingsApiMock.getQuotifySettings).toHaveBeenCalledWith('mock-access-token')
    expect(page.settings.value).toEqual(mockSettings)
    expect(page.conversionCostVndPerKg.value).toBe(250.5)
    expect(page.formattedConversionCost.value).toBe('250,50 VNĐ/KG')
    expect(page.formattedSettingsUpdatedAt.value).toContain('28/07/2026')
  })

  it('handles fetch settings error gracefully', async () => {
    settingsApiMock.getQuotifySettings.mockRejectedValue(new Error('API Error'))

    const page = useQuotifySettingsPage()
    await page.bootstrap()

    expect(page.settings.value).toBeNull()
    expect(page.generalError.value).toBe('Không thể tải cấu hình quy đổi.')
    expect(page.formattedConversionCost.value).toBe('Chưa có dữ liệu')
  })

  it('fetches today exchange rate successfully', async () => {
    const mockRate = {
      currency: 'USD',
      rate: '26120.00',
      source: 'Vietcombank USD bán ra',
      retrievedAt: '2026-07-28T08:00:00+07:00',
    }
    ratesApiMock.getUsdSellRateToday.mockResolvedValue(mockRate)

    const page = useQuotifySettingsPage()
    await page.bootstrap()

    expect(ratesApiMock.getUsdSellRateToday).toHaveBeenCalledWith('mock-access-token')
    expect(page.todayRate.value).toEqual(mockRate)
    expect(page.formattedRate.value).toBe('26.120,00 VNĐ/USD')
    expect(page.formattedRateRetrievedAt.value).toContain('28/07/2026')
  })

  it('handles fetch rate error gracefully', async () => {
    ratesApiMock.getUsdSellRateToday.mockRejectedValue(new Error('Rate Error'))

    const page = useQuotifySettingsPage()
    await page.bootstrap()

    expect(page.todayRate.value).toBeNull()
    expect(page.rateError.value).toBe('Không thể tải tỷ giá USD bán ra hôm nay.')
    expect(page.formattedRate.value).toBe('Chưa có dữ liệu')
  })

  it('updates settings successfully', async () => {
    const mockSettings = {
      id: 'settings-1',
      conversionCostVndPerKg: '200.00',
      updatedById: 'user-1',
      createdAt: '2026-07-28T01:00:00+00:00',
      updatedAt: '2026-07-28T02:00:00+00:00',
    }
    settingsApiMock.getQuotifySettings.mockResolvedValue(mockSettings)

    const updatedSettings = {
      ...mockSettings,
      conversionCostVndPerKg: '300.00',
      updatedAt: '2026-07-28T03:00:00+00:00',
    }
    settingsApiMock.updateConversionCost.mockResolvedValue(updatedSettings)

    const page = useQuotifySettingsPage()
    await page.bootstrap() // Load initial value

    // Simulate inputting a new value in form
    page.conversionCostVndPerKg.value = 300

    await page.submitSettings()

    expect(settingsApiMock.updateConversionCost).toHaveBeenCalledWith(
      { conversion_cost_vnd_per_kg: '300' },
      'mock-access-token',
    )
    expect(page.settings.value).toEqual(updatedSettings)
    expect(page.successMessage.value).toBe('Đã lưu cấu hình quy đổi.')
    expect(page.submitError.value).toBeNull()
  })

  it('refuses to update settings without permission', async () => {
    const permissionStore = usePermissionStore()
    permissionStore.permissions = ['quotify_settings.read'] // Đọc nhưng không ghi

    const page = useQuotifySettingsPage()
    await page.bootstrap()

    expect(page.canUpdateSettings.value).toBe(false)

    await page.submitSettings()

    expect(settingsApiMock.updateConversionCost).not.toHaveBeenCalled()
    expect(page.submitError.value).toBe('Bạn không có quyền cập nhật cấu hình quy đổi.')
  })

  it('handles update settings server error', async () => {
    settingsApiMock.getQuotifySettings.mockResolvedValue({
      id: 'settings-1',
      conversionCostVndPerKg: '200.00',
      updatedById: 'user-1',
      createdAt: '2026-07-28T01:00:00+00:00',
      updatedAt: '2026-07-28T02:00:00+00:00',
    })
    settingsApiMock.updateConversionCost.mockRejectedValue(new Error('Server error'))

    const page = useQuotifySettingsPage()
    await page.bootstrap()

    page.conversionCostVndPerKg.value = 400
    await page.submitSettings()

    expect(page.submitError.value).toBe('Lỗi hệ thống khi lưu cấu hình quy đổi.')
    expect(page.successMessage.value).toBeNull()
  })
})
