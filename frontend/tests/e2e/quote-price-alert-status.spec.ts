import { expect, test, type Page } from '@playwright/test'

const LOGGED_IN_COOKIE = 'quotify_logged_in'
const QUOTE_ID = 'e2e-quote'

async function mockAuth(page: Page) {
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
        email: 'reader@example.com',
        status: 'active',
        roles: ['user'],
        permissions: ['quotes.read'],
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

function line(id: string, name: string, status: string | null) {
  return {
    id,
    material_id: `material-${id}`,
    material_code: `M-${id}`,
    material_name: name,
    price_original: '970.00',
    currency: 'VND',
    unit: 'KG',
    delivery_month: '2026-11-01',
    line_order: 0,
    exchange_rate: null,
    exchange_rate_source: null,
    exchange_rate_source_mode: null,
    exchange_rate_entered_at: null,
    exchange_rate_manual_reason: null,
    exchange_rate_actor_id: null,
    import_tax_rate_percent: null,
    processing_cost_vnd_per_kg: null,
    price_converted_vnd_per_kg: '970.00',
    note: null,
    purchase_marked_at: null,
    purchase_marked_by_id: null,
    price_alert_status: status,
  }
}

async function mockQuote(page: Page) {
  const quote = {
    id: QUOTE_ID,
    supplier_id: 'supplier-1',
    supplier_name: 'Nhà cung cấp thử',
    supplier_code: 'NCC1',
    created_by_id: 'user-e2e',
    created_by_role: 'user',
    created_at: '2026-10-06T03:00:00+00:00',
    updated_at: '2026-10-06T03:00:00+00:00',
    cancelled_at: null,
    cancelled_by_id: null,
    cancel_reason: null,
    versions: [
      {
        id: 'version-1',
        quote_id: QUOTE_ID,
        version_number: 1,
        received_date: '2026-10-06',
        status: 'confirmed',
        file_id: null,
        is_backfilled: false,
        backfill_reason: null,
        correction_reason: null,
        created_by_id: 'user-e2e',
        created_by_name: 'Người xem',
        confirmed_at: '2026-10-06T03:00:00+00:00',
        confirmed_by_id: 'user-e2e',
        superseded_at: null,
        superseded_by_id: null,
        superseded_by_version_id: null,
        created_at: '2026-10-06T03:00:00+00:00',
        updated_at: '2026-10-06T03:00:00+00:00',
        lines: [
          line('1', 'Threonine', 'pending'),
          line('2', 'Lúa mỳ 3', null),
          line('3', 'Arginin', 'rejected'),
          line('4', 'Lysine', 'accepted'),
        ],
      },
    ],
  }
  await page.route(`**/api/v1/quotes/${QUOTE_ID}**`, (route) => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith(`/${QUOTE_ID}`)) {
      return route.fulfill({ status: 200, json: quote })
    }
    return route.fulfill({ status: 404, json: { detail: 'not found' } })
  })
}

test('shows the review state of flagged lines on the quote detail and nothing on normal lines', async ({
  page,
}) => {
  await mockAuth(page)
  await mockQuote(page)
  await page.goto(`/quotes/${QUOTE_ID}`)

  await expect(page.getByText('Danh sách dòng vật tư')).toBeVisible()
  const badges = page.getByTestId('price-alert-status')
  await expect(badges).toHaveCount(3)
  await expect(badges.nth(0)).toHaveText('Nghi nhập sai, chờ duyệt')
  await expect(badges.nth(1)).toHaveText('Đã đánh dấu nhập sai')
  await expect(badges.nth(2)).toHaveText('Giá đã được xác nhận')
  await expect(page.getByRole('cell', { name: 'Lúa mỳ 3' })).not.toContainText(
    'Nghi nhập sai',
  )
})
