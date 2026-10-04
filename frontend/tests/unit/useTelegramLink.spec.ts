import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope } from 'vue'

import { ApiError } from '@/api/http'
import { useTelegramLink } from '@/composables/useTelegramLink'
import { useAuthStore } from '@/stores/auth.store'
import type { TelegramLinkStatus, TelegramLinkToken } from '@/types/telegram'

const telegramApiMock = vi.hoisted(() => ({
  getTelegramLinkStatus: vi.fn(),
  createTelegramLinkToken: vi.fn(),
  cancelTelegramLinkRequest: vi.fn(),
  unlinkTelegram: vi.fn(),
}))

vi.mock('@/api/telegram.api', () => telegramApiMock)

const ACCOUNT_A = {
  status: 'active' as const,
  username: 'tele_a',
  firstName: 'An',
  linkedAt: '2026-10-01T03:00:00Z',
}
const ACCOUNT_B = {
  ...ACCOUNT_A,
  username: 'tele_b',
  linkedAt: '2026-10-04T03:00:00Z',
}

function status(
  overrides: Partial<TelegramLinkStatus> = {},
): TelegramLinkStatus {
  return {
    enabled: true,
    botUsername: 'quotify_bot',
    account: null,
    pending: null,
    ...overrides,
  }
}

function pending(seconds: number): TelegramLinkStatus['pending'] {
  return { expiresAt: '2026-10-04T10:10:00Z', expiresInSeconds: seconds }
}

function token(seconds = 600): TelegramLinkToken {
  return {
    deepLink: 'https://t.me/quotify_bot?start=abc_DEF-123',
    expiresAt: '2026-10-04T10:10:00Z',
    expiresInSeconds: seconds,
    botUsername: 'quotify_bot',
  }
}

/** Đồng hồ đơn điệu giả: tiến lên cùng fake timers, độc lập với `Date`. */
function createClock() {
  let now = 0
  return {
    now: () => now,
    advance: (ms: number) => {
      now += ms
    },
  }
}

