import { expect, test, type Page } from '@playwright/test'

const adminEmail = process.env.E2E_ADMIN_EMAIL
const adminPassword = process.env.E2E_ADMIN_PASSWORD

function requireE2ECredential(value: string | undefined, name: string): string {
  if (!value) {
    throw new Error(`${name} is required for catalog import E2E tests.`)
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

test('shows meaningful counts when material type import has an invalid CSV header', async ({
  page,
}) => {
  const failedJob = {
    id: '11111111-1111-4111-8111-111111111111',
    file_id: '22222222-2222-4222-8222-222222222222',
    entity_type: 'material_types',
    status: 'failed',
    total_rows: 1,
    processed_rows: 0,
    failed_rows: 1,
    error_summary: 'Header CSV không hợp lệ.',
    errors_json: [
      {
        row: 1,
        code: '',
        errors: [
          'Header CSV không hợp lệ. Cần đúng các cột: code, name, status, note.',
        ],
      },
    ],
    created_by_id: '33333333-3333-4333-8333-333333333333',
    created_at: '2026-08-05T08:00:00Z',
    updated_at: '2026-08-05T08:00:00Z',
    file: null,
  }

  await page.route('**/api/v1/catalog-imports/material_types', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      status: 201,
      body: JSON.stringify(failedJob),
    })
  })

  await page.route(
    '**/api/v1/catalog-imports/11111111-1111-4111-8111-111111111111',
    async (route) => {
      await route.fulfill({
        contentType: 'application/json',
        status: 200,
        body: JSON.stringify(failedJob),
      })
    },
  )

  await loginAsAdmin(page)

  await page.getByRole('link', { name: 'Loại vật tư', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Loại vật tư' })).toBeVisible()

  await page.getByRole('button', { name: 'Import CSV' }).click()
  await expect(
    page.getByRole('dialog', { name: 'Import loại vật tư' }),
  ).toBeVisible()

  await page.locator('input[type="file"]').setInputFiles({
    name: 'invalid-material-types.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from('ma,ten,trang_thai,ghi_chu\nNGUYEN_LIEU,Nguyên liệu,active,'),
  })

  await expect(page.locator('.material-types-page__import-status')).toHaveClass(
    /material-types-page__import-status--failed/,
  )
  await expect(page.getByText('Header CSV không hợp lệ.')).toBeVisible()
  await expect(
    page.getByText('0 thành công, 1 lỗi trên 1 dòng'),
  ).toBeVisible()
  await expect(page.getByRole('button', { name: 'Tải file lỗi' })).toBeVisible()
})
