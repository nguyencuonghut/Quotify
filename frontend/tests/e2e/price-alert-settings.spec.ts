import { expect, test, type Page } from '@playwright/test'

const LOGGED_IN_COOKIE = 'quotify_logged_in'

interface MockSettings {
  is_enabled: boolean
  anomaly_enabled: boolean
  reference_working_days: number
  light_from_percent: string
  medium_from_percent: string
  large_over_percent: string
  anomaly_percent: string
  anomaly_lookback_days: number
  max_trigger_delay_working_days: number
  staff_lookback_days: number
  dedupe_window_days: number
  immediate_cap_per_scan: number
  digest_hour_local: number
  reference_fallback_days: number
  enabled_since: string | null
  updated_at: string
}

interface MockMaterial {
  material_id: string
  code: string
  name: string
  override: {
    light_from_percent: string
    medium_from_percent: string
    large_over_percent: string
    anomaly_percent: string | null
  } | null
  freshness?: { is_watched: boolean; expected_interval_days: number } | null
}

const defaults = {
  light_from_percent: '2.50',
  medium_from_percent: '5.00',
  large_over_percent: '10.00',
  anomaly_percent: '30.00',
}

async function mockAuth(page: Page, permissions: string[]) {
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
        email: 'manager@example.com',
        status: 'active',
        roles: ['manager'],
        permissions,
        last_login_at: null,
        full_name: 'Quản lý',
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

function effective(material: MockMaterial) {
  const o = material.override
  return {
    light_from_percent: o?.light_from_percent ?? defaults.light_from_percent,
    medium_from_percent: o?.medium_from_percent ?? defaults.medium_from_percent,
    large_over_percent: o?.large_over_percent ?? defaults.large_over_percent,
    anomaly_percent: o?.anomaly_percent ?? defaults.anomaly_percent,
  }
}

async function mockPriceAlertApi(page: Page) {
  const settings: MockSettings = {
    is_enabled: false,
    anomaly_enabled: false,
    reference_working_days: 7,
    ...defaults,
    anomaly_lookback_days: 30,
    max_trigger_delay_working_days: 3,
    staff_lookback_days: 90,
    dedupe_window_days: 14,
    immediate_cap_per_scan: 30,
    digest_hour_local: 8,
    reference_fallback_days: 30,
    enabled_since: null,
    updated_at: '2026-10-06T03:00:00+00:00',
  }
  const materials: MockMaterial[] = [
    { material_id: 'm1', code: 'LM3', name: 'Lúa mỳ 3', override: null },
    { material_id: 'm2', code: 'NH', name: 'Ngô hạt', override: null },
  ]
  const calls = {
    puts: [] as unknown[],
    materialPuts: [] as unknown[],
    deletes: [] as string[],
    freshnessPuts: [] as unknown[],
    freshnessDeletes: [] as string[],
  }

  await page.route('**/api/v1/price-alert-settings', async (route) => {
    if (route.request().method() === 'PUT') {
      const body = route.request().postDataJSON()
      calls.puts.push(body)
      Object.assign(settings, body, {
        light_from_percent: String(body.light_from_percent),
        medium_from_percent: String(body.medium_from_percent),
        large_over_percent: String(body.large_over_percent),
        anomaly_percent: String(body.anomaly_percent),
        enabled_since: body.is_enabled ? '2026-10-06T04:00:00+00:00' : null,
      })
    }
    return route.fulfill({ status: 200, json: settings })
  })

  await page.route(
    '**/api/v1/price-alert-settings/materials?**',
    async (route) => {
      const search = new URL(route.request().url()).searchParams
        .get('search')
        ?.toLowerCase()
      const items = materials
        .filter((m) => !search || m.name.toLowerCase().includes(search))
        .map((m) => ({ ...m, effective: effective(m) }))
      return route.fulfill({
        status: 200,
        json: { items, total: items.length },
      })
    },
  )

  await page.route(
    '**/api/v1/price-alert-settings/materials/*',
    async (route) => {
      const id = route.request().url().split('/').pop() as string
      const material = materials.find(
        (m) => m.material_id === id,
      ) as MockMaterial
      if (route.request().method() === 'DELETE') {
        calls.deletes.push(id)
        material.override = null
        return route.fulfill({ status: 204 })
      }
      const body = route.request().postDataJSON()
      calls.materialPuts.push(body)
      material.override = {
        light_from_percent: body.light_from_percent.toFixed(2),
        medium_from_percent: body.medium_from_percent.toFixed(2),
        large_over_percent: body.large_over_percent.toFixed(2),
        anomaly_percent:
          body.anomaly_percent === null
            ? null
            : body.anomaly_percent.toFixed(2),
      }
      return route.fulfill({
        status: 200,
        json: {
          material_id: id,
          override: material.override,
          effective: effective(material),
        },
      })
    },
  )

  await page.route(
    '**/api/v1/price-alert-settings/materials/*/freshness',
    async (route) => {
      const id = route.request().url().split('/').slice(-2)[0] as string
      const material = materials.find(
        (m) => m.material_id === id,
      ) as MockMaterial
      if (route.request().method() === 'DELETE') {
        calls.freshnessDeletes.push(id)
        material.freshness = null
        return route.fulfill({ status: 204 })
      }
      const body = route.request().postDataJSON()
      calls.freshnessPuts.push(body)
      material.freshness = {
        is_watched: body.is_watched,
        expected_interval_days: body.expected_interval_days,
      }
      return route.fulfill({
        status: 200,
        json: { material_id: id, freshness: material.freshness },
      })
    },
  )

  return calls
}

test('turns the feature on and saves the form', async ({ page }) => {
  await mockAuth(page, ['price_alerts.manage'])
  const calls = await mockPriceAlertApi(page)
  await page.goto('/price-alert-settings')

  await expect(
    page.getByText('Mỗi lần bật lại, hệ thống bắt đầu quét'),
  ).toBeVisible()
  await page.locator('#price-alert-enabled').check()
  await page.getByTestId('settings-save').click()

  await expect(page.getByTestId('settings-success')).toHaveText(
    'Đã lưu cấu hình thông báo giá.',
  )
  await expect(page.getByText('Bật gần nhất lúc')).toBeVisible()
  expect(calls.puts).toHaveLength(1)
  expect(calls.puts[0]).toMatchObject({
    is_enabled: true,
    anomaly_enabled: false,
    medium_from_percent: 5,
    digest_hour_local: 8,
  })
})

test('blocks thresholds that do not rise and shows the message in Vietnamese', async ({
  page,
}) => {
  await mockAuth(page, ['price_alerts.manage'])
  const calls = await mockPriceAlertApi(page)
  await page.goto('/price-alert-settings')

  const medium = page.locator('#setting-mediumFromPercent')
  await medium.fill('2')
  await medium.blur()
  await page.getByTestId('settings-save').click()

  await expect(
    page.getByText(
      'Ngưỡng phải tăng dần: Nhẹ < Trung bình < Lớn < Bất thường.',
    ),
  ).toBeVisible()
  expect(calls.puts).toHaveLength(0)
})

test('edits a material override and goes back to the default', async ({
  page,
}) => {
  await mockAuth(page, ['price_alerts.manage'])
  const calls = await mockPriceAlertApi(page)
  await page.goto('/price-alert-settings')

  await page.getByTestId('material-search').fill('lúa')
  await expect(page.getByText('Ngô hạt')).toHaveCount(0)

  await page.getByTestId('material-edit').first().click()
  await page.locator('#material-lightFromPercent').fill('1')
  await page.locator('#material-mediumFromPercent').fill('3')
  await page.locator('#material-largeOverPercent').fill('6')
  await page.getByTestId('material-save').click()

  await expect(page.getByTestId('material-success')).toHaveText(
    'Đã lưu ngưỡng riêng cho Lúa mỳ 3.',
  )
  await expect(page.getByText('Ngưỡng riêng', { exact: true })).toBeVisible()
  expect(calls.materialPuts[0]).toMatchObject({
    light_from_percent: 1,
    medium_from_percent: 3,
    large_over_percent: 6,
    anomaly_percent: null,
  })

  await page.getByTestId('material-edit').first().click()
  await page.getByTestId('material-reset').click()
  await expect(page.getByTestId('material-success')).toHaveText(
    'Đã đưa Lúa mỳ 3 về ngưỡng mặc định.',
  )
  expect(calls.deletes).toEqual(['m1'])
})

test('stays inside the phone screen', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await mockAuth(page, ['price_alerts.manage'])
  await mockPriceAlertApi(page)
  await page.goto('/price-alert-settings')

  await expect(page.getByTestId('settings-save')).toBeVisible()
  await expect(page.getByText('Lúa mỳ 3')).toBeVisible()
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  )
  expect(overflow).toBeLessThanOrEqual(1)
})

