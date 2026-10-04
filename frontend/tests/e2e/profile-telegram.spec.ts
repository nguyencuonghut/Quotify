import { expect, test, type Page } from '@playwright/test'

const adminEmail = process.env.E2E_ADMIN_EMAIL
const adminPassword = process.env.E2E_ADMIN_PASSWORD

const DEEP_LINK = 'https://t.me/quotify_bot?start=e2e_one_time_code'

interface MockAccount {
  status: 'active' | 'blocked'
  username: string | null
  first_name: string | null
  linked_at: string
}

interface MockState {
  enabled: boolean
  account: MockAccount | null
  pending: boolean
}

function requireE2ECredential(value: string | undefined, name: string): string {
  if (!value) {
    throw new Error(`${name} is required for Telegram profile E2E tests.`)
  }

  return value
}

async function login(page: Page) {
  await page.goto('/login')
  await page
    .getByPlaceholder('Nhập email đăng nhập')
    .fill(requireE2ECredential(adminEmail, 'E2E_ADMIN_EMAIL'))
  await page
    .getByPlaceholder('Nhập mật khẩu')
    .fill(requireE2ECredential(adminPassword, 'E2E_ADMIN_PASSWORD'))
  await page.getByRole('button', { name: 'Đăng nhập' }).click()
  // Trang Hồ sơ ai cũng vào được, nên chỉ cần biết đã đăng nhập (không phụ thuộc quyền xem dashboard).
  await page.waitForURL((url) => !url.pathname.startsWith('/login'))
}

/**
 * Mock ba endpoint Telegram bằng biến trong closure. Đăng nhập và mọi API khác vẫn đi
 * tới backend thật, nên chỉ cần backend chạy, không cần bật Telegram thật.
 */
async function mockTelegramApi(page: Page, state: MockState) {
  const statusBody = () => ({
    enabled: state.enabled,
    bot_username: state.enabled ? 'quotify_bot' : null,
    account: state.account,
    pending_link: state.pending
      ? { expires_at: '2099-01-01T00:00:00Z', expires_in_seconds: 540 }
      : null,
  })

  await page.route('**/api/v1/users/me/telegram', async (route) => {
    const method = route.request().method()
    if (method === 'DELETE') {
      state.account = null
      return route.fulfill({ status: 204 })
    }
    return route.fulfill({ status: 200, json: statusBody() })
  })

  await page.route('**/api/v1/users/me/telegram/link-token', async (route) => {
    if (route.request().method() === 'DELETE') {
      state.pending = false
      return route.fulfill({ status: 204 })
    }
    state.pending = true
    return route.fulfill({
      status: 201,
      json: {
        deep_link: DEEP_LINK,
        expires_at: '2099-01-01T00:00:00Z',
        expires_in_seconds: 600,
        bot_username: 'quotify_bot',
      },
    })
  })
}

const accountA: MockAccount = {
  status: 'active',
  username: 'tele_a',
  first_name: 'An',
  linked_at: '2026-10-01T03:00:00Z',
}

test('links a first Telegram account and shows the result once Telegram completes', async ({
  page,
}) => {
  const state: MockState = { enabled: true, account: null, pending: false }
  await mockTelegramApi(page, state)
  await login(page)
  await page.goto('/profile')

  const panel = page.getByTestId('profile-telegram-panel')
  await expect(panel).toBeVisible()
  await expect(
    panel.getByText('Chưa có tài khoản Telegram nào được liên kết.'),
  ).toBeVisible()

  await page.getByTestId('profile-telegram-link-button').click()

  const open = page.getByTestId('profile-telegram-open-link')
  await expect(open).toHaveAttribute('href', DEEP_LINK)
  await expect(open).toHaveAttribute('target', '_blank')
  await expect(page.getByTestId('profile-telegram-qr')).toBeVisible()
  await expect(page.getByTestId('profile-telegram-countdown')).toContainText(
    'còn hiệu lực',
  )

  // Người dùng bấm Start trong Telegram: server đổi mã, giao diện thấy ở lần poll kế tiếp.
  state.account = {
    ...accountA,
    username: 'an_nguyen',
    linked_at: '2026-10-04T03:00:00Z',
  }
  state.pending = false

  await expect(page.getByTestId('profile-telegram-success')).toHaveText(
    'Đã liên kết tài khoản Telegram.',
    { timeout: 10_000 },
  )
  await expect(page.getByTestId('profile-telegram-account')).toContainText(
    '@an_nguyen',
  )
  await expect(page.getByTestId('profile-telegram-pending')).toHaveCount(0)

  const stored = await page.evaluate(() =>
    JSON.stringify({ ...localStorage, ...sessionStorage }),
  )
  expect(stored).not.toContain('e2e_one_time_code')
})

test('switches to another Telegram account and then unlinks through the dialog', async ({
  page,
}) => {
  const state: MockState = { enabled: true, account: accountA, pending: false }
  await mockTelegramApi(page, state)
  await login(page)
  await page.goto('/profile')

  await expect(page.getByTestId('profile-telegram-account')).toContainText(
    '@tele_a',
  )
  await page.getByTestId('profile-telegram-link-button').click()

  // Đang đổi: tài khoản cũ vẫn hiển thị cùng khối chờ.
  await expect(page.getByTestId('profile-telegram-pending')).toBeVisible()
  await expect(page.getByTestId('profile-telegram-account')).toContainText(
    '@tele_a',
  )

  state.account = {
    ...accountA,
    username: 'tele_b',
    linked_at: '2026-10-04T04:00:00Z',
  }
  state.pending = false
  await expect(page.getByTestId('profile-telegram-account')).toContainText(
    '@tele_b',
    { timeout: 10_000 },
  )
  await expect(page.getByTestId('profile-telegram-pending')).toHaveCount(0)

  await page.getByTestId('profile-telegram-unlink-button').click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toContainText('Hủy liên kết Telegram')
  await page.getByTestId('profile-telegram-confirm-unlink').click()

  await expect(page.getByTestId('profile-telegram-success')).toHaveText(
    'Đã hủy liên kết Telegram.',
  )
  await expect(page.getByTestId('profile-telegram-link-button')).toHaveText(
    /Liên kết Telegram/,
  )
  await expect(dialog).toBeHidden()
})

test('cancels a pending request', async ({ page }) => {
  const state: MockState = { enabled: true, account: null, pending: false }
  await mockTelegramApi(page, state)
  await login(page)
  await page.goto('/profile')

  await page.getByTestId('profile-telegram-link-button').click()
  await expect(page.getByTestId('profile-telegram-pending')).toBeVisible()
  await page.getByTestId('profile-telegram-cancel-button').click()

  await expect(page.getByTestId('profile-telegram-pending')).toHaveCount(0)
  expect(state.pending).toBe(false)
  await expect(page.getByTestId('profile-telegram-info')).toHaveCount(0)
})

test('hides the whole panel when the feature is switched off', async ({
  page,
}) => {
  const state: MockState = { enabled: false, account: null, pending: false }
  await mockTelegramApi(page, state)
  await login(page)
  await page.goto('/profile')

  await expect(page.getByText('Đổi mật khẩu').first()).toBeVisible()
  await expect(page.getByTestId('profile-telegram-panel')).toHaveCount(0)
})
