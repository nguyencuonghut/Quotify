import { expect, test, type Page } from '@playwright/test'

const LOGGED_IN_COOKIE = 'quotify_logged_in'

interface FreshnessItem {
  material_id: string
  material_code: string
  material_name: string
  material_type_id: string
  material_type_name: string
  is_watched: boolean
  expected_interval_days: number | null
  update_count: number
  supplier_count: number
  last_received_date: string | null
  age_days: number | null
  status: 'updated' | 'on_time' | 'overdue' | 'never'
  last_enterer_id: string | null
  last_enterer_label: string | null
}

function item(overrides: Partial<FreshnessItem>): FreshnessItem {
  return {
    material_id: 'm-1',
    material_code: 'NGO',
    material_name: 'Ngô hạt',
    material_type_id: 't-1',
    material_type_name: 'Nguyên liệu',
    is_watched: true,
    expected_interval_days: 7,
    update_count: 3,
    supplier_count: 2,
    last_received_date: '2026-10-06',
    age_days: 1,
    status: 'updated',
    last_enterer_id: 'u-1',
    last_enterer_label: 'Nguyễn Văn A',
    ...overrides,
  }
}

const CURRENT_WEEK = {
  week_start: '2026-10-05',
  week_end: '2026-10-11',
  as_of_date: '2026-10-07',
  summary: {
    watched_count: 3,
    updated_count: 1,
    on_time_count: 0,
    overdue_count: 2,
    unwatched_updated_count: 1,
  },
  items: [
    item({}),
    item({
      material_id: 'm-2',
      material_code: 'LYS',
      material_name: 'Lysine 99%',
      material_type_id: 't-2',
      material_type_name: 'Vi lượng',
      expected_interval_days: 14,
      update_count: 0,
      supplier_count: 0,
      last_received_date: '2026-09-20',
      age_days: 17,
      status: 'overdue',
      last_enterer_id: null,
      last_enterer_label: null,
    }),
    item({
      material_id: 'm-3',
      material_code: 'BAO',
      material_name: 'Bao bì 25kg',
      material_type_id: 't-3',
      material_type_name: 'Bao bì',
      expected_interval_days: 30,
      update_count: 0,
      supplier_count: 0,
      last_received_date: null,
      age_days: null,
      status: 'never',
      last_enterer_id: null,
      last_enterer_label: null,
    }),
    item({
      material_id: 'm-4',
      material_code: 'KHAC',
      material_name: 'Vật tư không theo dõi',
      is_watched: false,
      expected_interval_days: null,
      update_count: 1,
      supplier_count: 1,
      age_days: 0,
      last_received_date: '2026-10-07',
      status: 'updated',
    }),
  ],
}

const PREVIOUS_WEEK = {
  week_start: '2026-09-28',
  week_end: '2026-10-04',
  as_of_date: '2026-10-04',
  summary: {
    watched_count: 1,
    updated_count: 1,
    on_time_count: 0,
    overdue_count: 0,
    unwatched_updated_count: 0,
  },
  items: [
    item({
      material_id: 'm-9',
      material_name: 'Khô đậu tương',
      material_code: 'KDT',
    }),
  ],
}

