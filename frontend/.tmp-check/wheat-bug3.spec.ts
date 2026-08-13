import { expect, test } from '@playwright/test'

const adminEmail = process.env.E2E_ADMIN_EMAIL
const adminPassword = process.env.E2E_ADMIN_PASSWORD

test('zoom into the chart region where Lúa mì should have data', async ({ page }) => {
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

  // Disable the min-max bands for Ngô hạt and Khô dầu đậu nành so only the
  // average lines remain, making Lúa mì's line (if present) easier to spot.
  const toggles = historyPanel.locator('.dashboard-page__comparison-band-toggle')
  const count = await toggles.count()
  for (let i = 0; i < count; i++) {
    const text = await toggles.nth(i).textContent()
    if (text && !text.includes('Lúa mì')) {
      await toggles.nth(i).locator('input, [role=checkbox]').first().click({ force: true })
      await page.waitForTimeout(150)
    }
  }
  await page.waitForTimeout(300)

  const canvas = historyPanel.locator('canvas')
  await canvas.scrollIntoViewIfNeeded()
  const box = await canvas.boundingBox()
  if (!box) throw new Error('no canvas box')
  await page.screenshot({
    path: '.tmp-check/zoom-wheat-region.png',
    clip: { x: box.x, y: box.y, width: box.width, height: box.height },
  })
})
