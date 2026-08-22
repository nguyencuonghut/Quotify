import { createPinia, setActivePinia } from 'pinia'
import { describe, expect, it, vi, beforeEach } from 'vitest'

import { ApiError } from '@/api/http'
import { useLoginPage } from '@/composables/useLoginPage'
import { useAuthStore } from '@/stores/auth.store'

describe('useLoginPage error handling', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  async function submitWithLoginError(error: unknown) {
    const authStore = useAuthStore()
    vi.spyOn(authStore, 'login').mockRejectedValue(error)
    const onSuccess = vi.fn()

    const page = useLoginPage(onSuccess)
    page.email.value = 'user@quotify.local'
    page.password.value = 'password123'

    await page.submitLogin()
    return { page, onSuccess }
  }

  it('shows an invalid-credentials message on the password field for a 401', async () => {
    const { page, onSuccess } = await submitWithLoginError(
      new ApiError('Unauthorized', 401),
    )

    expect(page.errors.value.password).toBe('Thông tin đăng nhập không hợp lệ.')
    expect(page.generalError.value).toBeNull()
    expect(onSuccess).not.toHaveBeenCalled()
  })

  it('shows a connection error in the general banner (not the password field) for a network error', async () => {
    const { page, onSuccess } = await submitWithLoginError(new TypeError('fetch failed'))

    expect(page.generalError.value).toBe('Không thể kết nối tới dịch vụ xác thực.')
    expect(page.errors.value.password).toBeUndefined()
    expect(onSuccess).not.toHaveBeenCalled()
  })

  it('shows a generic error in the general banner for an unexpected server error, without throwing', async () => {
    const { page, onSuccess } = await submitWithLoginError(
      new ApiError('Internal Server Error', 500),
    )

    expect(page.generalError.value).toBe('Đã có lỗi xảy ra, vui lòng thử lại sau.')
    expect(page.errors.value.password).toBeUndefined()
    expect(onSuccess).not.toHaveBeenCalled()
  })
})
