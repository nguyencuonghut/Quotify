import {
  expect,
  test,
  type APIRequestContext,
  type Page,
} from '@playwright/test'

/**
 * E2E toàn bộ chuỗi Telegram: giao diện thật, backend thật, DB thật. Chỉ Telegram là giả:
 * test gọi webhook thay cho Telegram, và (nếu có) đọc tin bot gửi đi từ Telegram giả.
 * Khác `profile-telegram.spec.ts` (mock endpoint ngay ở trình duyệt).
 */
const adminEmail = process.env.E2E_ADMIN_EMAIL
const adminPassword = process.env.E2E_ADMIN_PASSWORD
const webhookSecret = process.env.E2E_TELEGRAM_WEBHOOK_SECRET
const fakeTelegramUrl = process.env.E2E_FAKE_TELEGRAM_URL

test.skip(
  !webhookSecret,
  'E2E_TELEGRAM_WEBHOOK_SECRET chưa đặt: bỏ qua E2E Telegram đầy đủ.',
)

interface SentMessage {
  chat_id: number
  text: string
}

function requireValue(value: string | undefined, name: string): string {
  if (!value) {
    throw new Error(`${name} is required for the Telegram E2E tests.`)
  }

  return value
}

// Khóa unique của telegram_user_id nên mỗi lần chạy phải dùng id khác.
function randomTelegramId(): number {
  return 7_000_000_000 + Math.floor(Math.random() * 1_000_000_000)
}

let updateCounter = Math.floor(Math.random() * 1_000_000) * 1000

async function login(page: Page) {
  await page.goto('/login')
  await page
    .getByPlaceholder('Nhập email đăng nhập')
    .fill(requireValue(adminEmail, 'E2E_ADMIN_EMAIL'))
  await page
    .getByPlaceholder('Nhập mật khẩu')
    .fill(requireValue(adminPassword, 'E2E_ADMIN_PASSWORD'))
  await page.getByRole('button', { name: 'Đăng nhập' }).click()
  await page.waitForURL((url) => !url.pathname.startsWith('/login'))
}

function sendAsTelegram(
  request: APIRequestContext,
  text: string,
  telegramUserId: number,
  username: string,
  secret: string | null = webhookSecret ?? null,
) {
  updateCounter += 1
  return request.post('/api/v1/telegram/webhook', {
    headers: secret ? { 'X-Telegram-Bot-Api-Secret-Token': secret } : {},
    data: {
      update_id: updateCounter,
      message: {
        message_id: 1,
        date: 0,
        text,
        chat: { id: telegramUserId, type: 'private' },
        from: {
          id: telegramUserId,
          is_bot: false,
          first_name: 'Người thử',
          username,
        },
      },
    },
  })
}

async function botMessagesTo(
  request: APIRequestContext,
  chatId: number,
): Promise<string[]> {
  if (!fakeTelegramUrl) return []
  const response = await request.get(`${fakeTelegramUrl}/__sent`, {
    params: { chat_id: String(chatId) },
  })
  return ((await response.json()) as SentMessage[]).map((item) => item.text)
}

async function codeFromLink(page: Page): Promise<string> {
  const link = await page
    .getByTestId('profile-telegram-link-input')
    .inputValue()
  const code = link.split('start=')[1]
  expect(code, 'đường dẫn phải có mã sau start=').toBeTruthy()
  return code!
}

/** Dọn trạng thái còn sót từ lần chạy trước (DB test có thể được giữ lại giữa các lần). */
async function resetPanel(page: Page) {
  if (await page.getByTestId('profile-telegram-cancel-button').count()) {
    await page.getByTestId('profile-telegram-cancel-button').click()
    await expect(page.getByTestId('profile-telegram-pending')).toHaveCount(0)
  }
  if (await page.getByTestId('profile-telegram-unlink-button').count()) {
    await page.getByTestId('profile-telegram-unlink-button').click()
    await page.getByTestId('profile-telegram-confirm-unlink').click()
    await expect(page.getByTestId('profile-telegram-account')).toHaveCount(0)
  }
}

