import { expect, test, type Page } from '@playwright/test'

const adminEmail = process.env.E2E_ADMIN_EMAIL
const adminPassword = process.env.E2E_ADMIN_PASSWORD

function requireE2ECredential(value: string | undefined, name: string): string {
  if (!value) {
    throw new Error(`${name} is required for suppliers E2E tests.`)
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

test('opens supplier edit dialog on the first click after searching', async ({
  page,
}) => {
  await loginAsAdmin(page)

  await page.getByRole('link', { name: 'Nhà cung cấp', exact: true }).click()
  await expect(
    page.getByRole('heading', { name: 'Nhà cung cấp' }),
  ).toBeVisible()

  const searchInput = page.getByPlaceholder('Mã hoặc tên NCC...')
  await searchInput.fill('W')
  await expect(
    page.getByRole('cell', { name: 'Wilmar Agro Việt Nam (Wilmar Agro)' }),
  ).toBeVisible()

  const wilmarRow = page
    .getByRole('row')
    .filter({ hasText: 'Wilmar Agro Việt Nam (Wilmar Agro)' })
    .first()
  await wilmarRow.getByRole('button', { name: 'Chỉnh sửa' }).click()

  await expect(
    page.getByRole('dialog', { name: 'Chỉnh sửa NCC' }),
  ).toBeVisible()
  await expect(page.getByLabel('Tên NCC')).toHaveValue(
    'Wilmar Agro Việt Nam (Wilmar Agro)',
  )
})
