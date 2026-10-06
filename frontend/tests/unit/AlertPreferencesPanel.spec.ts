import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AlertPreferencesPanel from '@/components/profile/AlertPreferencesPanel.vue'

const composableMock = vi.hoisted(() => ({ useAlertPreferences: vi.fn() }))

vi.mock('@/composables/useAlertPreferences', () => composableMock)

function state(overrides: Record<string, unknown> = {}) {
  return {
    isEnabled: ref(true),
    minLevelChoice: ref('default'),
    adminReceiveAll: ref(false),
    effectiveMinLevel: ref('medium'),
    isLoaded: ref(true),
    isLoading: ref(false),
    isSaving: ref(false),
    loadError: ref(null),
    errorMessage: ref(null),
    successMessage: ref(null),
    isAdmin: ref(false),
    defaultOptionLabel: ref('Mặc định theo vai trò (hiện là Trung bình)'),
    load: vi.fn(),
    save: vi.fn(),
    ...overrides,
  }
}

function mountPanel() {
  return mount(AlertPreferencesPanel, {
    global: { stubs: { Select: true } },
  })
}

describe('AlertPreferencesPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    composableMock.useAlertPreferences.mockReturnValue(state())
  })

  it('loads on mount and explains what the level does and what always gets through', () => {
    const mocked = state()
    composableMock.useAlertPreferences.mockReturnValue(mocked)

    const wrapper = mountPanel()

    expect(mocked.load).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('Tùy chọn thông báo giá')
    expect(wrapper.text()).toContain('mức tối thiểu không áp dụng')
    expect(wrapper.text()).toContain('là người nhập phiếu')
    expect(wrapper.text()).toContain('bản tin tổng hợp hằng ngày')
  })

  it('toggles the personal switch through the composable state', async () => {
    const mocked = state()
    composableMock.useAlertPreferences.mockReturnValue(mocked)

    const wrapper = mountPanel()
    await wrapper
      .get('[data-testid="alert-preferences-enabled"]')
      .setValue(false)

    expect(mocked.isEnabled.value).toBe(false)
  })

  it('saves from the form', async () => {
    const mocked = state()
    composableMock.useAlertPreferences.mockReturnValue(mocked)

    const wrapper = mountPanel()
    await wrapper
      .get('[data-testid="alert-preferences-form"]')
      .trigger('submit')

    expect(mocked.save).toHaveBeenCalledTimes(1)
  })

  it('shows the admin option only for an admin, with the note about the system account', () => {
    expect(
      mountPanel().find('[data-testid="alert-preferences-admin-all"]').exists(),
    ).toBe(false)

    composableMock.useAlertPreferences.mockReturnValue(
      state({ isAdmin: ref(true) }),
    )
    const wrapper = mountPanel()

    expect(
      wrapper.find('[data-testid="alert-preferences-admin-all"]').exists(),
    ).toBe(true)
    expect(wrapper.text()).toContain('không bao giờ nhận thông báo')
  })

  it('shows save results as status or alert messages', () => {
    composableMock.useAlertPreferences.mockReturnValue(
      state({
        successMessage: ref('Đã lưu tùy chọn thông báo.'),
        errorMessage: ref('Không thể lưu tùy chọn. Vui lòng thử lại.'),
      }),
    )

    const wrapper = mountPanel()

    expect(
      wrapper
        .get('[data-testid="alert-preferences-success"]')
        .attributes('role'),
    ).toBe('status')
    expect(
      wrapper.get('[data-testid="alert-preferences-error"]').attributes('role'),
    ).toBe('alert')
  })

  it('disables saving until loaded and while saving', () => {
    composableMock.useAlertPreferences.mockReturnValue(
      state({ isLoaded: ref(false) }),
    )
    expect(
      mountPanel()
        .get('[data-testid="alert-preferences-save"]')
        .attributes('disabled'),
    ).toBeDefined()

    composableMock.useAlertPreferences.mockReturnValue(
      state({ isSaving: ref(true) }),
    )
    expect(
      mountPanel()
        .get('[data-testid="alert-preferences-save"]')
        .attributes('disabled'),
    ).toBeDefined()
  })

  it('does not let the retry button fire again while a load is running', () => {
    composableMock.useAlertPreferences.mockReturnValue(
      state({
        loadError: ref('Không thể tải tùy chọn thông báo.'),
        isLoading: ref(true),
      }),
    )

    const wrapper = mountPanel()

    expect(
      wrapper
        .get('[data-testid="alert-preferences-retry"]')
        .attributes('disabled'),
    ).toBeDefined()
  })

  it('offers a retry instead of the form when loading failed', async () => {
    const mocked = state({
      loadError: ref('Không thể tải tùy chọn thông báo.'),
      isLoaded: ref(false),
    })
    composableMock.useAlertPreferences.mockReturnValue(mocked)

    const wrapper = mountPanel()
    await wrapper
      .get('[data-testid="alert-preferences-retry"]')
      .trigger('click')

    expect(
      wrapper.find('[data-testid="alert-preferences-form"]').exists(),
    ).toBe(false)
    expect(
      wrapper
        .get('[data-testid="alert-preferences-load-error"]')
        .attributes('role'),
    ).toBe('alert')
    expect(mocked.load).toHaveBeenCalledTimes(2)
  })
})
