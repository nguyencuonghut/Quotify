import { expect, test } from '@playwright/test'

const adminEmail = process.env.E2E_ADMIN_EMAIL
const adminPassword = process.env.E2E_ADMIN_PASSWORD

test('inspect price-trends calls for history chart with 3 materials at delivery month 11/2024', async ({ page }) => {
  const calls: { url: string; status: number; pointCount: number | null }[] = []
  page.on('response', async (response) => {
    if (response.url().includes('/api/v1/dashboard/quotify/price-trends')) {
      let pointCount: number | null = null
      try {
        const body = await response.json()
        pointCount = Array.isArray(body.points) ? body.points.length : null
      } catch {
        pointCount = null
      }
      calls.push({ url: response.url(), status: response.status(), pointCount })
    }
  })

  await page.goto('/login')
  await page.getByPlaceholder('Nhập email đăng nhập').fill(adminEmail!)
  await page.getByPlaceholder('Nhập mật khẩu').fill(adminPassword!)
  await page.getByRole('button', { name: 'Đăng nhập' }).click()
  await expect(page.getByRole('heading', { name: 'Bảng điều khiển' })).toBeVisible()

  const historyPanel = page.locator('.dashboard-page__panel', {
    hasText: 'Diễn biến giá theo thời gian chào giá',
  })
  await historyPanel.getByPlaceholder('mm/yyyy').click()
  await page.waitForTimeout(200)
  await page.locator('.p-datepicker-select-year').click()
  await page.waitForTimeout(200)
  await page.locator('.p-datepicker-year').filter({ hasText: '2024' }).click()
  await page.waitForTimeout(200)
  await page.locator('.p-datepicker-month').filter({ hasText: 'Nov' }).click()
  await page.waitForTimeout(300)

  const dateValue = await historyPanel.getByPlaceholder('mm/yyyy').inputValue()
  console.log('DATE_PICKER_VALUE', dateValue)

  await historyPanel.locator('.p-multiselect').click()
  await page.waitForTimeout(200)
  for (const name of ['Ngô hạt', 'Lúa mì', 'Khô dầu đậu nành']) {
    await page.getByPlaceholder('Tìm vật tư...').fill(name)
    const option = page.getByRole('option', { name: new RegExp(name) }).first()
    await option.waitFor({ state: 'visible' })
    await page.waitForTimeout(300)
    await option.click()
    await page.waitForTimeout(500)
  }
  await page.keyboard.press('Escape')
  await page.waitForTimeout(1500)

  console.log('HISTORY_CALLS', JSON.stringify(calls, null, 2))
  await page.screenshot({ path: '.tmp-check/history-3-materials.png', fullPage: true })
})