test('links, switches and unlinks a Telegram account through the real backend', async ({
  page,
  request,
}) => {
  const firstTelegram = randomTelegramId()
  const secondTelegram = randomTelegramId()
  const firstName = `e2e_a_${firstTelegram}`
  const secondName = `e2e_b_${secondTelegram}`

  await login(page)
  await page.goto('/profile')
  await expect(page.getByTestId('profile-telegram-panel')).toBeVisible()
  await resetPanel(page)

  // Liên kết lần đầu: mã trong đường dẫn do backend thật cấp.
  await page.getByTestId('profile-telegram-link-button').click()
  const firstCode = await codeFromLink(page)
  expect(
    (
      await sendAsTelegram(
        request,
        `/start ${firstCode}`,
        firstTelegram,
        firstName,
      )
    ).status(),
  ).toBe(200)

  await expect(page.getByTestId('profile-telegram-success')).toHaveText(
    'Đã liên kết tài khoản Telegram.',
    { timeout: 15_000 },
  )
  await expect(page.getByTestId('profile-telegram-account')).toContainText(
    `@${firstName}`,
  )
  expect((await botMessagesTo(request, firstTelegram)).join('\n')).toContain(
    'Đã liên kết với tài khoản',
  )

  // Mã đã dùng thì không dùng lại được.
  await sendAsTelegram(
    request,
    `/start ${firstCode}`,
    secondTelegram,
    secondName,
  )
  expect((await botMessagesTo(request, secondTelegram)).join('\n')).toContain(
    'không hợp lệ',
  )

  // Đổi sang tài khoản Telegram khác.
  await page.getByTestId('profile-telegram-link-button').click()
  const secondCode = await codeFromLink(page)
  await sendAsTelegram(
    request,
    `/start ${secondCode}`,
    secondTelegram,
    secondName,
  )

  await expect(page.getByTestId('profile-telegram-account')).toContainText(
    `@${secondName}`,
    { timeout: 15_000 },
  )
  await expect(page.getByTestId('profile-telegram-pending')).toHaveCount(0)
  expect((await botMessagesTo(request, firstTelegram)).join('\n')).toContain(
    'đã được thay thế',
  )

  // Hủy liên kết qua hộp thoại xác nhận.
  await page.getByTestId('profile-telegram-unlink-button').click()
  await page.getByTestId('profile-telegram-confirm-unlink').click()
  await expect(page.getByTestId('profile-telegram-success')).toHaveText(
    'Đã hủy liên kết Telegram.',
  )
  await expect(page.getByTestId('profile-telegram-empty')).toBeVisible()
})

test('stops linking from Telegram with /stop and refuses a wrong webhook secret', async ({
  page,
  request,
}) => {
  const telegramId = randomTelegramId()
  const username = `e2e_c_${telegramId}`

  await login(page)
  await page.goto('/profile')
  await resetPanel(page)
  await page.getByTestId('profile-telegram-link-button').click()
  const code = await codeFromLink(page)

  const forged = await sendAsTelegram(
    request,
    `/start ${code}`,
    telegramId,
    username,
    'sai-secret',
  )
  expect(forged.status()).toBe(403)
  await expect(page.getByTestId('profile-telegram-pending')).toBeVisible()

  await sendAsTelegram(request, `/start ${code}`, telegramId, username)
  await expect(page.getByTestId('profile-telegram-account')).toContainText(
    `@${username}`,
    { timeout: 15_000 },
  )

  await sendAsTelegram(request, '/stop', telegramId, username)
  // Giao diện làm mới khi cửa sổ lấy lại focus, nên tải lại trang để thấy kết quả của /stop.
  await page.reload()
  await expect(page.getByTestId('profile-telegram-empty')).toBeVisible()
  expect((await botMessagesTo(request, telegramId)).join('\n')).toContain(
    'Đã hủy liên kết',
  )
})
