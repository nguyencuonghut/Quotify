import { expect, test, type Page } from '@playwright/test'

const adminEmail = process.env.E2E_ADMIN_EMAIL
const adminPassword = process.env.E2E_ADMIN_PASSWORD
const sampleQuoteId = '1dfc8c2a-8092-4731-a689-b8509084e749'

function requireE2ECredential(value: string | undefined, name: string): string {
  if (!value) {
    throw new Error(`${name} is required for quote detail filter E2E tests.`)
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

test('quote detail lines can be filtered by global search, material name and delivery month', async ({
  page,
}) => {
  await loginAsAdmin(page)
  await page.goto(`/quotes/${sampleQuoteId}`)

  await expect(
    page.getByRole('heading', { name: 'Phiếu báo giá nguyên liệu' }),
  ).toBeVisible()
  await expect(page.getByText('Danh sách dòng vật tư')).toBeVisible()

  await page.getByPlaceholder('Tìm mã, tên vật tư, giá, tháng...').fill('Ngô hạt')
  await expect(page.getByRole('cell', { name: 'Ngô hạt' }).first()).toBeVisible()

  await page.getByLabel('Tên vật tư').click()
  await page.getByRole('option', { name: 'Ngô hạt' }).click()
  await expect(page.getByRole('cell', { name: 'Ngô hạt' }).first()).toBeVisible()

  await page.getByLabel('Tháng giao').click()
  await page.getByRole('option', { name: '08/2026' }).click()
  await expect(page.locator('.quote-detail-page__lines-count')).toContainText(
    /^1\/\d+ dòng\s*$/,
  )
  await expect(page.getByRole('cell', { name: '08/2026' }).first()).toBeVisible()
})
