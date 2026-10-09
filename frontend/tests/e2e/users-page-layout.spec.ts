import { expect, test, type Page } from '@playwright/test'

const SHOT_DIR = process.env.E2E_SHOT_DIR

async function mockUsersPage(page: Page) {
  await page.route('**/api/v1/auth/refresh', (route) =>
    route.fulfill({
      status: 200,
      json: { access_token: 'e2e-token', token_type: 'bearer', expires_in: 3600 },
    }),
  )
  await page.route('**/api/v1/auth/me', (route) =>
    route.fulfill({
      status: 200,
      json: {
        id: 'admin-e2e',
        email: 'admin@example.com',
        status: 'active',
        roles: ['admin'],
        permissions: [
          'users.read',
          'users.create',
          'users.update',
          'users.delete',
          'users.import',
          'users.export',
          'roles.read',
        ],
        last_login_at: null,
        full_name: 'Quản trị',
        avatar_url: null,
      },
    }),
  )
  await page
    .context()
    .addCookies([
      { name: 'quotify_logged_in', value: '1', url: 'http://127.0.0.1:4173' },
    ])
  await page.route('**/api/v1/roles/lookup**', (route) =>
    route.fulfill({
      status: 200,
      json: {
        items: [
          { id: 'r1', name: 'admin', description: null, is_system: true, permissions: [], created_at: '2026-01-01T00:00:00Z' },
          { id: 'r2', name: 'manager', description: null, is_system: true, permissions: [], created_at: '2026-01-01T00:00:00Z' },
        ],
      },
    }),
  )
  await page.route('**/api/v1/users?**', (route) =>
    route.fulfill({
      status: 200,
      json: {
        total: 1,
        items: [
          {
            id: 'u1',
            email: 'nguyencuonghut55@gmail.com',
            status: 'active',
            roles: ['manager'],
            permissions: [],
            last_login_at: '2026-10-06T05:14:00Z',
            full_name: 'Quản lý phòng Mua',
            avatar_url: null,
            telegram_status: 'active',
          },
        ],
      },
    }),
  )
}

const VIEWPORTS = [
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'tablet', width: 900, height: 900 },
  { name: 'mobile', width: 390, height: 844 },
]

for (const viewport of VIEWPORTS) {
  test(`users page header is balanced and does not overflow on ${viewport.name}`, async ({
    page,
  }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height })
    await mockUsersPage(page)
    await page.goto('/users')

    const filters = page.locator('.users-page__filters')
    await expect(filters).toBeVisible()
    await expect(page.getByTestId('users-page-telegram-filter')).toBeVisible()

    const boxes = await page
      .locator('.users-page__filters > .users-page__filter-field')
      .evaluateAll((nodes) =>
        nodes.map((node) => {
          const rect = node.getBoundingClientRect()
          return { top: Math.round(rect.top), width: Math.round(rect.width) }
        }),
      )
    expect(boxes).toHaveLength(4)
    if (viewport.name === 'desktop') {
      // Cả bốn ô nằm một hàng.
      expect(new Set(boxes.map((box) => box.top)).size).toBe(1)
    }
    if (viewport.name === 'mobile') {
      // Mỗi ô một hàng, cùng độ rộng.
      expect(new Set(boxes.map((box) => box.top)).size).toBe(4)
      expect(new Set(boxes.map((box) => box.width)).size).toBe(1)
    }

    const bodySize = await page.locator('body').evaluate((body) => ({
      clientWidth: body.clientWidth,
      scrollWidth: body.scrollWidth,
    }))
    expect(bodySize.scrollWidth).toBeLessThanOrEqual(bodySize.clientWidth)

    if (SHOT_DIR) {
      await page.screenshot({ path: `${SHOT_DIR}/users-${viewport.name}.png` })
    }
  })
}
