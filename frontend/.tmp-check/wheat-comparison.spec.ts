import { expect, test } from '@playwright/test'

const adminEmail = process.env.E2E_ADMIN_EMAIL
const adminPassword = process.env.E2E_ADMIN_PASSWORD

test('inspect comparison chart with 3 materials including sparse Lúa mì', async ({ page }) => {
  await page.goto('/login')
  await page.getByPlaceholder('Nhập email đăng nhập').fill(adminEmail!)
  await page.getByPlaceholder('Nhập mật khẩu').fill(adminPassword!)
  await page.getByRole('button', { name: 'Đăng nhập' }).click()
  await expect(page.getByRole('heading', { name: 'Bảng điều khiển' })).toBeVisible()

  const panel = page.locator('.dashboard-page__panel', {
    hasText: 'So sánh giá nguyên liệu theo kỳ hàng về',
  })
  await panel.locator('.p-multiselect').click()
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

  const toggles = panel.locator('.dashboard-page__comparison-band-toggle')
  const count = await toggles.count()
  for (let i = 0; i < count; i++) {
    const text = await toggles.nth(i).textContent()
    if (text && !text.includes('Lúa mì')) {
      await toggles.nth(i).locator('input, [role=checkbox]').first().click({ force: true })
      await page.waitForTimeout(150)
    }
  }
  await page.waitForTimeout(300)

  const canvas = panel.locator('canvas')
  await canvas.scrollIntoViewIfNeeded()
  const box = await canvas.boundingBox()
  if (!box) throw new Error('no canvas box')
  await page.screenshot({
    path: '.tmp-check/zoom-wheat-comparison.png',
    clip: { x: box.x, y: box.y, width: box.width, height: box.height },
  })
})
