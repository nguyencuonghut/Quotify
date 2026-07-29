import { expect, test, type Page } from '@playwright/test'

const adminEmail = process.env.E2E_ADMIN_EMAIL
const adminPassword = process.env.E2E_ADMIN_PASSWORD

function requireE2ECredential(value: string | undefined, name: string): string {
  if (!value) {
    throw new Error(`${name} is required for quotes mobile E2E tests.`)
  }

  return value
}

async function loginAsAdmin(page: Page) {
  await page.goto('/login')

  await page
    .getByPlaceholder('Nhập email đăng nhập')
    .fill(requireE2ECredential(adminEmail, 'E2E_ADMIN_EMAIL'))
  await page
    .getByPlaceholder('Nhập mật khẩu')
    .fill(requireE2ECredential(adminPassword, 'E2E_ADMIN_PASSWORD'))
  await page.getByRole('button', { name: 'Đăng nhập' }).click()

  await expect(
    page.getByRole('heading', { name: 'Bảng điều khiển' }),
  ).toBeVisible()
}

test('quotes list renders as mobile cards instead of a wide desktop table', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await loginAsAdmin(page)

  await page.goto('/quotes')

  await expect(page.getByRole('heading', { name: 'Bảng báo giá' })).toBeVisible()
  await expect(page.locator('.quotes-page__mobile-list')).toBeVisible()
  await expect(page.locator('.quotes-page__table-wrapper')).toBeHidden()
  await expect(
    page.locator('.quotes-page__mobile-card, .quotes-page__mobile-state').first(),
  ).toBeVisible()
  const firstCard = page.locator('.quotes-page__mobile-card').first()
  if ((await firstCard.count()) > 0) {
    await expect(firstCard.getByText(/VNĐ\/KG/)).toBeVisible()
    await expect(firstCard).not.toContainText('₫ / KG')
  }
  const bodySize = await page.locator('body').evaluate((body) => ({
    clientWidth: body.clientWidth,
    scrollWidth: body.scrollWidth,
  }))
  expect(bodySize.scrollWidth).toBeLessThanOrEqual(bodySize.clientWidth)
})
