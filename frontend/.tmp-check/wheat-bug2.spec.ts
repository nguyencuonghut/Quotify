import { expect, test } from '@playwright/test'

const adminEmail = process.env.E2E_ADMIN_EMAIL
const adminPassword = process.env.E2E_ADMIN_PASSWORD

test('inspect chart.js dataset internals for Lúa mì', async ({ page }) => {
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

  const canvas = historyPanel.locator('canvas')
  const chartInfo = await canvas.evaluate((el: HTMLCanvasElement) => {
    // Chart.js v4 registers instances in a global registry accessible via Chart.getChart
    // @ts-expect-error - Chart is a global exposed by the chart.js UMD/ESM bundle loaded on this page
    const chart = window.Chart ? window.Chart.getChart(el) : null
    if (!chart) return { error: 'no chart found via window.Chart' }
    return {
      labels: chart.data.labels,
      datasets: chart.data.datasets.map((d: any) => ({
        label: d.label,
        data: d.data,
        borderColor: d.borderColor,
        order: d.order,
        hidden: d.hidden,
      })),
    }
  })
  console.log('CHART_INTERNALS', JSON.stringify(chartInfo, null, 2))
})
