import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/http'
import { useAlertPreferences } from '@/composables/useAlertPreferences'
import { useAuthStore } from '@/stores/auth.store'
import type { AlertPreferencesDomain } from '@/types/alert-preferences'

const apiMock = vi.hoisted(() => ({
  getAlertPreferences: vi.fn(),
  updateAlertPreferences: vi.fn(),
}))

vi.mock('@/api/alert-preferences.api', () => apiMock)

function preferences(
  overrides: Partial<AlertPreferencesDomain> = {},
): AlertPreferencesDomain {
  return {
    isEnabled: true,
    minLevelChoice: 'default',
    effectiveMinLevel: 'medium',
    adminReceiveAll: false,
    ...overrides,
  }
}

function login(roles: string[]) {
  const auth = useAuthStore()
  auth.accessToken = 'token-1'
  auth.currentUser = {
    id: 'user-1',
    email: 'user@example.com',
    status: 'active',
    roles,
    permissions: [],
    lastLoginAt: null,
    fullName: 'Người dùng',
    avatarUrl: null,
  }
}

describe('useAlertPreferences', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    login(['manager'])
    vi.clearAllMocks()
    apiMock.getAlertPreferences.mockResolvedValue(preferences())
  })

  it('loads the preferences and describes the role default', async () => {
    const page = useAlertPreferences()

    await page.load()

    expect(apiMock.getAlertPreferences).toHaveBeenCalledWith('token-1')
    expect(page.isEnabled.value).toBe(true)
    expect(page.minLevelChoice.value).toBe('default')
    expect(page.defaultOptionLabel.value).toBe(
      'Mặc định theo vai trò (hiện là Trung bình)',
    )
    expect(page.isLoaded.value).toBe(true)
    expect(page.isAdmin.value).toBe(false)
  })

  it('saves the chosen level and shows a success message', async () => {
    apiMock.updateAlertPreferences.mockResolvedValue(
      preferences({ minLevelChoice: 'light', effectiveMinLevel: 'light' }),
    )
    const page = useAlertPreferences()
    await page.load()

    page.minLevelChoice.value = 'light'
    await page.save()

    expect(apiMock.updateAlertPreferences).toHaveBeenCalledWith(
      { is_enabled: true, min_level: 'light', admin_receive_all: false },
      'token-1',
    )
    expect(page.successMessage.value).toBe('Đã lưu tùy chọn thông báo.')
    expect(page.errorMessage.value).toBeNull()
    expect(page.defaultOptionLabel.value).toBe(
      'Mặc định theo vai trò (hiện là Nhẹ)',
    )
  })

  it('turns notifications off', async () => {
    apiMock.updateAlertPreferences.mockResolvedValue(
      preferences({ isEnabled: false }),
    )
    const page = useAlertPreferences()
    await page.load()

    page.isEnabled.value = false
    await page.save()

    expect(apiMock.updateAlertPreferences.mock.calls[0][0].is_enabled).toBe(
      false,
    )
  })

  it('never asks for "receive all" from someone who is not an admin', async () => {
    apiMock.updateAlertPreferences.mockResolvedValue(preferences())
    const page = useAlertPreferences()
    await page.load()

    page.adminReceiveAll.value = true
    await page.save()

    expect(
      apiMock.updateAlertPreferences.mock.calls[0][0].admin_receive_all,
    ).toBe(false)
  })

  it('lets an admin turn on "receive all"', async () => {
    login(['admin'])
    apiMock.updateAlertPreferences.mockResolvedValue(
      preferences({ adminReceiveAll: true }),
    )
    const page = useAlertPreferences()
    await page.load()

    page.adminReceiveAll.value = true
    await page.save()

    expect(page.isAdmin.value).toBe(true)
    expect(
      apiMock.updateAlertPreferences.mock.calls[0][0].admin_receive_all,
    ).toBe(true)
  })

  it.each([
    [403, 'Chỉ quản trị viên được bật nhận mọi thông báo.'],
    [500, 'Không thể lưu tùy chọn. Vui lòng thử lại.'],
  ])(
    'shows a fixed message for status %s and never the server detail',
    async (status, text) => {
      apiMock.updateAlertPreferences.mockRejectedValue(
        new ApiError('secret detail', status, { detail: 'secret detail' }),
      )
      const page = useAlertPreferences()
      await page.load()

      await page.save()

      expect(page.errorMessage.value).toBe(text)
      expect(page.successMessage.value).toBeNull()
    },
  )

  it('keeps a load failure as a fixed message and can retry', async () => {
    apiMock.getAlertPreferences.mockRejectedValueOnce(new Error('boom'))
    const page = useAlertPreferences()

    await page.load()
    expect(page.loadError.value).toBe('Không thể tải tùy chọn thông báo.')
    expect(page.isLoaded.value).toBe(false)

    await page.load()
    expect(page.loadError.value).toBeNull()
    expect(page.isLoaded.value).toBe(true)
  })

  it('ignores a second save while one is running', async () => {
    let finish: (value: unknown) => void = () => undefined
    apiMock.updateAlertPreferences.mockReturnValue(
      new Promise((resolve) => (finish = resolve)),
    )
    const page = useAlertPreferences()
    await page.load()

    const first = page.save()
    await page.save()
    finish(preferences())
    await first

    expect(apiMock.updateAlertPreferences).toHaveBeenCalledTimes(1)
  })
})
