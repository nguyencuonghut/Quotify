import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

interface AccessTokenResponse {
  access_token: string
}

const adminEmail = process.env.E2E_ADMIN_EMAIL
const adminPassword = process.env.E2E_ADMIN_PASSWORD

function requireE2ECredential(value: string | undefined, name: string): string {
  if (!value) {
    throw new Error(`${name} is required for audit log E2E tests.`)
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

async function getAdminAccessToken(request: APIRequestContext): Promise<string> {
  const response = await request.post('/api/v1/auth/login', {
    data: {
      email: requireE2ECredential(adminEmail, 'E2E_ADMIN_EMAIL'),
      password: requireE2ECredential(adminPassword, 'E2E_ADMIN_PASSWORD'),
    },
  })
  expect(response.ok()).toBe(true)

  const payload = (await response.json()) as AccessTokenResponse
  return payload.access_token
}

test('admin sees a real mutation event in audit logs and viewer renders on desktop and mobile', async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await loginAsAdmin(page)

  const accessToken = await getAdminAccessToken(request)
  const roleName = `audit_e2e_${Date.now()}`
  const createRoleResponse = await request.post('/api/v1/roles', {
    data: {
      name: roleName,
      description: 'Vai trò dùng để kiểm chứng Audit Log E2E.',
      permissions: ['dashboard.read'],
    },
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  })

  expect(createRoleResponse.status()).toBe(201)

  await page.getByRole('link', { name: 'Nhật ký audit', exact: true }).click()
  await expect(
    page.getByRole('heading', { name: 'Nhật ký audit' }),
  ).toBeVisible()

  await page.getByLabel('Hoạt động').click()
  await page.getByRole('option', { name: 'Tạo vai trò' }).click()
  await page.getByRole('button', { name: 'Lọc', exact: true }).click()

  await expect(page.getByText('roles.role_created').first()).toBeVisible()
  await expect(
    page.getByText(/Hiển thị từ 1 đến .* trên tổng số .* dòng/),
  ).toBeVisible()
  await page.getByRole('button', { name: 'Xem chi tiết nhật ký audit' }).first().click()
  await expect(
    page.getByRole('dialog', { name: 'Chi tiết nhật ký audit' }),
  ).toContainText(roleName)

  await page.screenshot({
    fullPage: true,
    path: 'test-results/audit-logs-desktop.png',
  })

  await page.setViewportSize({ width: 390, height: 844 })
  await expect(
    page.getByRole('heading', { name: 'Nhật ký audit' }),
  ).toBeVisible()

  await page.screenshot({
    fullPage: true,
    path: 'test-results/audit-logs-mobile.png',
  })
})

test('user without audit.read cannot read audit logs through the API', async ({
  page,
  request,
}) => {
  await loginAsAdmin(page)

  const adminAccessToken = await getAdminAccessToken(request)
  const limitedUserEmail = `audit-limited-${Date.now()}@example.test`
  const limitedUserPassword = 'AuditUser123!'
  const createUserResponse = await request.post('/api/v1/users', {
    data: {
      email: limitedUserEmail,
      password: limitedUserPassword,
      status: 'active',
      role_names: ['user'],
      full_name: 'Audit Limited User',
      avatar_url: null,
    },
    headers: {
      Authorization: `Bearer ${adminAccessToken}`,
    },
  })

  expect(createUserResponse.status()).toBe(201)

  const loginResponse = await request.post('/api/v1/auth/login', {
    data: {
      email: limitedUserEmail,
      password: limitedUserPassword,
    },
  })
  expect(loginResponse.status()).toBe(200)

  const limitedPayload = (await loginResponse.json()) as AccessTokenResponse
  const auditResponse = await request.get('/api/v1/audit-logs', {
    headers: {
      Authorization: `Bearer ${limitedPayload.access_token}`,
    },
  })

  expect(auditResponse.status()).toBe(403)
})
