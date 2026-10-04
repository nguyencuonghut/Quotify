import { mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ref, type Ref } from 'vue'

import type { TelegramAccount } from '@/types/telegram'
import type { TelegramLinkMode } from '@/composables/useTelegramLink'

const DEEP_LINK = 'https://t.me/quotify_bot?start=abc_DEF-123'

const ACCOUNT: TelegramAccount = {
  status: 'active',
  username: 'an_nguyen',
  firstName: 'An',
  linkedAt: '2026-10-01T03:00:00Z',
}

interface TelegramState {
  account: Ref<TelegramAccount | null>
  bootstrap: ReturnType<typeof vi.fn>
  cancelPending: ReturnType<typeof vi.fn>
  closeUnlinkDialog: ReturnType<typeof vi.fn>
  confirmUnlink: ReturnType<typeof vi.fn>
  copyLink: ReturnType<typeof vi.fn>
  deepLink: Ref<string | null>
  errorMessage: Ref<string | null>
  infoMessage: Ref<string | null>
  isBusy: Ref<boolean>
  isCopied: Ref<boolean>
  isExpired: Ref<boolean>
  isPending: Ref<boolean>
  isSwitching: Ref<boolean>
  isUnlinkDialogVisible: Ref<boolean>
  isVisible: Ref<boolean>
  mode: Ref<TelegramLinkMode>
  openUnlinkDialog: ReturnType<typeof vi.fn>
  reload: ReturnType<typeof vi.fn>
  remainingLabel: Ref<string>
  startLinking: ReturnType<typeof vi.fn>
  successMessage: Ref<string | null>
}

const holder = vi.hoisted(() => ({
  telegram: null as unknown,
  qr: null as unknown,
}))

vi.mock('@/composables/useTelegramLink', () => ({
  useTelegramLink: () => holder.telegram,
}))

vi.mock('@/composables/useQrCode', () => ({
  useQrCode: () => ({ qr: holder.qr }),
}))

vi.mock('@/composables/useProfilePage', () => ({
  useProfilePage: () => ({
    avatarError: ref(null),
    avatarSuccess: ref(null),
    confirmPassword: ref(''),
    confirmPasswordProps: ref({}),
    currentPassword: ref(''),
    currentPasswordProps: ref({}),
    currentUser: ref({ fullName: 'Nguyễn Văn An', email: 'an@example.com' }),
    errors: ref({}),
    formatDateTime: (value: string | null) => `ngày(${value})`,
    handleAvatarUpload: vi.fn(),
    isAvatarUploading: ref(false),
    isPasswordSubmitting: ref(false),
    newPassword: ref(''),
    newPasswordProps: ref({}),
    passwordError: ref(null),
    passwordSuccess: ref(null),
    permissionsDisplay: ref('3 quyền đã được cấp'),
    profileAvatarUrl: ref('/avatar.png'),
    rolesDisplay: ref('Trưởng phòng'),
    submitPasswordChange: vi.fn(),
  }),
}))

import ProfilePage from '@/pages/ProfilePage.vue'

const passthroughStub = { template: '<div><slot /></div>' }
const dialogStub = {
  props: { visible: Boolean, header: String },
  template:
    '<div v-if="visible" data-testid="dialog"><h4>{{ header }}</h4><slot /><slot name="footer" /></div>',
}

function makeTelegram(overrides: Partial<TelegramState> = {}): TelegramState {
  return {
    account: ref(null),
    bootstrap: vi.fn().mockResolvedValue(undefined),
    cancelPending: vi.fn(),
    closeUnlinkDialog: vi.fn(),
    confirmUnlink: vi.fn(),
    copyLink: vi.fn(),
    deepLink: ref(null),
    errorMessage: ref(null),
    infoMessage: ref(null),
    isBusy: ref(false),
    isCopied: ref(false),
    isExpired: ref(false),
    isPending: ref(false),
    isSwitching: ref(false),
    isUnlinkDialogVisible: ref(false),
    isVisible: ref(true),
    mode: ref<TelegramLinkMode>('unlinked'),
    openUnlinkDialog: vi.fn(),
    reload: vi.fn(),
    remainingLabel: ref('09:30'),
    startLinking: vi.fn(),
    successMessage: ref(null),
    ...overrides,
  }
}

let wrapper: VueWrapper | null = null

function mountPage(
  telegram: TelegramState,
  qr: { path: string; size: number } | null = null,
) {
  holder.telegram = telegram
  holder.qr = ref(qr)
  wrapper = mount(ProfilePage, {
    global: {
      stubs: {
        AdminLayout: passthroughStub,
        Dialog: dialogStub,
        FileUpload: true,
      },
    },
  })
  return wrapper
}

