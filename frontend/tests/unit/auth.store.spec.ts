import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { ApiError } from '@/api/http'
import { useAuthStore } from '@/stores/auth.store'

const authApiMock = vi.hoisted(() => ({
  getCurrentUser: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
  refreshSession: vi.fn(),
}))

vi.mock('@/api/auth.api', () => authApiMock)

describe('auth.store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    document.cookie = 'quotify_logged_in=; max-age=0'
  })

  it('bootstraps authenticated state from refresh cookie', async () => {
    document.cookie = 'quotify_logged_in=true'
    authApiMock.refreshSession.mockResolvedValue({
      accessToken: 'bootstrap-token',
      tokenType: 'bearer',
      expiresInSeconds: 900,
    })
    authApiMock.getCurrentUser.mockResolvedValue({
      id: 'user-1',
      email: 'admin@quotify.local',
      status: 'active',
      roles: ['admin'],
      permissions: ['dashboard.read', 'users.read'],
      lastLoginAt: '2026-06-10T00:00:00Z',
    })

    const authStore = useAuthStore()

    await authStore.initialize()

    expect(authStore.isAuthenticated).toBe(true)
    expect(authStore.currentUser?.email).toBe('admin@quotify.local')
    expect(authStore.permissions).toContain('dashboard.read')
  })

  it('falls back to anonymous state when refresh is unauthorized', async () => {
    document.cookie = 'quotify_logged_in=true'
    authApiMock.refreshSession.mockRejectedValue(
      new ApiError('Refresh token is invalid.', 401),
    )

    const authStore = useAuthStore()

    await authStore.initialize()

    expect(authStore.initialized).toBe(true)
    expect(authStore.isAuthenticated).toBe(false)
    expect(authStore.currentUser).toBeNull()
  })

  it('keeps the login marker cookie on a network-level refresh failure', async () => {
    // Simulates a fetch aborted by page navigation, e.g. rapid Ctrl+R/F5,
    // which browsers surface as a TypeError. This must not be treated the
    // same as an explicit 401/403 rejection, or one aborted request would
    // permanently sign the user out on every future reload.
    document.cookie = 'quotify_logged_in=true'
    authApiMock.refreshSession.mockRejectedValue(new TypeError('Failed to fetch'))

    const authStore = useAuthStore()

    await authStore.initialize()

    expect(authStore.initialized).toBe(true)
    expect(authStore.isAuthenticated).toBe(false)
    expect(
      document.cookie
        .split(';')
        .some((item) => item.trim().startsWith('quotify_logged_in=true')),
    ).toBe(true)
  })

  it('logs in and resolves current user after credential success', async () => {
    authApiMock.login.mockResolvedValue({
      accessToken: 'login-token',
      tokenType: 'bearer',
      expiresInSeconds: 900,
    })
    authApiMock.getCurrentUser.mockResolvedValue({
      id: 'user-2',
      email: 'ops@quotify.local',
      status: 'active',
      roles: ['user'],
      permissions: ['dashboard.read'],
      lastLoginAt: null,
    })

    const authStore = useAuthStore()

    await authStore.login({
      email: 'ops@quotify.local',
      password: 'Password@123',
    })

    expect(authStore.isAuthenticated).toBe(true)
    expect(authStore.currentUser?.roles).toEqual(['user'])
    expect(authApiMock.login).toHaveBeenCalledWith({
      email: 'ops@quotify.local',
      password: 'Password@123',
    })
  })
})
