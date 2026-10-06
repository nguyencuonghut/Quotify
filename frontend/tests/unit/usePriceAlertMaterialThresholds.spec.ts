import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { effectScope } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/http'
import { usePriceAlertMaterialThresholds } from '@/composables/usePriceAlertMaterialThresholds'
import { useAuthStore } from '@/stores/auth.store'
import type { MaterialThresholdDomain } from '@/types/price-alert-settings'

const apiMock = vi.hoisted(() => ({
  listMaterialThresholds: vi.fn(),
  putMaterialThreshold: vi.fn(),
  deleteMaterialThreshold: vi.fn(),
}))

vi.mock('@/api/price-alert-settings.api', () => apiMock)

function material(
  overrides: Partial<MaterialThresholdDomain> = {},
): MaterialThresholdDomain {
  return {
    materialId: 'm1',
    code: 'LM3',
    name: 'Lúa mỳ 3',
    hasOverride: false,
    override: null,
    effective: { light: 2.5, medium: 5, large: 10, anomaly: 30 },
    lightLabel: '2,50%',
    mediumLabel: '5,00%',
    largeLabel: '10,00%',
    anomalyLabel: '30,00%',
    anomalyIsDefault: true,
    ...overrides,
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

describe('usePriceAlertMaterialThresholds', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    login(['price_alerts.manage'])
    vi.clearAllMocks()
    apiMock.listMaterialThresholds.mockResolvedValue({
      items: [material()],
      total: 1,
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('loads the first page with the token', async () => {
    const page = usePriceAlertMaterialThresholds()

    await page.fetchMaterials()

    expect(apiMock.listMaterialThresholds).toHaveBeenCalledWith(
      { limit: 10, offset: 0 },
      'token-1',
    )
    expect(page.materials.value).toHaveLength(1)
    expect(page.total.value).toBe(1)
  })

  it('searches after a short pause and goes back to the first row', async () => {
    // vee-validate cần timer thật, nên chỉ test debounce mới dùng đồng hồ giả.
    vi.useFakeTimers()
    const page = usePriceAlertMaterialThresholds()
    await page.onPageChange({ first: 20, rows: 10 })

    page.search.value = 'lúa'
    page.onSearchInput()
    page.search.value = 'lúa mỳ'
    page.onSearchInput()
    expect(apiMock.listMaterialThresholds).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(400)

    expect(apiMock.listMaterialThresholds).toHaveBeenCalledTimes(2)
    expect(apiMock.listMaterialThresholds).toHaveBeenLastCalledWith(
      { limit: 10, offset: 0, search: 'lúa mỳ' },
      'token-1',
    )
    expect(page.first.value).toBe(0)
  })

  it('refuses an anomaly threshold above what the server accepts (999,99)', async () => {
    const page = usePriceAlertMaterialThresholds()
    page.openEdit(material())

    page.fields.anomalyPercent.value = 1000
    await page.saveOverride()
    await flushPromises()

    expect(apiMock.putMaterialThreshold).not.toHaveBeenCalled()
    expect(page.errors.value.anomalyPercent).toBe(
      'Ngưỡng giá bất thường không được vượt quá 999,99%.',
    )
  })

  it('drops a pending search when the page is left', async () => {
    vi.useFakeTimers()
    const scope = effectScope()
    const page = scope.run(() => usePriceAlertMaterialThresholds())!

    page.onSearchInput()
    scope.stop()
    await vi.advanceTimersByTimeAsync(400)

    expect(apiMock.listMaterialThresholds).not.toHaveBeenCalled()
  })

  it('opens the dialog with the effective thresholds and saves an override', async () => {
    apiMock.putMaterialThreshold.mockResolvedValue(
      material({ hasOverride: true }),
    )
    const page = usePriceAlertMaterialThresholds()
    await page.fetchMaterials()

    page.openEdit(material())
    expect(page.dialogVisible.value).toBe(true)
    expect(page.fields.lightFromPercent.value).toBe(2.5)
    expect(page.fields.anomalyPercent.value).toBeNull()

    page.fields.lightFromPercent.value = 1
    page.fields.mediumFromPercent.value = 3
    page.fields.largeOverPercent.value = 6
    page.fields.anomalyPercent.value = 45
    await page.saveOverride()
    await flushPromises()

    expect(apiMock.putMaterialThreshold).toHaveBeenCalledWith(
      expect.objectContaining({ materialId: 'm1' }),
      {
        light_from_percent: 1,
        medium_from_percent: 3,
        large_over_percent: 6,
        anomaly_percent: 45,
      },
      'token-1',
    )
    expect(page.dialogVisible.value).toBe(false)
    expect(page.successMessage.value).toBe('Đã lưu ngưỡng riêng cho Lúa mỳ 3.')
    expect(apiMock.listMaterialThresholds).toHaveBeenCalledTimes(2)
  })

  it('sends null for the anomaly threshold when it is left empty (use the default)', async () => {
    apiMock.putMaterialThreshold.mockResolvedValue(material())
    const page = usePriceAlertMaterialThresholds()
    page.openEdit(material())
    page.fields.lightFromPercent.value = 1
    page.fields.mediumFromPercent.value = 3
    page.fields.largeOverPercent.value = 6

    await page.saveOverride()
    await flushPromises()

    expect(
      apiMock.putMaterialThreshold.mock.calls[0][1].anomaly_percent,
    ).toBeNull()
  })

  it('refuses thresholds that do not rise or an anomaly threshold not above Large', async () => {
    const page = usePriceAlertMaterialThresholds()
    page.openEdit(material())

    page.fields.mediumFromPercent.value = 2
    await page.saveOverride()
    await flushPromises()
    expect(page.errors.value.mediumFromPercent).toBe(
      'Ngưỡng phải tăng dần: Nhẹ < Trung bình < Lớn.',
    )

    page.fields.mediumFromPercent.value = 5
    page.fields.anomalyPercent.value = 8
    await page.saveOverride()
    await flushPromises()
    expect(page.errors.value.anomalyPercent).toBe(
      'Ngưỡng giá bất thường phải lớn hơn ngưỡng Lớn.',
    )
    expect(apiMock.putMaterialThreshold).not.toHaveBeenCalled()
  })

  it('goes back to the defaults with a delete and refreshes the list', async () => {
    apiMock.deleteMaterialThreshold.mockResolvedValue(undefined)
    const custom = material({
      hasOverride: true,
      override: { light: 1, medium: 3, large: 6, anomaly: null },
    })
    const page = usePriceAlertMaterialThresholds()
    page.openEdit(custom)

    await page.resetToDefault()
    await flushPromises()

    expect(apiMock.deleteMaterialThreshold).toHaveBeenCalledWith(
      'm1',
      'token-1',
    )
    expect(page.dialogVisible.value).toBe(false)
    expect(page.successMessage.value).toBe(
      'Đã đưa Lúa mỳ 3 về ngưỡng mặc định.',
    )
    expect(apiMock.listMaterialThresholds).toHaveBeenCalledTimes(1)
  })

  it.each([
    [404, 'Không tìm thấy vật tư này.'],
    [422, 'Ngưỡng không hợp lệ. Kiểm tra thứ tự và phạm vi giá trị.'],
    [403, 'Bạn không có quyền sửa ngưỡng thông báo giá.'],
    [500, 'Không thể lưu ngưỡng. Vui lòng thử lại.'],
  ])(
    'shows a fixed message for status %s and keeps the dialog open',
    async (status, text) => {
      apiMock.putMaterialThreshold.mockRejectedValue(
        new ApiError('secret detail', status, { detail: 'secret detail' }),
      )
      const page = usePriceAlertMaterialThresholds()
      page.openEdit(material())
      page.fields.lightFromPercent.value = 1
      page.fields.mediumFromPercent.value = 3
      page.fields.largeOverPercent.value = 6

      await page.saveOverride()
      await flushPromises()

      expect(page.errorMessage.value).toBe(text)
      expect(page.dialogVisible.value).toBe(true)
    },
  )

  it('ignores an older list response and keeps a load failure as a fixed message', async () => {
    let resolveFirst: (value: unknown) => void = () => undefined
    apiMock.listMaterialThresholds
      .mockReturnValueOnce(new Promise((resolve) => (resolveFirst = resolve)))
      .mockResolvedValueOnce({
        items: [material({ materialId: 'new' })],
        total: 1,
      })
    const page = usePriceAlertMaterialThresholds()

    const slow = page.fetchMaterials()
    await page.onPageChange({ first: 0, rows: 20 })
    resolveFirst({ items: [material({ materialId: 'old' })], total: 5 })
    await slow
    expect(page.materials.value.map((m) => m.materialId)).toEqual(['new'])

    apiMock.listMaterialThresholds.mockRejectedValue(new Error('boom'))
    await page.fetchMaterials()
    expect(page.generalError.value).toBe(
      'Không thể tải danh sách ngưỡng theo vật tư.',
    )
    expect(page.materials.value).toEqual([])
  })
})