function byTestId(testId: string) {
  return wrapper!.find(`[data-testid="${testId}"]`)
}

describe('ProfilePage Telegram panel', () => {
  beforeEach(() => {
    holder.telegram = null
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
  })

  it('offers to link Telegram when nothing is linked and starts linking on click', async () => {
    const telegram = makeTelegram()
    mountPage(telegram)

    const button = byTestId('profile-telegram-link-button')
    expect(button.exists()).toBe(true)
    expect(button.text()).toContain('Liên kết Telegram')
    await button.trigger('click')

    expect(telegram.startLinking).toHaveBeenCalledTimes(1)
    expect(telegram.bootstrap).toHaveBeenCalledTimes(1)
  })

  it('does not render the panel when the feature is off, but keeps the other panels', () => {
    mountPage(makeTelegram({ isVisible: ref(false) }))

    expect(byTestId('profile-telegram-panel').exists()).toBe(false)
    expect(wrapper!.text()).toContain('Ảnh đại diện')
    expect(wrapper!.text()).toContain('Đổi mật khẩu')
    expect(wrapper!.text()).not.toContain('Thông báo Telegram')
  })

  it('shows the pending link with a safe href, a countdown and a cancel button', async () => {
    const telegram = makeTelegram({
      isPending: ref(true),
      deepLink: ref(DEEP_LINK),
      mode: ref<TelegramLinkMode>('pending'),
    })
    mountPage(telegram)

    const open = byTestId('profile-telegram-open-link')
    expect(open.attributes('href')).toBe(DEEP_LINK)
    expect(open.attributes('target')).toBe('_blank')
    expect(open.attributes('rel')).toBe('noopener noreferrer')
    expect(byTestId('profile-telegram-countdown').text()).toContain('09:30')
    expect(byTestId('profile-telegram-link-input').element).toHaveProperty(
      'value',
      DEEP_LINK,
    )

    await byTestId('profile-telegram-copy-button').trigger('click')
    await byTestId('profile-telegram-cancel-button').trigger('click')

    expect(telegram.copyLink).toHaveBeenCalledTimes(1)
    expect(telegram.cancelPending).toHaveBeenCalledTimes(1)
    expect(byTestId('profile-telegram-cancel-button').text()).toContain(
      'Hủy yêu cầu',
    )
  })

  it('explains how to get the link back when it is pending but no longer in memory', () => {
    mountPage(
      makeTelegram({
        isPending: ref(true),
        deepLink: ref(null),
        mode: ref<TelegramLinkMode>('pending'),
      }),
    )

    expect(byTestId('profile-telegram-open-link').exists()).toBe(false)
    expect(byTestId('profile-telegram-lost-link').text()).toContain(
      'Tạo đường dẫn mới để lấy lại đường dẫn',
    )
    expect(byTestId('profile-telegram-new-link-button').text()).toContain(
      'Tạo đường dẫn mới',
    )
  })

  it('shows the account and the pending block together while switching', () => {
    mountPage(
      makeTelegram({
        account: ref(ACCOUNT),
        isPending: ref(true),
        isSwitching: ref(true),
        deepLink: ref(DEEP_LINK),
        mode: ref<TelegramLinkMode>('linked'),
      }),
    )

    expect(byTestId('profile-telegram-account').text()).toContain('@an_nguyen')
    expect(byTestId('profile-telegram-account').text()).toContain(
      'ngày(2026-10-01T03:00:00Z)',
    )
    expect(byTestId('profile-telegram-pending').exists()).toBe(true)
    expect(byTestId('profile-telegram-link-button').exists()).toBe(false)
  })

  it('labels the primary button "Đổi tài khoản Telegram" when already linked', () => {
    mountPage(
      makeTelegram({
        account: ref(ACCOUNT),
        mode: ref<TelegramLinkMode>('linked'),
      }),
    )

    expect(byTestId('profile-telegram-link-button').text()).toContain(
      'Đổi tài khoản Telegram',
    )
    expect(byTestId('profile-telegram-unlink-button').text()).toContain(
      'Hủy liên kết',
    )
  })

  it('tells a blocked user how to receive notifications again', () => {
    mountPage(
      makeTelegram({
        account: ref({ ...ACCOUNT, status: 'blocked' }),
        mode: ref<TelegramLinkMode>('blocked'),
      }),
    )

    expect(byTestId('profile-telegram-blocked-hint').text()).toContain('/start')
  })

  it('falls back to the first name when the account has no username', () => {
    mountPage(
      makeTelegram({
        account: ref({ ...ACCOUNT, username: null }),
        mode: ref<TelegramLinkMode>('linked'),
      }),
    )

    const text = byTestId('profile-telegram-account').text()
    expect(text).toContain('An')
    expect(text).not.toContain('@')
  })

  it('exposes errors as alerts and successes or notices as status messages', () => {
    mountPage(
      makeTelegram({
        errorMessage: ref('Lỗi thử nghiệm'),
        successMessage: ref('Đã liên kết tài khoản Telegram.'),
        infoMessage: ref('Đường dẫn đã hết hạn.'),
      }),
    )

    expect(byTestId('profile-telegram-error').attributes('role')).toBe('alert')
    expect(byTestId('profile-telegram-success').attributes('role')).toBe(
      'status',
    )
    expect(byTestId('profile-telegram-info').attributes('role')).toBe('status')
  })

  it('confirms unlinking through the dialog footer', async () => {
    const telegram = makeTelegram({
      account: ref(ACCOUNT),
      isUnlinkDialogVisible: ref(true),
      mode: ref<TelegramLinkMode>('linked'),
    })
    mountPage(telegram)

    expect(byTestId('dialog').exists()).toBe(true)
    await byTestId('profile-telegram-confirm-unlink').trigger('click')

    expect(telegram.confirmUnlink).toHaveBeenCalledTimes(1)
  })

  it('opens the confirmation dialog instead of unlinking straight away', async () => {
    const telegram = makeTelegram({
      account: ref(ACCOUNT),
      mode: ref<TelegramLinkMode>('linked'),
    })
    mountPage(telegram)

    await byTestId('profile-telegram-unlink-button').trigger('click')

    expect(telegram.openUnlinkDialog).toHaveBeenCalledTimes(1)
    expect(telegram.confirmUnlink).not.toHaveBeenCalled()
  })

  it('offers a retry when the first load failed', async () => {
    const telegram = makeTelegram({
      mode: ref<TelegramLinkMode>('error'),
      errorMessage: ref('Hệ thống đang gặp sự cố. Vui lòng thử lại sau.'),
    })
    mountPage(telegram)

    await byTestId('profile-telegram-retry-button').trigger('click')

    expect(telegram.reload).toHaveBeenCalledTimes(1)
    expect(byTestId('profile-telegram-link-button').exists()).toBe(false)
  })

  it('disables the actions with an explanation while a request is running', () => {
    mountPage(makeTelegram({ isBusy: ref(true) }))

    const button = byTestId('profile-telegram-link-button')
    expect(button.attributes('disabled')).toBeDefined()
    expect(button.attributes('title')).toBe('Đang xử lý, vui lòng đợi.')
  })

  it('says so when the link has expired locally', () => {
    mountPage(
      makeTelegram({
        isPending: ref(true),
        isExpired: ref(true),
        deepLink: ref(DEEP_LINK),
        mode: ref<TelegramLinkMode>('pending'),
      }),
    )

    expect(byTestId('profile-telegram-countdown').text()).toContain(
      'đã hết hạn',
    )
    expect(byTestId('profile-telegram-open-link').exists()).toBe(false)
  })

  it('shows a QR code of the pending link when one is available', () => {
    mountPage(
      makeTelegram({
        isPending: ref(true),
        deepLink: ref(DEEP_LINK),
        mode: ref<TelegramLinkMode>('pending'),
      }),
      { path: 'M4 4h1v1h-1z', size: 13 },
    )

    const svg = byTestId('profile-telegram-qr')
    expect(svg.exists()).toBe(true)
    expect(svg.attributes('role')).toBe('img')
    expect(svg.attributes('aria-label')).toContain('Mã QR')
    expect(svg.attributes('viewBox')).toBe('0 0 13 13')
    expect(svg.find('path').attributes('d')).toBe('M4 4h1v1h-1z')
  })

  it('works without a QR code', () => {
    mountPage(
      makeTelegram({
        isPending: ref(true),
        deepLink: ref(DEEP_LINK),
        mode: ref<TelegramLinkMode>('pending'),
      }),
      null,
    )

    expect(byTestId('profile-telegram-qr').exists()).toBe(false)
    expect(byTestId('profile-telegram-open-link').exists()).toBe(true)
  })

  it('never shows a QR code for an expired link', () => {
    mountPage(
      makeTelegram({
        isPending: ref(true),
        isExpired: ref(true),
        deepLink: ref(DEEP_LINK),
        mode: ref<TelegramLinkMode>('pending'),
      }),
      { path: 'M4 4h1v1h-1z', size: 13 },
    )

    expect(byTestId('profile-telegram-qr').exists()).toBe(false)
  })
})
