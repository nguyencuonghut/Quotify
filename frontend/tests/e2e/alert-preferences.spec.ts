import { expect, test, type Page } from '@playwright/test'

const LOGGED_IN_COOKIE = 'quotify_logged_in'

interface MockPreferences {
  is_enabled: boolean
  min_level: 'light' | 'medium' | 'large' | null
  effective_min_level: 'light' | 'medium' | 'large'
  admin_receive_all: boolean
}

async function mockAuth(page: Page, roles: string[]) {
  const session = {
    access_token: 'e2e-token',
    token_type: 'bearer',
    expires_in: 3600,
  }
  await page.route('**/api/v1/auth/refresh', (route) =>
    route.fulfill({ status: 200, json: session }),
  )
  await page.route('**/api/v1/auth/me', (route) =>
    route.fulfill({
      status: 200,
      json: {
        id: 'user-e2e',
        email: 'user@example.com',
        status: 'active',
        roles,
        permissions: [],
        last_login_at: null,
        full_name: 'Người dùng',
        avatar_url: null,
      },
    }),
  )
  await page
    .context()
    .addCookies([
      { name: LOGGED_IN_COOKIE, value: '1', url: 'http://127.0.0.1:4173' },
    ])
}

async function mockTelegramAndPreferences(
  page: Page,
  options: { telegramEnabled?: boolean } = {},
) {
  const state: MockPreferences = {
    is_enabled: true,
    min_level: null,
    effective_min_level: 'medium',
    admin_receive_all: false,
  }
  const puts: unknown[] = []

  await page.route('**/api/v1/users/me/telegram', (route) =>
    route.fulfill({
      status: 200,
      json: {
        enabled: options.telegramEnabled ?? true,
        bot_username: 'quotify_bot',
        account: null,
        pending_link: null,
      },
    }),
  )
  await page.route('**/api/v1/users/me/alert-preferences', async (route) => {
    if (route.request().method() === 'PUT') {
      const body = route.request().postDataJSON()
      puts.push(body)
      state.is_enabled = body.is_enabled
      state.min_level = body.min_level
      state.admin_receive_all = body.admin_receive_all
      state.effective_min_level = body.min_level ?? 'medium'
    }
    return route.fulfill({ status: 200, json: state })
  })
  return puts
}

test('saves the minimum level and the on/off switch', async ({ page }) => {
  await mockAuth(page, ['manager'])
  const puts = await mockTelegramAndPreferences(page)
  await page.goto('/profile')

  const panel = page.getByTestId('alert-preferences-panel')
  await expect(panel).toBeVisible()
  await expect(
    panel.getByText('Mặc định theo vai trò (hiện là Trung bình)'),
  ).toBeVisible()
  await expect(page.getByTestId('alert-preferences-admin-all')).toHaveCount(0)

  await page.getByTestId('alert-preferences-level').click()
  await page.getByRole('option', { name: /Từ mức Nhẹ/ }).click()
  await page.getByTestId('alert-preferences-save').click()

  await expect(page.getByTestId('alert-preferences-success')).toHaveText(
    'Đã lưu tùy chọn thông báo.',
  )
  expect(puts).toEqual([
    { is_enabled: true, min_level: 'light', admin_receive_all: false },
  ])
})

test('lets an admin choose to receive every alert', async ({ page }) => {
  await mockAuth(page, ['admin'])
  const puts = await mockTelegramAndPreferences(page)
  await page.goto('/profile')

  await expect(page.getByText('không bao giờ nhận thông báo')).toBeVisible()
  await page.locator('#alert-preferences-admin-all').check()
  await page.getByTestId('alert-preferences-save').click()

  await expect(page.getByTestId('alert-preferences-success')).toBeVisible()
  expect(puts[0]).toMatchObject({ admin_receive_all: true })
})

test('hides the options when Telegram is switched off', async ({ page }) => {
  await mockAuth(page, ['manager'])
  await mockTelegramAndPreferences(page, { telegramEnabled: false })
  await page.goto('/profile')

  await expect(page.getByText('Đổi mật khẩu').first()).toBeVisible()
  await expect(page.getByTestId('alert-preferences-panel')).toHaveCount(0)
})

test('stays inside the phone screen', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await mockAuth(page, ['admin'])
  await mockTelegramAndPreferences(page)
  await page.goto('/profile')

  await expect(page.getByTestId('alert-preferences-save')).toBeVisible()
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  )
  expect(overflow).toBeLessThanOrEqual(1)
})
