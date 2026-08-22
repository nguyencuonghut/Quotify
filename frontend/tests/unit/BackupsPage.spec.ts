import { mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import { defineComponent, ref } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useAuthStore } from '@/stores/auth.store'

const backupsPageMock = vi.hoisted(() => ({
  fetchBackupLogs: vi.fn(),
  fetchBackupSchedules: vi.fn(),
  triggerBackup: vi.fn(),
  saveSchedule: vi.fn(),
  removeSchedule: vi.fn(),
  downloadBackupFile: vi.fn(),
}))

const backupSchedules = ref<Record<string, unknown>[]>([])

vi.mock('@/composables/useBackupsPage', async () => {
  const actual = await vi.importActual<typeof import('@/composables/useBackupsPage')>(
    '@/composables/useBackupsPage',
  )
  return {
    ...actual,
    useBackupsPage: () => ({
      backupLogs: ref([]),
      totalBackupLogs: ref(0),
      backupSchedules,
      loadingLogs: ref(false),
      loadingSchedules: ref(false),
      isTriggering: ref(false),
      isSavingSchedule: ref(false),
      isDeletingSchedule: ref(false),
      generalError: ref(null),
      generalSuccess: ref(null),
      ...backupsPageMock,
    }),
  }
})

import BackupsPage from '@/pages/BackupsPage.vue'

const passthroughStub = defineComponent({
  template: '<div><slot /></div>',
})

let activeWrapper: VueWrapper | null = null

afterEach(() => {
  activeWrapper?.unmount()
  activeWrapper = null
})

beforeEach(() => {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }))
})

async function mountBackupsPage() {
  activeWrapper = mount(BackupsPage, {
    global: {
      plugins: [PrimeVue],
      stubs: {
        AdminLayout: passthroughStub,
        Button: false,
        Column: false,
        DataTable: false,
        Dialog: true,
        InputText: true,
        Select: true,
        Checkbox: true,
        Tag: true,
      },
    },
  })
  // Bảng lịch trình chỉ render khi tab "Lịch trình tự động" đang active
  // (mặc định tab đầu tiên là "logs").
  await activeWrapper.findAll('.backups-page__tab-btn')[1]!.trigger('click')
  return activeWrapper
}

function setPermissions(permissions: string[]) {
  const authStore = useAuthStore()
  authStore.currentUser = {
    id: 'admin-1',
    email: 'admin@quotify.local',
    status: 'active',
    roles: [],
    permissions,
    lastLoginAt: null,
  }
}

describe('BackupsPage schedule row action permissions', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    backupSchedules.value = [
      {
        id: 'sched-1',
        name: 'Sao lưu hàng ngày',
        frequency: 'daily',
        dayOfWeek: null,
        timeOfDay: '02:00:00',
        oneOffDatetime: null,
        isActive: true,
        nextRunAt: null,
        lastRunAt: null,
      },
    ]
  })

  it('disables the edit button with an explanatory title when the user lacks backups.write', async () => {
    setPermissions([])

    const wrapper = await mountBackupsPage()

    const editButton = wrapper.find('[data-testid="backups-page-edit-schedule"]')
    expect(editButton.exists()).toBe(true)
    expect(editButton.attributes('disabled')).toBeDefined()
    expect(editButton.attributes('title')).toBe(
      'Bạn không có quyền chỉnh sửa lịch trình sao lưu.',
    )
  })

  it('enables the edit button when the user has backups.write', async () => {
    setPermissions(['backups.write'])

    const wrapper = await mountBackupsPage()

    const editButton = wrapper.find('[data-testid="backups-page-edit-schedule"]')
    expect(editButton.attributes('disabled')).toBeUndefined()
    expect(editButton.attributes('title')).toBe('Chỉnh sửa')
  })

  it('disables the delete button with an explanatory title when the user lacks backups.write', async () => {
    setPermissions([])

    const wrapper = await mountBackupsPage()

    const deleteButton = wrapper.find('[data-testid="backups-page-delete-schedule"]')
    expect(deleteButton.exists()).toBe(true)
    expect(deleteButton.attributes('disabled')).toBeDefined()
    expect(deleteButton.attributes('title')).toBe(
      'Bạn không có quyền xóa lịch trình sao lưu.',
    )
  })

  it('enables the delete button when the user has backups.write', async () => {
    setPermissions(['backups.write'])

    const wrapper = await mountBackupsPage()

    const deleteButton = wrapper.find('[data-testid="backups-page-delete-schedule"]')
    expect(deleteButton.attributes('disabled')).toBeUndefined()
    expect(deleteButton.attributes('title')).toBe('Xóa')
  })
})
