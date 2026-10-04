import { computed, getCurrentScope, onScopeDispose, ref } from 'vue'

import { ApiError } from '@/api/http'
import {
  cancelTelegramLinkRequest,
  createTelegramLinkToken,
  getTelegramLinkStatus,
  unlinkTelegram,
} from '@/api/telegram.api'
import { useAuthStore } from '@/stores/auth.store'
import type { TelegramAccount, TelegramLinkStatus } from '@/types/telegram'

export type TelegramLinkMode =
  | 'loading'
  | 'error'
  | 'unlinked'
  | 'pending'
  | 'linked'
  | 'blocked'

const POLL_INTERVAL_MS = 3000
const COUNTDOWN_INTERVAL_MS = 1000
const COPIED_RESET_MS = 2000

const MESSAGES = {
  rateLimited: 'Bạn thao tác quá nhanh. Vui lòng thử lại sau ít phút.',
  unavailable:
    'Tính năng Telegram hiện chưa sẵn sàng. Vui lòng liên hệ quản trị viên.',
  serverError: 'Hệ thống đang gặp sự cố. Vui lòng thử lại sau.',
  generic: 'Không thể thực hiện thao tác với Telegram. Vui lòng thử lại.',
  copyFailed:
    'Không thể sao chép tự động. Hãy chọn đường dẫn và sao chép thủ công.',
  linked: 'Đã liên kết tài khoản Telegram.',
  unlinked: 'Đã hủy liên kết Telegram.',
  expired:
    'Đường dẫn liên kết đã hết hạn hoặc bị thay thế. Hãy tạo đường dẫn mới.',
  superseded:
    'Đường dẫn trong tab này đã bị thay thế bởi đường dẫn mới hơn. Hãy tạo đường dẫn mới.',
} as const

/** Lỗi map theo mã trạng thái sang câu cố định; không bao giờ hiển thị `detail` của backend. */
function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 429) return MESSAGES.rateLimited
    if (error.status === 503) return MESSAGES.unavailable
    if (error.status >= 500) return MESSAGES.serverError
  }
  return MESSAGES.generic
}

interface UseTelegramLinkOptions {
  /** Đồng hồ đơn điệu (ms). Mặc định `performance.now()`, tiêm vào khi test. */
  now?: () => number
}