test('sets the watch list config of a material and removes it again', async ({
  page,
}) => {
  await mockAuth(page, ['price_alerts.manage'])
  const calls = await mockPriceAlertApi(page)
  await page.goto('/price-alert-settings')

  const row = page.locator('tr', { hasText: 'Lúa mỳ 3' })
  await expect(row).toContainText('Chưa đặt')

  await row.getByTestId('material-watch').click()
  await expect(page.locator('#watch-interval')).toHaveValue('14 ngày')
  if (process.env.E2E_SCREENSHOT_DIR) {
    await page.waitForTimeout(600)
    await page.screenshot({
      path: `${process.env.E2E_SCREENSHOT_DIR}/watch-dialog.png`,
    })
  }

  await page.locator('#watch-interval').fill('10')
  await page.getByTestId('watch-save').click()

  await expect(page.getByTestId('material-success')).toHaveText(
    'Đã lưu theo dõi giá cho Lúa mỳ 3.',
  )
  expect(calls.freshnessPuts).toEqual([
    { is_watched: true, expected_interval_days: 10 },
  ])
  await expect(row).toContainText('Có')
  await expect(page.getByTestId('watch-save')).toBeHidden()
  await page.waitForTimeout(400)
  if (process.env.E2E_SCREENSHOT_DIR) {
    await page.screenshot({
      path: `${process.env.E2E_SCREENSHOT_DIR}/watch-table.png`,
      fullPage: true,
    })
  }
  await expect(row).toContainText('10')

  await row.getByTestId('material-watch').click()
  await page.getByTestId('watch-clear').click()
  await expect(page.getByTestId('material-success')).toHaveText(
    'Đã bỏ cấu hình theo dõi giá của Lúa mỳ 3.',
  )
  await expect(row).toContainText('Chưa đặt')
  expect(calls.freshnessDeletes).toEqual(['m1'])
})

test('blocks a watch interval outside 1 to 365 days with a Vietnamese message', async ({
  page,
}) => {
  await mockAuth(page, ['price_alerts.manage'])
  const calls = await mockPriceAlertApi(page)
  await page.goto('/price-alert-settings')

  await page
    .locator('tr', { hasText: 'Lúa mỳ 3' })
    .getByTestId('material-watch')
    .click()
  await page.locator('#watch-interval').fill('')
  await page.getByTestId('watch-save').click()

  await expect(page.getByTestId('watch-error')).toHaveText(
    'Chu kỳ phải là số nguyên từ 1 đến 365 ngày.',
  )
  expect(calls.freshnessPuts).toHaveLength(0)
})
