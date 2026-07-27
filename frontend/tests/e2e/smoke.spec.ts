import { expect, test } from '@playwright/test'

test('redirects anonymous users to the login page', async ({ page }) => {
  await page.goto('/')

  await expect(
    page.getByRole('heading', { name: 'Hồng Hà HRMS' }),
  ).toBeVisible()
  await expect(page.getByText('Hệ thống Quản lý Nhân sự')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Đăng nhập' })).toBeVisible()
})