describe('useTelegramLink', () => {
  let scope = effectScope()
  let clock = createClock()

  function mount() {
    const link = scope.run(() => useTelegramLink({ now: clock.now }))
    if (!link) throw new Error('scope không chạy')
    return link
  }

  /** Server thật: số giây còn lại giảm dần theo thời gian, hết hạn thì không còn `pending`. */
  function serverCountingDownFrom(seconds: number) {
    telegramApiMock.getTelegramLinkStatus.mockImplementation(async () => {
      const left = seconds - Math.floor(clock.now() / 1000)
      return status({ pending: left > 0 ? pending(left) : null })
    })
  }

  /** Tiến fake timers và đồng hồ đơn điệu giả cùng lúc, từng giây một cho sát thực tế. */
  async function advance(ms: number) {
    for (let elapsed = 0; elapsed < ms; elapsed += 1000) {
      const step = Math.min(1000, ms - elapsed)
      clock.advance(step)
      await vi.advanceTimersByTimeAsync(step)
    }
  }

  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
    vi.useFakeTimers()
    scope = effectScope()
    clock = createClock()
    useAuthStore().accessToken = 'mock-access-token'
    telegramApiMock.getTelegramLinkStatus.mockResolvedValue(status())
  })

  afterEach(() => {
    scope.stop()
    vi.useRealTimers()
  })

  it('loads the status and starts a link request with the current access token', async () => {
    telegramApiMock.createTelegramLinkToken.mockResolvedValue(token())
    const link = mount()

    await link.bootstrap()
    expect(link.mode.value).toBe('unlinked')
    expect(link.enabled.value).toBe(true)

    useAuthStore().accessToken = 'rotated-access-token'
    await link.startLinking()

    expect(telegramApiMock.createTelegramLinkToken).toHaveBeenCalledWith(
      'rotated-access-token',
    )
    expect(link.mode.value).toBe('pending')
    expect(link.deepLink.value).toBe(
      'https://t.me/quotify_bot?start=abc_DEF-123',
    )
    expect(link.remainingSeconds.value).toBe(600)
  })

  it('stays hidden until the first status arrives and respects enabled=false', async () => {
    telegramApiMock.getTelegramLinkStatus.mockResolvedValue(
      status({ enabled: false, botUsername: null }),
    )
    const link = mount()

    expect(link.mode.value).toBe('loading')
    expect(link.isVisible.value).toBe(false)

    await link.bootstrap()

    expect(link.enabled.value).toBe(false)
    expect(link.isVisible.value).toBe(false)
  })

  it('shows an error mode when the first load fails and retries on demand', async () => {
    telegramApiMock.getTelegramLinkStatus.mockRejectedValueOnce(
      new ApiError('x', 500),
    )
    const link = mount()

    await link.bootstrap()

    expect(link.mode.value).toBe('error')
    expect(link.isVisible.value).toBe(true)
    expect(link.errorMessage.value).toBe(
      'Hệ thống đang gặp sự cố. Vui lòng thử lại sau.',
    )

    await link.reload()

    expect(link.mode.value).toBe('unlinked')
    expect(link.errorMessage.value).toBeNull()
  })

  it('polls every 3 seconds while pending and stops once the server clears it', async () => {
    telegramApiMock.createTelegramLinkToken.mockResolvedValue(token())
    const link = mount()
    await link.bootstrap()
    await link.startLinking()
    telegramApiMock.getTelegramLinkStatus.mockClear()
    telegramApiMock.getTelegramLinkStatus.mockResolvedValue(
      status({ pending: pending(597) }),
    )

    await advance(3000)
    await advance(3000)
    expect(telegramApiMock.getTelegramLinkStatus).toHaveBeenCalledTimes(2)

    telegramApiMock.getTelegramLinkStatus.mockResolvedValue(
      status({ account: ACCOUNT_A }),
    )
    await advance(3000)
    expect(link.mode.value).toBe('linked')
    expect(link.successMessage.value).toBe('Đã liên kết tài khoản Telegram.')
    expect(link.deepLink.value).toBeNull()

    telegramApiMock.getTelegramLinkStatus.mockClear()
    await advance(10000)
    expect(telegramApiMock.getTelegramLinkStatus).not.toHaveBeenCalled()
  })

  it('does not poll when nothing is pending', async () => {
    const link = mount()
    await link.bootstrap()
    telegramApiMock.getTelegramLinkStatus.mockClear()

    await advance(10000)

    expect(telegramApiMock.getTelegramLinkStatus).not.toHaveBeenCalled()
  })

  it('keeps the current account while switching, and finishes when linked_at changes', async () => {
    telegramApiMock.getTelegramLinkStatus.mockResolvedValue(
      status({ account: ACCOUNT_A }),
    )
    telegramApiMock.createTelegramLinkToken.mockResolvedValue(token())
    const link = mount()
    await link.bootstrap()

    await link.startLinking()

    expect(link.mode.value).toBe('linked')
    expect(link.isPending.value).toBe(true)
    expect(link.account.value?.username).toBe('tele_a')
    expect(link.isSwitching.value).toBe(true)

    telegramApiMock.getTelegramLinkStatus.mockResolvedValue(
      status({ account: ACCOUNT_B }),
    )
    await advance(3000)

    expect(link.account.value?.username).toBe('tele_b')
    expect(link.isPending.value).toBe(false)
    expect(link.successMessage.value).toBe('Đã liên kết tài khoản Telegram.')
  })

  it('reports an expired link when the server clears it without a new account', async () => {
    telegramApiMock.createTelegramLinkToken.mockResolvedValue(token())
    const link = mount()
    await link.bootstrap()
    await link.startLinking()

    telegramApiMock.getTelegramLinkStatus.mockResolvedValue(status())
    await advance(3000)

    expect(link.mode.value).toBe('unlinked')
    expect(link.infoMessage.value).toBe(
      'Đường dẫn liên kết đã hết hạn hoặc bị thay thế. Hãy tạo đường dẫn mới.',
    )
    expect(link.successMessage.value).toBeNull()
  })

  it('cancels a pending request through the API without an expiry notice', async () => {
    telegramApiMock.createTelegramLinkToken.mockResolvedValue(token())
    telegramApiMock.cancelTelegramLinkRequest.mockResolvedValue(undefined)
    const link = mount()
    await link.bootstrap()
    await link.startLinking()

    await link.cancelPending()
    telegramApiMock.getTelegramLinkStatus.mockClear()
    await advance(10000)

    expect(telegramApiMock.cancelTelegramLinkRequest).toHaveBeenCalledWith(
      'mock-access-token',
    )
    expect(link.isPending.value).toBe(false)
    expect(link.deepLink.value).toBeNull()
    expect(link.infoMessage.value).toBeNull()
    expect(telegramApiMock.getTelegramLinkStatus).not.toHaveBeenCalled()
  })

  it('ignores a status response that was requested before the user cancelled', async () => {
    telegramApiMock.createTelegramLinkToken.mockResolvedValue(token())
    telegramApiMock.cancelTelegramLinkRequest.mockResolvedValue(undefined)
    const link = mount()
    await link.bootstrap()
    await link.startLinking()
    let release: (value: TelegramLinkStatus) => void = () => undefined
    telegramApiMock.getTelegramLinkStatus.mockReturnValue(
      new Promise<TelegramLinkStatus>((resolve) => {
        release = resolve
      }),
    )
    await advance(3000) // poll đang bay, server lúc đó vẫn còn mã chờ

    await link.cancelPending()
    release(status({ pending: pending(400) })) // phản hồi cũ đến muộn
    await advance(0)

    expect(link.isPending.value).toBe(false)
    expect(link.deepLink.value).toBeNull()
    expect(link.infoMessage.value).toBeNull()
  })

  it('ignores a status response that was requested before a new link was issued', async () => {
    const link = mount()
    await link.bootstrap()
    let release: (value: TelegramLinkStatus) => void = () => undefined
    telegramApiMock.getTelegramLinkStatus.mockReturnValue(
      new Promise<TelegramLinkStatus>((resolve) => {
        release = resolve
      }),
    )
    window.dispatchEvent(new Event('focus')) // làm mới đang bay, server chưa có mã
    telegramApiMock.createTelegramLinkToken.mockResolvedValue(token())

    await link.startLinking()
    release(status()) // phản hồi cũ: không có mã chờ
    await advance(0)

    expect(link.isPending.value).toBe(true)
    expect(link.deepLink.value).toBe(
      'https://t.me/quotify_bot?start=abc_DEF-123',
    )
  })

  it('counts down from the server-provided seconds regardless of the system clock', async () => {
    telegramApiMock.createTelegramLinkToken.mockResolvedValue(token(120))
    const link = mount()
    await link.bootstrap()
    await link.startLinking()
    serverCountingDownFrom(120)
    // Đồng hồ hệ thống bị lệch 1 giờ không được ảnh hưởng đếm ngược.
    vi.setSystemTime(Date.now() + 3_600_000)

    await advance(45_000)

    expect(link.remainingSeconds.value).toBe(75)
    expect(link.isExpired.value).toBe(false)
  })

  it('drops the link when another tab issued a newer one', async () => {
    telegramApiMock.createTelegramLinkToken.mockResolvedValue(token())
    const link = mount()
    await link.bootstrap()
    await link.startLinking()
    expect(link.deepLink.value).not.toBeNull()

    // Tab khác cấp mã mới: server báo một hạn khác với hạn của mã đang giữ trong tab này.
    telegramApiMock.getTelegramLinkStatus.mockResolvedValue(
      status({
        pending: { expiresAt: '2026-10-04T10:12:00Z', expiresInSeconds: 590 },
      }),
    )
    await advance(3000)

    expect(link.deepLink.value).toBeNull()
    expect(link.isPending.value).toBe(true)
    expect(link.infoMessage.value).toBe(
      'Đường dẫn trong tab này đã bị thay thế bởi đường dẫn mới hơn. Hãy tạo đường dẫn mới.',
    )
  })

  it('keeps the link when the server reports the same expiry with different formatting', async () => {
    telegramApiMock.createTelegramLinkToken.mockResolvedValue({
      ...token(),
      expiresAt: '2026-10-04T10:10:00.123456Z',
    })
    const link = mount()
    await link.bootstrap()
    await link.startLinking()

    telegramApiMock.getTelegramLinkStatus.mockResolvedValue(
      status({
        pending: {
          expiresAt: '2026-10-04T10:10:00.123456+00:00',
          expiresInSeconds: 597,
        },
      }),
    )
    await advance(3000)

    expect(link.deepLink.value).not.toBeNull()
    expect(link.infoMessage.value).toBeNull()
  })

  it('formats the remaining time as mm:ss', async () => {
    telegramApiMock.createTelegramLinkToken.mockResolvedValue(token(600))
    const link = mount()
    await link.bootstrap()
    await link.startLinking()
    serverCountingDownFrom(600)

    expect(link.remainingLabel.value).toBe('10:00')
    await advance(65_000)
    expect(link.remainingLabel.value).toBe('08:55')
  })

  it('marks the link as expired locally when the countdown reaches zero', async () => {
    telegramApiMock.createTelegramLinkToken.mockResolvedValue(token(5))
    const link = mount()
    await link.bootstrap()
    await link.startLinking()
    serverCountingDownFrom(5)

    await advance(5000)

    expect(link.remainingSeconds.value).toBe(0)
    expect(link.isExpired.value).toBe(true)

    // Poll kế tiếp: server xác nhận đã hết hạn nên không còn chờ.
    await advance(1000)
    expect(link.isPending.value).toBe(false)
  })

  it('never starts overlapping status requests', async () => {
    telegramApiMock.createTelegramLinkToken.mockResolvedValue(token())
    const link = mount()
    await link.bootstrap()
    await link.startLinking()
    let release: (value: TelegramLinkStatus) => void = () => undefined
    telegramApiMock.getTelegramLinkStatus.mockClear()
    telegramApiMock.getTelegramLinkStatus.mockReturnValue(
      new Promise<TelegramLinkStatus>((resolve) => {
        release = resolve
      }),
    )

    await advance(3000)
    await advance(3000)
    await advance(3000)
    expect(telegramApiMock.getTelegramLinkStatus).toHaveBeenCalledTimes(1)

    release(status({ pending: pending(500) }))
    await advance(3000)
    expect(telegramApiMock.getTelegramLinkStatus).toHaveBeenCalledTimes(2)
  })

  it('does not poll while the tab is hidden and refreshes once when it is shown again', async () => {
    telegramApiMock.createTelegramLinkToken.mockResolvedValue(token())
    const link = mount()
    await link.bootstrap()
    await link.startLinking()
    telegramApiMock.getTelegramLinkStatus.mockClear()
    telegramApiMock.getTelegramLinkStatus.mockResolvedValue(
      status({ pending: pending(500) }),
    )

    const hidden = vi.spyOn(document, 'hidden', 'get').mockReturnValue(true)
    await advance(9000)
    expect(telegramApiMock.getTelegramLinkStatus).not.toHaveBeenCalled()

    hidden.mockReturnValue(false)
    document.dispatchEvent(new Event('visibilitychange'))
    await vi.advanceTimersByTimeAsync(0)
    expect(telegramApiMock.getTelegramLinkStatus).toHaveBeenCalledTimes(1)
    hidden.mockRestore()
  })

  it('refreshes exactly once when the window regains focus', async () => {
    const link = mount()
    await link.bootstrap()
    telegramApiMock.getTelegramLinkStatus.mockClear()

    window.dispatchEvent(new Event('focus'))
    await vi.advanceTimersByTimeAsync(0)

    expect(telegramApiMock.getTelegramLinkStatus).toHaveBeenCalledTimes(1)
  })

  it('removes timers and listeners on dispose', async () => {
    telegramApiMock.createTelegramLinkToken.mockResolvedValue(token())
    const link = mount()
    await link.bootstrap()
    await link.startLinking()
    telegramApiMock.getTelegramLinkStatus.mockClear()

    link.dispose()
    window.dispatchEvent(new Event('focus'))
    document.dispatchEvent(new Event('visibilitychange'))
    await advance(10000)

    expect(telegramApiMock.getTelegramLinkStatus).not.toHaveBeenCalled()
    expect(vi.getTimerCount()).toBe(0)
  })

  it('unlinks through a confirmation step', async () => {
    telegramApiMock.getTelegramLinkStatus.mockResolvedValue(
      status({ account: ACCOUNT_A }),
    )
    telegramApiMock.unlinkTelegram.mockResolvedValue(undefined)
    const link = mount()
    await link.bootstrap()

    link.openUnlinkDialog()
    expect(link.isUnlinkDialogVisible.value).toBe(true)
    await link.confirmUnlink()

    expect(telegramApiMock.unlinkTelegram).toHaveBeenCalledWith(
      'mock-access-token',
    )
    expect(link.account.value).toBeNull()
    expect(link.mode.value).toBe('unlinked')
    expect(link.isUnlinkDialogVisible.value).toBe(false)
    expect(link.successMessage.value).toBe('Đã hủy liên kết Telegram.')
  })

  it('shows a blocked account as such', async () => {
    telegramApiMock.getTelegramLinkStatus.mockResolvedValue(
      status({ account: { ...ACCOUNT_A, status: 'blocked' } }),
    )
    const link = mount()

    await link.bootstrap()

    expect(link.mode.value).toBe('blocked')
  })

  it('copies the link to the clipboard and reports failures', async () => {
    telegramApiMock.createTelegramLinkToken.mockResolvedValue(token())
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText },
      configurable: true,
    })
    const link = mount()
    await link.bootstrap()
    await link.startLinking()

    await link.copyLink()
    expect(writeText).toHaveBeenCalledWith(
      'https://t.me/quotify_bot?start=abc_DEF-123',
    )
    expect(link.isCopied.value).toBe(true)
    await advance(2500)
    expect(link.isCopied.value).toBe(false)

    writeText.mockRejectedValue(new Error('denied'))
    await link.copyLink()
    expect(link.errorMessage.value).toBe(
      'Không thể sao chép tự động. Hãy chọn đường dẫn và sao chép thủ công.',
    )
  })

  it.each([
    [429, 'Bạn thao tác quá nhanh. Vui lòng thử lại sau ít phút.'],
    [
      503,
      'Tính năng Telegram hiện chưa sẵn sàng. Vui lòng liên hệ quản trị viên.',
    ],
    [500, 'Hệ thống đang gặp sự cố. Vui lòng thử lại sau.'],
    [502, 'Hệ thống đang gặp sự cố. Vui lòng thử lại sau.'],
  ])('maps HTTP %i to a fixed Vietnamese message', async (code, message) => {
    telegramApiMock.createTelegramLinkToken.mockRejectedValue(
      new ApiError('Backend detail in English', code),
    )
    const link = mount()
    await link.bootstrap()

    await link.startLinking()

    expect(link.errorMessage.value).toBe(message)
    expect(link.errorMessage.value).not.toContain('Backend detail')
    expect(link.isPending.value).toBe(false)
  })

  it('uses a generic message for errors that are not API errors', async () => {
    telegramApiMock.createTelegramLinkToken.mockRejectedValue(
      new TypeError('boom'),
    )
    const link = mount()
    await link.bootstrap()

    await link.startLinking()

    expect(link.errorMessage.value).toBe(
      'Không thể thực hiện thao tác với Telegram. Vui lòng thử lại.',
    )
  })

  it('rejects a link token whose deep link is unsafe', async () => {
    telegramApiMock.createTelegramLinkToken.mockRejectedValue(
      new Error('Đường dẫn Telegram không hợp lệ.'),
    )
    const link = mount()
    await link.bootstrap()

    await link.startLinking()

    expect(link.deepLink.value).toBeNull()
    expect(link.errorMessage.value).toBe(
      'Không thể thực hiện thao tác với Telegram. Vui lòng thử lại.',
    )
  })

  it('never writes the deep link to web storage', async () => {
    telegramApiMock.createTelegramLinkToken.mockResolvedValue(token())
    const setItem = vi.spyOn(Storage.prototype, 'setItem')
    const link = mount()
    await link.bootstrap()

    await link.startLinking()

    expect(setItem).not.toHaveBeenCalled()
    setItem.mockRestore()
  })
})
