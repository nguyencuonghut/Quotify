import { expect, test, type Page } from '@playwright/test'

const LOGGED_IN_COOKIE = 'quotify_logged_in'

interface MockEvent {
  id: string
  review_status: 'pending' | 'accepted' | 'rejected'
  reviewed_by_name: string | null
  reviewed_at: string | null
}

/** Đăng nhập giả: bài kiểm thử này không cần mật khẩu thật, chỉ cần một trưởng phòng có quyền duyệt. */
async function mockAuth(page: Page) {
  const session = {
    access_token: 'e2e-token',
    token_type: 'bearer',
    expires_in: 3600,
  }
  await page.route('**/api/v1/auth/login', (route) =>
    route.fulfill({ status: 200, json: session }),
  )
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
        permissions: ['price_alerts.receive_all'],
        last_login_at: null,
        full_name: 'Quản lý',
        avatar_url: null,
      },
    }),
  )
}

// Cờ "đã đăng nhập" mà backend đặt khi login thật; thiếu nó thì tải lại trang sẽ không khôi phục phiên.
async function markLoggedIn(page: Page) {
  const url = new URL(
    page.url() === 'about:blank' ? 'http://127.0.0.1:4173' : page.url(),
  )
  await page
    .context()
    .addCookies([{ name: LOGGED_IN_COOKIE, value: '1', url: url.origin }])
}

async function login(page: Page) {
  await mockAuth(page)
  await markLoggedIn(page)
}

function item(event: MockEvent) {
  return {
    id: event.id,
    material_id: 'material-1',
    material_name: 'Threonine',
    delivery_month: '2026-11-01',
    received_date: '2026-09-15',
    price_new: '970.00',
    median: '25600.00',
    percent_change: '-96.21',
    reference_prices: ['25600.00', '25435.00', '25900.00'],
    reference_point_count: 3,
    quote_id: 'quote-1',
    entered_by_name: 'Lê Thị Hồng',
    review_status: event.review_status,
    attached_count: 0,
    age_working_days: 1,
    created_at: '2026-09-15T03:00:00+00:00',
    reviewed_by_name: event.reviewed_by_name,
    reviewed_at: event.reviewed_at,
  }
}

/** API giả bằng biến trong closure; đăng nhập và mọi API khác vẫn đi tới backend thật. */
async function mockAnomalyApi(
  page: Page,
  event: MockEvent,
  options: { conflictOnReview?: boolean } = {},
) {
  const reviews: string[] = []

  await page.route('**/api/v1/price-alerts/anomalies?**', async (route) => {
    const status = new URL(route.request().url()).searchParams.get('status')
    const pending = event.review_status === 'pending'
    const visible = status === 'pending' ? pending : !pending
    return route.fulfill({
      status: 200,
      json: { items: visible ? [item(event)] : [], total: visible ? 1 : 0 },
    })
  })

  await page.route(
    '**/api/v1/price-alerts/anomalies/*/review',
    async (route) => {
      const decision = route.request().postDataJSON().decision as string
      reviews.push(decision)
      if (options.conflictOnReview) {
        event.review_status = 'accepted'
        event.reviewed_by_name = 'An'
        event.reviewed_at = '2026-10-05T06:24:00+00:00'
        return route.fulfill({
          status: 409,
          json: {
            detail: {
              message: 'Điểm giá này đã được xử lý.',
              review_status: 'accepted',
              reviewed_by_name: 'An',
              reviewed_at: '2026-10-05T06:24:00+00:00',
            },
          },
        })
      }
      event.review_status = decision as MockEvent['review_status']
      event.reviewed_by_name = 'Quản lý'
      event.reviewed_at = '2026-10-05T06:30:00+00:00'
      return route.fulfill({
        status: 200,
        json: {
          id: event.id,
          review_status: event.review_status,
          reviewed_by_name: event.reviewed_by_name,
          reviewed_at: event.reviewed_at,
        },
      })
    },
  )

  return reviews
}

const freshEvent = (): MockEvent => ({
  id: 'event-1',
  review_status: 'pending',
  reviewed_by_name: null,
  reviewed_at: null,
})

test('confirms a pending price after the dialog and moves it to the history', async ({
  page,
}) => {
  const reviews = await mockAnomalyApi(page, freshEvent())
  await login(page)
  await page.goto('/price-alert-anomalies')

  await expect(page.getByText('Threonine').first()).toBeVisible()
  await page.getByTestId('anomaly-accept').first().click()
  await expect(page.getByTestId('anomaly-confirm-text')).toContainText(
    'Xác nhận Threonine, kỳ 11/2026, giá 970',
  )
  await page.getByTestId('anomaly-confirm').click()

  await expect(page.getByTestId('anomalies-success')).toContainText(
    'Đã ghi nhận giá đúng cho Threonine',
  )
  expect(reviews).toEqual(['accepted'])
  await expect(
    page.getByText('Không có điểm giá nào đang chờ duyệt.').first(),
  ).toBeVisible()

  await page.getByTestId('anomalies-tab-resolved').click()
  await expect(page.getByText('Đã xác nhận giá đúng').first()).toBeVisible()
})

test('tells who already decided when someone else handled the card first', async ({
  page,
}) => {
  await mockAnomalyApi(page, freshEvent(), { conflictOnReview: true })
  await login(page)
  await page.goto('/price-alert-anomalies')

  await page.getByTestId('anomaly-reject').first().click()
  await page.getByTestId('anomaly-confirm').click()

  await expect(page.getByTestId('anomalies-error')).toContainText(
    'Đã xác nhận giá đúng bởi An',
  )
})

test('keeps the review buttons usable on a phone screen', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const reviews = await mockAnomalyApi(page, freshEvent())
  await login(page)
  await page.goto('/price-alert-anomalies')

  const cards = page.getByTestId('anomaly-cards')
  await expect(cards.getByText('Threonine')).toBeVisible()
  await expect(cards.getByText('Kỳ giao hàng 11/2026')).toBeVisible()

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  )
  expect(overflow).toBeLessThanOrEqual(1)

  await cards.getByRole('button', { name: 'Nhập sai' }).click()
  await page.getByTestId('anomaly-confirm').click()
  await expect(page.getByTestId('anomalies-success')).toBeVisible()
  expect(reviews).toEqual(['rejected'])
})
