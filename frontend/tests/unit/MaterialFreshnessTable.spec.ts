import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { computed, defineComponent, nextTick, ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import MaterialFreshnessTable from '@/components/dashboard/MaterialFreshnessTable.vue'
import { useAuthStore } from '@/stores/auth.store'
import type {
  MaterialFreshness,
  MaterialFreshnessItem,
} from '@/types/material-freshness'

const composableMock = vi.hoisted(() => ({ useMaterialFreshness: vi.fn() }))

vi.mock('@/composables/useMaterialFreshness', () => composableMock)

function item(
  overrides: Partial<MaterialFreshnessItem> = {},
): MaterialFreshnessItem {
  return {
    materialId: 'm-1',
    materialCode: 'NGO',
    materialName: 'Ngô hạt',
    materialTypeId: 't-1',
    materialTypeName: 'Nguyên liệu',
    isWatched: true,
    expectedIntervalDays: 7,
    updateCount: 3,
    supplierCount: 2,
    lastReceivedDate: '2026-10-06',
    ageDays: 1,
    status: 'updated',
    lastEntererId: 'u-1',
    lastEntererLabel: 'Nguyễn Văn A',
    ...overrides,
  }
}

const DATA: MaterialFreshness = {
  weekStart: '2026-10-05',
  weekEnd: '2026-10-11',
  asOfDate: '2026-10-07',
  summary: {
    watchedCount: 3,
    updatedCount: 1,
    onTimeCount: 0,
    overdueCount: 2,
    unwatchedUpdatedCount: 0,
  },
  items: [],
}

function state(overrides: Record<string, unknown> = {}) {
  const rows = ref<MaterialFreshnessItem[]>([
    item(),
    item({
      materialId: 'm-2',
      materialCode: 'LYS',
      materialName: 'Lysine 99%',
      materialTypeName: 'Vi lượng',
      updateCount: 0,
      supplierCount: 0,
      lastReceivedDate: '2026-09-20',
      ageDays: 17,
      expectedIntervalDays: 14,
      status: 'overdue',
      lastEntererId: null,
      lastEntererLabel: null,
    }),
  ])
  return {
    data: ref(DATA),
    rows,
    isLoading: ref(false),
    errorMessage: ref<string | null>(null),
    statusFilter: ref(null),
    typeFilter: ref(null),
    statusOptions: [
      { label: 'Quá hạn', value: 'overdue' },
      { label: 'Chưa có giá', value: 'never' },
      { label: 'Đúng hạn', value: 'on_time' },
      { label: 'Đã cập nhật', value: 'updated' },
    ],
    typeOptions: computed(() => [{ label: 'Nguyên liệu', value: 't-1' }]),
    hasActiveFilters: ref(false),
    isEmpty: ref(false),
    hasNoMatches: ref(false),
    summaryCards: computed(() => [
      {
        key: 'watched',
        label: 'Đang theo dõi',
        value: '3',
        detail: 'vật tư trong danh sách theo dõi',
        icon: 'pi pi-eye',
        tone: 'primary',
      },
      {
        key: 'overdue',
        label: 'Quá hạn',
        value: '2',
        detail: 'gồm cả vật tư chưa từng có giá',
        icon: 'pi pi-exclamation-triangle',
        tone: 'warn',
      },
    ]),
    load: vi.fn(),
    resetFilters: vi.fn(),
    ...overrides,
  }
}

const DataTableStub = defineComponent({
  props: { value: { type: Array, default: () => [] } },
  template: '<div data-testid="table-stub">{{ value.length }} dòng</div>',
})

function login(permissions: string[]) {
  const auth = useAuthStore()
  auth.accessToken = 'token-1'
  auth.currentUser = {
    id: 'user-1',
    email: 'user@example.com',
    status: 'active',
    roles: ['user'],
    permissions,
    lastLoginAt: null,
    fullName: 'Người dùng',
    avatarUrl: null,
  }
}

function mountTable(props: { weekStart: string | null; reloadToken: number }) {
  return mount(MaterialFreshnessTable, {
    props,
    global: {
      stubs: {
        Button: {
          template:
            '<button data-testid="reset-filters" @click="$emit(\'click\')" />',
        },
        Column: true,
        DataTable: DataTableStub,
        RouterLink: { template: '<a data-testid="settings-link"><slot /></a>' },
        Select: true,
        Tag: {
          props: ['value'],
          template: '<span class="tag-stub">{{ value }}</span>',
        },
      },
    },
  })
}

describe('MaterialFreshnessTable', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    login(['dashboard.read'])
    vi.clearAllMocks()
    composableMock.useMaterialFreshness.mockReturnValue(state())
  })

  it('loads the chosen week on mount and shows the summary and the rows', async () => {
    const mock = state()
    composableMock.useMaterialFreshness.mockReturnValue(mock)

    const wrapper = mountTable({ weekStart: '2026-10-05', reloadToken: 1 })
    await nextTick()

    expect(mock.load).toHaveBeenCalledTimes(1)
    expect(mock.load).toHaveBeenCalledWith('2026-10-05')
    expect(wrapper.text()).toContain('Độ mới của giá theo vật tư')
    expect(wrapper.text()).toContain('05/10/2026')
    expect(wrapper.text()).toContain('11/10/2026')
    expect(
      wrapper.get('[data-testid="material-freshness-card-watched"]').text(),
    ).toContain('3')
    expect(
      wrapper.get('[data-testid="material-freshness-card-overdue"]').text(),
    ).toContain('Quá hạn')
    expect(wrapper.get('[data-testid="table-stub"]').text()).toBe('2 dòng')
  })

  it('does not call the API before the page has started its first load', async () => {
    const mock = state()
    composableMock.useMaterialFreshness.mockReturnValue(mock)

    mountTable({ weekStart: null, reloadToken: 0 })
    await nextTick()

    expect(mock.load).not.toHaveBeenCalled()
  })

  it('reloads when the page reloads the week and when the applied week changes', async () => {
    const mock = state()
    composableMock.useMaterialFreshness.mockReturnValue(mock)
    const wrapper = mountTable({ weekStart: '2026-10-05', reloadToken: 1 })
    await nextTick()

    await wrapper.setProps({ reloadToken: 2 })
    expect(mock.load).toHaveBeenCalledTimes(2)
    expect(mock.load).toHaveBeenLastCalledWith('2026-10-05')

    await wrapper.setProps({ weekStart: '2026-09-28', reloadToken: 3 })
    expect(mock.load).toHaveBeenCalledTimes(3)
    expect(mock.load).toHaveBeenLastCalledWith('2026-09-28')
  })

  it('shows each material as a card with its status, age, interval and last enterer', () => {
    const wrapper = mountTable({ weekStart: '2026-10-05', reloadToken: 1 })

    const cards = wrapper.findAll(
      '[data-testid="material-freshness-mobile-item"]',
    )
    expect(cards).toHaveLength(2)
    expect(cards[0].text()).toContain('Ngô hạt')
    expect(cards[0].text()).toContain('Đã cập nhật')
    expect(cards[0].text()).toContain('Nguyễn Văn A')
    expect(cards[0].text()).toContain('06/10/2026')
    expect(cards[1].text()).toContain('Lysine 99%')
    expect(cards[1].text()).toContain('Quá hạn')
    expect(cards[1].text()).toContain('17 ngày')
    expect(cards[1].text()).toContain('14 ngày')
    expect(cards[1].text()).toContain('—')
  })

  it('explains that the table counts by the date the quote was received', () => {
    const wrapper = mountTable({ weekStart: '2026-10-05', reloadToken: 1 })

    expect(wrapper.text()).toContain('Tính theo ngày nhận báo giá')
  })

  it('shows the settings link only to people who can manage price alerts', () => {
    expect(
      mountTable({ weekStart: null, reloadToken: 1 })
        .find('[data-testid="settings-link"]')
        .exists(),
    ).toBe(false)

    login(['dashboard.read', 'price_alerts.manage'])
    expect(
      mountTable({ weekStart: null, reloadToken: 1 })
        .find('[data-testid="settings-link"]')
        .exists(),
    ).toBe(true)
  })

  it('shows a fixed error message instead of the table when loading fails', () => {
    composableMock.useMaterialFreshness.mockReturnValue(
      state({
        data: ref(null),
        rows: ref([]),
        errorMessage: ref('Không thể tải độ mới của giá theo vật tư.'),
      }),
    )

    const wrapper = mountTable({ weekStart: null, reloadToken: 1 })

    const alert = wrapper.get('[data-testid="material-freshness-error"]')
    expect(alert.attributes('role')).toBe('alert')
    expect(alert.text()).toBe('Không thể tải độ mới của giá theo vật tư.')
    expect(wrapper.find('[data-testid="table-stub"]').exists()).toBe(false)
  })

  it('shows an empty state when the week has nothing to show', () => {
    composableMock.useMaterialFreshness.mockReturnValue(
      state({ rows: ref([]), isEmpty: ref(true) }),
    )

    const wrapper = mountTable({ weekStart: null, reloadToken: 1 })

    expect(
      wrapper.get('[data-testid="material-freshness-empty"]').text(),
    ).toContain('Chưa có vật tư nào để hiển thị trong tuần này')
  })

  it('offers to clear the filters when none of the materials match', async () => {
    const mock = state({
      rows: ref([]),
      hasNoMatches: ref(true),
      hasActiveFilters: ref(true),
    })
    composableMock.useMaterialFreshness.mockReturnValue(mock)

    const wrapper = mountTable({ weekStart: null, reloadToken: 1 })

    expect(
      wrapper.get('[data-testid="material-freshness-no-match"]').text(),
    ).toContain('Không có vật tư nào khớp bộ lọc')
    await wrapper.get('[data-testid="reset-filters"]').trigger('click')
    expect(mock.resetFilters).toHaveBeenCalled()
  })

  it('tells the user it is refreshing while keeping the previous week visible', () => {
    composableMock.useMaterialFreshness.mockReturnValue(
      state({ isLoading: ref(true), isEmpty: ref(true) }),
    )

    const wrapper = mountTable({ weekStart: '2026-10-05', reloadToken: 1 })

    const status = wrapper.get('[data-testid="material-freshness-loading"]')
    expect(status.attributes('role')).toBe('status')
    expect(wrapper.attributes('aria-busy')).toBe('true')
    expect(
      wrapper.get('[data-testid="material-freshness-card-watched"]').exists(),
    ).toBe(true)
    // Đang tải thì không hiện trạng thái "trống" suy ra từ dữ liệu của tuần trước.
    expect(
      wrapper.find('[data-testid="material-freshness-empty"]').exists(),
    ).toBe(false)
  })

  it('does not claim to be busy when nothing is loading', () => {
    const wrapper = mountTable({ weekStart: '2026-10-05', reloadToken: 1 })

    expect(wrapper.attributes('aria-busy')).toBe('false')
    expect(
      wrapper.find('[data-testid="material-freshness-loading"]').exists(),
    ).toBe(false)
  })
})