async function mockAuth(page: Page, permissions: string[], roles: string[]) {
  await page.route('**/api/v1/auth/refresh', (route) =>
    route.fulfill({
      status: 200,
      json: {
        access_token: 'e2e-token',
        token_type: 'bearer',
        expires_in: 3600,
      },
    }),
  )
  await page.route('**/api/v1/auth/me', (route) =>
    route.fulfill({
      status: 200,
      json: {
        id: 'user-e2e',
        email: 'reader@example.com',
        status: 'active',
        roles,
        permissions,
        last_login_at: null,
        full_name: 'Người xem',
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

async function mockDashboardApi(page: Page) {
  const freshnessWeeks: Array<string | null> = []
  await page.route('**/api/v1/materials/lookup**', (route) =>
    route.fulfill({ status: 200, json: { items: [] } }),
  )
  await page.route('**/api/v1/dashboard/quotify/entry-kpis**', (route) =>
    route.fulfill({
      status: 200,
      json: { total_quote_count: 0, user_kpis: [] },
    }),
  )
  await page.route('**/api/v1/dashboard/quotify/price-trends**', (route) =>
    route.fulfill({
      status: 200,
      json: {
        summary: {
          min_price: null,
          max_price: null,
          avg_price: null,
          total_lines: 0,
          total_quotes: 0,
          purchased_lines: 0,
        },
        points: [],
        purchase_contexts: [],
      },
    }),
  )
  await page.route(
    '**/api/v1/dashboard/quotify/weekly-entry-activity**',
    (route) =>
      route.fulfill({
        status: 200,
        json: {
          week_start: '2026-10-05',
          week_end: '2026-10-11',
          total_quote_count: 0,
          active_user_count: 0,
          users_with_quotes: 0,
          users_without_quotes: 0,
          user_activities: [],
        },
      }),
  )
  await page.route(
    '**/api/v1/dashboard/quotify/material-freshness**',
    (route) => {
      const weekStart = new URL(route.request().url()).searchParams.get(
        'week_start',
      )
      freshnessWeeks.push(weekStart)
      return route.fulfill({
        status: 200,
        json: weekStart === '2026-09-28' ? PREVIOUS_WEEK : CURRENT_WEEK,
      })
    },
  )
  return { freshnessWeeks }
}

async function saveScreenshot(page: Page, name: string) {
  const directory = process.env.E2E_SCREENSHOT_DIR
  if (directory) {
    await page
      .getByTestId('material-freshness')
      .screenshot({ path: `${directory}/${name}.png` })
  }
}

test('a manager sees the freshness table, the settings link and follows the week filter', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await mockAuth(page, ['dashboard.read', 'price_alerts.manage'], ['manager'])
  const { freshnessWeeks } = await mockDashboardApi(page)

  await page.goto('/')

  const table = page.getByTestId('material-freshness')
  await expect(
    table.getByRole('heading', { name: 'Độ mới của giá theo vật tư' }),
  ).toBeVisible()
  await expect(table.getByText('Ngô hạt').first()).toBeVisible()
  await expect(table.getByText('Lysine 99%').first()).toBeVisible()
  await expect(table.getByText('Chưa có giá').first()).toBeVisible()
  await expect(
    table.getByTestId('material-freshness-card-overdue'),
  ).toContainText('2')
  await expect(table.getByTestId('settings-link')).toBeVisible()
  await saveScreenshot(page, 'desktop-current-week')

  // Dòng quá hạn và dòng chưa có giá phải được tô nổi trên bảng desktop (không chỉ có nhãn).
  const overdueRow = table.locator('tr.material-freshness__row--attention', {
    hasText: 'Lysine 99%',
  })
  await expect(overdueRow).toContainText('Quá hạn')
  await expect(overdueRow).toContainText('17 ngày')
  await expect(overdueRow).toContainText('14 ngày')
  const neverRow = table.locator('tr.material-freshness__row--attention', {
    hasText: 'Bao bì 25kg',
  })
  await expect(neverRow).toContainText('Chưa có giá')
  const backgroundOf = (row: typeof overdueRow) =>
    row.evaluate((element) => getComputedStyle(element).backgroundColor)
  const plainRow = table.locator('tbody tr', { hasText: 'Ngô hạt' }).first()
  expect(await backgroundOf(overdueRow)).not.toBe(await backgroundOf(plainRow))
  expect(await backgroundOf(neverRow)).not.toBe(await backgroundOf(plainRow))

  // Chọn một ngày của tuần trước rồi bấm "Lọc": bảng gọi lại với đúng thứ Hai của tuần đó.
  expect(freshnessWeeks).toHaveLength(1)
  await page.getByPlaceholder('Chọn tuần').fill('30/09/2026')
  // Mới chọn tuần mà chưa bấm "Lọc" thì bảng chưa gọi lại.
  await page.waitForTimeout(400)
  expect(freshnessWeeks).toHaveLength(1)
  await page.getByRole('button', { name: 'Lọc' }).first().click()
  await expect(table.getByText('Khô đậu tương').first()).toBeVisible()
  expect(freshnessWeeks[freshnessWeeks.length - 1]).toBe('2026-09-28')
})

test('a regular dashboard user sees the table but not the settings link', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await mockAuth(page, ['dashboard.read'], ['user'])
  await mockDashboardApi(page)

  await page.goto('/')

  const table = page.getByTestId('material-freshness')
  await expect(table.getByText('Ngô hạt').first()).toBeVisible()
  await expect(table.getByTestId('settings-link')).toHaveCount(0)
})

test('shows cards instead of the wide table and stays inside the phone screen', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await mockAuth(page, ['dashboard.read'], ['user'])
  await mockDashboardApi(page)

  await page.goto('/')

  const table = page.getByTestId('material-freshness')
  await expect(
    table.getByTestId('material-freshness-mobile-item').first(),
  ).toBeVisible()
  await expect(table.locator('.material-freshness__table-wrapper')).toBeHidden()
  await expect(table.getByTestId('material-freshness-mobile-item')).toHaveCount(
    4,
  )
  await saveScreenshot(page, 'mobile')
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  )
  expect(overflow).toBeLessThanOrEqual(1)
})

test('keeps the page inside the screen at the narrowest desktop width that still shows the table', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1290, height: 900 })
  await mockAuth(page, ['dashboard.read'], ['user'])
  await mockDashboardApi(page)

  await page.goto('/')

  const table = page.getByTestId('material-freshness')
  await expect(
    table.locator('.material-freshness__table-wrapper'),
  ).toBeVisible()
  await expect(table.getByText('Lysine 99%').first()).toBeVisible()
  await saveScreenshot(page, 'desktop-1290')
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  )
  expect(overflow).toBeLessThanOrEqual(1)
})