export function useTelegramLink(options: UseTelegramLinkOptions = {}) {
  const authStore = useAuthStore()
  const now = options.now ?? (() => performance.now())

  const isLoaded = ref(false)
  const loadFailed = ref(false)
  const enabled = ref(false)
  const botUsername = ref<string | null>(null)
  const account = ref<TelegramAccount | null>(null)
  // Phần "đang chờ" độc lập với `account`: khi đổi tài khoản, cả hai cùng có giá trị.
  const pendingSeconds = ref<number | null>(null)
  const pendingReceivedAt = ref(0)
  const clockTick = ref(now())
  // Chỉ giữ trong bộ nhớ, tuyệt đối không ghi vào localStorage hay sessionStorage.
  const deepLink = ref<string | null>(null)

  const isBusy = ref(false)
  const isCopied = ref(false)
  const isUnlinkDialogVisible = ref(false)
  const errorMessage = ref<string | null>(null)
  const successMessage = ref<string | null>(null)
  const infoMessage = ref<string | null>(null)

  let pollTimer: ReturnType<typeof setInterval> | null = null
  let countdownTimer: ReturnType<typeof setInterval> | null = null
  let copiedTimer: ReturnType<typeof setTimeout> | null = null
  // Hạn của mã mà `deepLink` đang giữ; so với hạn server báo để biết mã đã bị tab khác thay chưa.
  let deepLinkExpiresAt: number | null = null
  let inFlight: Promise<void> | null = null
  let listening = false
  // Tăng mỗi khi hành động của người dùng đổi trạng thái; phản hồi của request đã gửi trước đó là cũ.
  let stateVersion = 0

  const isPending = computed(() => pendingSeconds.value !== null)
  const isSwitching = computed(() => account.value !== null && isPending.value)
  const isVisible = computed(
    () => (isLoaded.value && enabled.value) || loadFailed.value,
  )
  const remainingSeconds = computed(() => {
    if (pendingSeconds.value === null) return 0
    const elapsed = Math.floor(
      (clockTick.value - pendingReceivedAt.value) / 1000,
    )
    return Math.max(0, pendingSeconds.value - elapsed)
  })
  const remainingLabel = computed(() => {
    const minutes = Math.floor(remainingSeconds.value / 60)
    const seconds = remainingSeconds.value % 60
    return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
  })
  const isExpired = computed(
    () => isPending.value && remainingSeconds.value === 0,
  )
  const mode = computed<TelegramLinkMode>(() => {
    if (!isLoaded.value) return loadFailed.value ? 'error' : 'loading'
    if (account.value)
      return account.value.status === 'blocked' ? 'blocked' : 'linked'
    return isPending.value ? 'pending' : 'unlinked'
  })

  function setPending(seconds: number) {
    pendingSeconds.value = seconds
    pendingReceivedAt.value = now()
    clockTick.value = pendingReceivedAt.value
  }

  function clearDeepLink() {
    deepLink.value = null
    deepLinkExpiresAt = null
  }

  function clearPending() {
    pendingSeconds.value = null
    clearDeepLink()
  }

  function clearMessages() {
    errorMessage.value = null
    successMessage.value = null
    infoMessage.value = null
  }

  function stopTimers() {
    if (pollTimer !== null) clearInterval(pollTimer)
    if (countdownTimer !== null) clearInterval(countdownTimer)
    pollTimer = null
    countdownTimer = null
  }

  /** Bật poll và đếm ngược khi đang chờ, tắt khi không còn chờ. */
  function syncTimers() {
    if (!isPending.value) {
      stopTimers()
      return
    }
    if (countdownTimer === null) {
      countdownTimer = setInterval(() => {
        clockTick.value = now()
      }, COUNTDOWN_INTERVAL_MS)
    }
    if (pollTimer === null) {
      pollTimer = setInterval(() => {
        if (!document.hidden) void refresh()
      }, POLL_INTERVAL_MS)
    }
  }

  function applyStatus(status: TelegramLinkStatus) {
    const previousLinkedAt = account.value?.linkedAt ?? null
    const wasLoaded = isLoaded.value
    const wasPending = isPending.value

    enabled.value = status.enabled
    botUsername.value = status.botUsername
    account.value = status.account
    if (status.pending) {
      setPending(status.pending.expiresInSeconds)
      if (
        deepLink.value !== null &&
        deepLinkExpiresAt !== Date.parse(status.pending.expiresAt)
      ) {
        // Server đang giữ mã khác với mã trong tab này: mã của ta đã bị thay thế.
        clearDeepLink()
        infoMessage.value = MESSAGES.superseded
      }
    } else {
      clearPending()
    }
    isLoaded.value = true
    loadFailed.value = false

    const linkedAt = status.account?.linkedAt ?? null
    if (wasLoaded && linkedAt !== null && linkedAt !== previousLinkedAt) {
      successMessage.value = MESSAGES.linked
      infoMessage.value = null
    } else if (wasPending && !status.pending) {
      infoMessage.value = MESSAGES.expired
    }
    syncTimers()
  }

  function refresh(): Promise<void> {
    // Chống request chồng: poll, focus và tab hiện lại dùng chung một yêu cầu đang bay.
    if (inFlight) return inFlight
    const requestedAtVersion = stateVersion
    inFlight = (async () => {
      try {
        const status = await getTelegramLinkStatus(authStore.accessToken)
        // Người dùng vừa tạo, hủy hay bỏ liên kết trong lúc chờ: phản hồi này đã cũ, bỏ qua.
        if (requestedAtVersion === stateVersion) applyStatus(status)
      } catch (error) {
        // Poll nền thất bại thì im lặng, chỉ báo lỗi khi chưa có dữ liệu nào.
        if (!isLoaded.value) {
          loadFailed.value = true
          errorMessage.value = describeError(error)
        }
      } finally {
        inFlight = null
      }
    })()
    return inFlight
  }

  function handleVisibilityChange() {
    if (!document.hidden && isLoaded.value) void refresh()
  }

  function handleFocus() {
    if (isLoaded.value) void refresh()
  }

  function addListeners() {
    if (listening) return
    listening = true
    document.addEventListener('visibilitychange', handleVisibilityChange)
    window.addEventListener('focus', handleFocus)
  }

  async function bootstrap() {
    addListeners()
    await refresh()
  }

  async function reload() {
    errorMessage.value = null
    loadFailed.value = false
    await refresh()
  }

  async function runAction(action: () => Promise<void>) {
    if (isBusy.value) return
    isBusy.value = true
    clearMessages()
    try {
      await action()
    } catch (error) {
      errorMessage.value = describeError(error)
    } finally {
      isBusy.value = false
    }
  }

  function startLinking() {
    return runAction(async () => {
      const issued = await createTelegramLinkToken(authStore.accessToken)
      stateVersion += 1
      deepLink.value = issued.deepLink
      deepLinkExpiresAt = Date.parse(issued.expiresAt)
      setPending(issued.expiresInSeconds)
      syncTimers()
    })
  }

  function cancelPending() {
    return runAction(async () => {
      await cancelTelegramLinkRequest(authStore.accessToken)
      stateVersion += 1
      clearPending()
      syncTimers()
    })
  }

  function openUnlinkDialog() {
    isUnlinkDialogVisible.value = true
  }

  function closeUnlinkDialog() {
    isUnlinkDialogVisible.value = false
  }

  async function confirmUnlink() {
    await runAction(async () => {
      await unlinkTelegram(authStore.accessToken)
      stateVersion += 1
      account.value = null
      successMessage.value = MESSAGES.unlinked
    })
    isUnlinkDialogVisible.value = false
  }

  async function copyLink() {
    if (!deepLink.value) return
    try {
      await navigator.clipboard.writeText(deepLink.value)
    } catch {
      errorMessage.value = MESSAGES.copyFailed
      return
    }
    isCopied.value = true
    if (copiedTimer !== null) clearTimeout(copiedTimer)
    copiedTimer = setTimeout(() => {
      isCopied.value = false
      copiedTimer = null
    }, COPIED_RESET_MS)
  }

  function dispose() {
    stopTimers()
    if (copiedTimer !== null) clearTimeout(copiedTimer)
    copiedTimer = null
    if (listening) {
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      window.removeEventListener('focus', handleFocus)
      listening = false
    }
  }

  if (getCurrentScope()) onScopeDispose(dispose)

  return {
    account,
    botUsername,
    bootstrap,
    cancelPending,
    closeUnlinkDialog,
    confirmUnlink,
    copyLink,
    deepLink,
    dispose,
    enabled,
    errorMessage,
    infoMessage,
    isBusy,
    isCopied,
    isExpired,
    isPending,
    isSwitching,
    isUnlinkDialogVisible,
    isVisible,
    mode,
    openUnlinkDialog,
    reload,
    remainingLabel,
    remainingSeconds,
    startLinking,
    successMessage,
  }
}
