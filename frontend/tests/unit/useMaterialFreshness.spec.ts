import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useMaterialFreshness } from '@/composables/useMaterialFreshness'
import { useAuthStore } from '@/stores/auth.store'
import type {
  MaterialFreshness,
  MaterialFreshnessItem,
} from '@/types/material-freshness'

const apiMock = vi.hoisted(() => ({
  getMaterialFreshness: vi.fn(),
}))

vi.mock('@/api/material-freshness.api', () => apiMock)

function item(
  overrides: Partial<MaterialFreshnessItem> = {},
): MaterialFreshnessItem {
  return {
    materialId: 'm-1',
    materialCode: 'M1',
    materialName: 'Vật tư 1',
    materialTypeId: 't-1',
    materialTypeName: 'Nguyên liệu',
    isWatched: true,
    expectedIntervalDays: 7,
    updateCount: 0,
    supplierCount: 0,
    lastReceivedDate: '2026-10-01',
    ageDays: 6,
    status: 'on_time',
    lastEntererId: null,
    lastEntererLabel: null,
    ...overrides,
  }
}

function freshness(
  items: MaterialFreshnessItem[],
  overrides: Partial<MaterialFreshness> = {},
): MaterialFreshness {
  return {
    weekStart: '2026-10-05',
    weekEnd: '2026-10-11',
    asOfDate: '2026-10-07',
    summary: {
      watchedCount: 4,
      updatedCount: 1,
      onTimeCount: 1,
      overdueCount: 2,
      unwatchedUpdatedCount: 3,
    },
    items,
    ...overrides,
  }
}

describe('useMaterialFreshness', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useAuthStore().accessToken = 'token-1'
    vi.clearAllMocks()
    apiMock.getMaterialFreshness.mockResolvedValue(freshness([item()]))
  })

  it('loads the table for the chosen week with the access token', async () => {
    const table = useMaterialFreshness()

    await table.load('2026-10-05')

    expect(apiMock.getMaterialFreshness).toHaveBeenCalledWith(
      '2026-10-05',
      'token-1',
    )
    expect(table.data.value?.weekStart).toBe('2026-10-05')
    expect(table.rows.value).toHaveLength(1)
    expect(table.isLoading.value).toBe(false)
    expect(table.errorMessage.value).toBeNull()
  })

  it('shows a fixed message and drops the old table when loading fails', async () => {
    const table = useMaterialFreshness()
    await table.load('2026-10-05')
    apiMock.getMaterialFreshness.mockRejectedValueOnce(
      new Error('boom: chi tiết server'),
    )

    await table.load('2026-09-28')

    expect(table.errorMessage.value).toBe(
      'Không thể tải độ mới của giá theo vật tư.',
    )
    expect(table.data.value).toBeNull()
    expect(table.rows.value).toEqual([])
    expect(table.isLoading.value).toBe(false)
  })

  it('ignores a slower older response that arrives after a newer one', async () => {
    let resolveOld: (value: MaterialFreshness) => void = () => {}
    apiMock.getMaterialFreshness
      .mockImplementationOnce(
        () =>
          new Promise<MaterialFreshness>((resolve) => (resolveOld = resolve)),
      )
      .mockResolvedValueOnce(
        freshness([item({ materialName: 'Tuần mới' })], {
          weekStart: '2026-10-12',
        }),
      )
    const table = useMaterialFreshness()

    const oldLoad = table.load('2026-10-05')
    await table.load('2026-10-12')
    resolveOld(
      freshness([item({ materialName: 'Tuần cũ' })], {
        weekStart: '2026-10-05',
      }),
    )
    await oldLoad

    expect(table.data.value?.weekStart).toBe('2026-10-12')
    expect(table.rows.value[0].materialName).toBe('Tuần mới')
    expect(table.isLoading.value).toBe(false)
  })

  it('keeps loading until the latest request finishes', async () => {
    let resolveNew: (value: MaterialFreshness) => void = () => {}
    apiMock.getMaterialFreshness
      .mockResolvedValueOnce(freshness([item()]))
      .mockImplementationOnce(
        () =>
          new Promise<MaterialFreshness>((resolve) => (resolveNew = resolve)),
      )
    const table = useMaterialFreshness()

    await table.load('2026-10-05')
    const second = table.load('2026-10-12')
    expect(table.isLoading.value).toBe(true)
    resolveNew(freshness([item()]))
    await second

    expect(table.isLoading.value).toBe(false)
  })

  it('sorts overdue first by age, then never, on-time by age, then updated by count', async () => {
    apiMock.getMaterialFreshness.mockResolvedValue(
      freshness([
        item({
          materialId: 'u2',
          materialName: 'B cập nhật ít',
          status: 'updated',
          updateCount: 2,
        }),
        item({
          materialId: 'u5',
          materialName: 'A cập nhật nhiều',
          status: 'updated',
          updateCount: 5,
        }),
        item({
          materialId: 'o9',
          materialName: 'Quá hạn 9',
          status: 'overdue',
          ageDays: 9,
        }),
        item({
          materialId: 'o20',
          materialName: 'Quá hạn 20',
          status: 'overdue',
          ageDays: 20,
        }),
        item({
          materialId: 'nv',
          materialName: 'Chưa có giá',
          status: 'never',
          ageDays: null,
        }),
        item({
          materialId: 't3',
          materialName: 'Đúng hạn 3',
          status: 'on_time',
          ageDays: 3,
        }),
        item({
          materialId: 't6',
          materialName: 'Đúng hạn 6',
          status: 'on_time',
          ageDays: 6,
        }),
      ]),
    )
    const table = useMaterialFreshness()

    await table.load('2026-10-05')

    expect(table.rows.value.map((row) => row.materialId)).toEqual([
      'o20',
      'o9',
      'nv',
      't6',
      't3',
      'u5',
      'u2',
    ])
  })

  it('filters by status and by material type and can reset the filters', async () => {
    apiMock.getMaterialFreshness.mockResolvedValue(
      freshness([
        item({
          materialId: 'a',
          status: 'overdue',
          ageDays: 9,
          materialTypeId: 't-nl',
          materialTypeName: 'Nguyên liệu',
        }),
        item({
          materialId: 'b',
          status: 'overdue',
          ageDays: 8,
          materialTypeId: 't-vl',
          materialTypeName: 'Vi lượng',
        }),
        item({
          materialId: 'c',
          status: 'updated',
          updateCount: 1,
          materialTypeId: 't-nl',
          materialTypeName: 'Nguyên liệu',
        }),
      ]),
    )
    const table = useMaterialFreshness()
    await table.load('2026-10-05')

    expect(table.typeOptions.value).toEqual([
      { label: 'Nguyên liệu', value: 't-nl' },
      { label: 'Vi lượng', value: 't-vl' },
    ])
    expect(table.statusOptions.map((option) => option.value)).toEqual([
      'overdue',
      'never',
      'on_time',
      'updated',
    ])

    table.statusFilter.value = 'overdue'
    expect(table.rows.value.map((row) => row.materialId)).toEqual(['a', 'b'])
    expect(table.hasActiveFilters.value).toBe(true)

    table.typeFilter.value = 't-vl'
    expect(table.rows.value.map((row) => row.materialId)).toEqual(['b'])

    table.statusFilter.value = 'updated'
    expect(table.rows.value).toEqual([])
    expect(table.hasNoMatches.value).toBe(true)
    expect(table.isEmpty.value).toBe(false)

    table.resetFilters()
    expect(table.rows.value).toHaveLength(3)
    expect(table.hasActiveFilters.value).toBe(false)
    expect(table.hasNoMatches.value).toBe(false)
  })

  it('reports an empty table when the week has nothing to show', async () => {
    apiMock.getMaterialFreshness.mockResolvedValue(freshness([]))
    const table = useMaterialFreshness()

    await table.load('2026-10-05')

    expect(table.isEmpty.value).toBe(true)
    expect(table.hasNoMatches.value).toBe(false)
  })

  it('builds the four summary cards from the watched materials', async () => {
    const table = useMaterialFreshness()
    expect(table.summaryCards.value).toEqual([])

    await table.load('2026-10-05')

    expect(table.summaryCards.value).toEqual([
      {
        key: 'watched',
        label: 'Đang theo dõi',
        value: '4',
        detail: 'vật tư trong danh sách theo dõi',
        icon: 'pi pi-eye',
        tone: 'primary',
      },
      {
        key: 'updated',
        label: 'Đã cập nhật',
        value: '1 / 4',
        detail: '+3 vật tư không theo dõi cũng có giá mới',
        icon: 'pi pi-check-circle',
        tone: 'success',
      },
      {
        key: 'on_time',
        label: 'Đúng hạn',
        value: '1',
        detail: 'chưa có giá mới nhưng còn trong chu kỳ',
        icon: 'pi pi-clock',
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
    ])
  })

  it('turns the overdue card green when nothing is overdue and drops the extra note', async () => {
    apiMock.getMaterialFreshness.mockResolvedValue(
      freshness([], {
        summary: {
          watchedCount: 2,
          updatedCount: 2,
          onTimeCount: 0,
          overdueCount: 0,
          unwatchedUpdatedCount: 0,
        },
      }),
    )
    const table = useMaterialFreshness()

    await table.load('2026-10-05')

    const cards = table.summaryCards.value
    expect(cards[1].detail).toBe('trong tuần đã chọn')
    expect(cards[3].tone).toBe('success')
  })

  it('drops a material-type filter that no longer exists in the newly loaded week', async () => {
    apiMock.getMaterialFreshness
      .mockResolvedValueOnce(
        freshness([
          item({
            materialId: 'a',
            materialTypeId: 't-bb',
            materialTypeName: 'Bao bì',
          }),
          item({
            materialId: 'b',
            materialTypeId: 't-nl',
            materialTypeName: 'Nguyên liệu',
          }),
        ]),
      )
      .mockResolvedValueOnce(
        freshness([
          item({
            materialId: 'c',
            materialTypeId: 't-nl',
            materialTypeName: 'Nguyên liệu',
          }),
        ]),
      )
    const table = useMaterialFreshness()
    await table.load('2026-10-05')
    table.typeFilter.value = 't-bb'
    table.statusFilter.value = 'on_time'

    await table.load('2026-10-12')

    // Lọc theo loại biến mất cùng lựa chọn của nó; lọc theo trạng thái (luôn hợp lệ) được giữ.
    expect(table.typeFilter.value).toBeNull()
    expect(table.statusFilter.value).toBe('on_time')
    expect(table.rows.value.map((row) => row.materialId)).toEqual(['c'])
  })

  it('keeps a material-type filter that is still available in the new week', async () => {
    apiMock.getMaterialFreshness.mockResolvedValue(
      freshness([
        item({
          materialId: 'a',
          materialTypeId: 't-nl',
          materialTypeName: 'Nguyên liệu',
        }),
      ]),
    )
    const table = useMaterialFreshness()
    await table.load('2026-10-05')
    table.typeFilter.value = 't-nl'

    await table.load('2026-10-12')

    expect(table.typeFilter.value).toBe('t-nl')
  })

  describe('search, enterer filter and column sorting', () => {
    const lysine = item({
      materialId: 'lys',
      materialCode: 'LYS99',
      materialName: 'Lysine 99%',
      materialTypeId: 't-vl',
      materialTypeName: 'Vi lượng',
      status: 'overdue',
      ageDays: 17,
      expectedIntervalDays: 14,
      updateCount: 0,
      supplierCount: 0,
      lastReceivedDate: '2026-09-20',
      lastEntererId: 'u-b',
      lastEntererLabel: 'Trần Thị Bích',
    })
    const ngo = item({
      materialId: 'ngo',
      materialCode: 'NGO',
      materialName: 'Ngô hạt',
      materialTypeId: 't-nl',
      materialTypeName: 'Nguyên liệu',
      status: 'updated',
      updateCount: 5,
      supplierCount: 3,
      ageDays: 1,
      expectedIntervalDays: 7,
      lastReceivedDate: '2026-10-06',
      lastEntererId: 'u-a',
      lastEntererLabel: 'Nguyễn Văn An',
    })
    const bao = item({
      materialId: 'bao',
      materialCode: 'BAO',
      materialName: 'Bao bì 25kg',
      materialTypeId: 't-bb',
      materialTypeName: 'Bao bì',
      status: 'never',
      ageDays: null,
      expectedIntervalDays: 30,
      updateCount: 0,
      supplierCount: 0,
      lastReceivedDate: null,
      lastEntererId: null,
      lastEntererLabel: null,
    })
    const ids = (table: ReturnType<typeof useMaterialFreshness>) =>
      table.rows.value.map((row) => row.materialId)

    async function loaded() {
      apiMock.getMaterialFreshness.mockResolvedValue(
        freshness([ngo, lysine, bao]),
      )
      const table = useMaterialFreshness()
      await table.load('2026-10-05')
      return table
    }

    it.each([
      ['lysine', ['lys']],
      ['LYS99', ['lys']],
      ['  ngo  ', ['ngo']],
      ['bì 25', ['bao']],
      ['bi 25', ['bao']], // không phân biệt dấu
      ['ngô hat', ['ngo']],
      ['vi luong', ['lys']], // theo tên loại
      ['TRAN thi', ['lys']], // theo người nhập
      ['khongco', []],
    ])(
      'searches name, code, type and enterer without caring about accents: "%s"',
      async (text, expected) => {
        const table = await loaded()

        table.searchText.value = text

        expect(ids(table)).toEqual(expected)
      },
    )

    it('a blank search shows everything and counts as no active filter', async () => {
      const table = await loaded()
      table.searchText.value = '   '

      expect(ids(table)).toHaveLength(3)
      expect(table.hasActiveFilters.value).toBe(false)
      table.searchText.value = 'ngo'
      expect(table.hasActiveFilters.value).toBe(true)
    })

    it('lists the enterers (and "unknown") and filters by them', async () => {
      const table = await loaded()

      expect(table.entererOptions.value).toEqual([
        { label: 'Chưa rõ người nhập', value: '__none__' },
        { label: 'Nguyễn Văn An', value: 'u-a' },
        { label: 'Trần Thị Bích', value: 'u-b' },
      ])
      table.entererFilter.value = 'u-a'
      expect(ids(table)).toEqual(['ngo'])
      table.entererFilter.value = '__none__'
      expect(ids(table)).toEqual(['bao'])
      expect(table.hasActiveFilters.value).toBe(true)
    })

    it('combines search, status, type and enterer, and resetFilters clears all of them', async () => {
      const table = await loaded()
      table.searchText.value = 'l'
      table.statusFilter.value = 'overdue'
      table.typeFilter.value = 't-vl'
      table.entererFilter.value = 'u-b'
      expect(ids(table)).toEqual(['lys'])

      table.entererFilter.value = 'u-a'
      expect(ids(table)).toEqual([])
      expect(table.hasNoMatches.value).toBe(true)

      table.resetFilters()
      expect(ids(table)).toHaveLength(3)
      expect(table.searchText.value).toBe('')
      expect(table.entererFilter.value).toBeNull()
    })

    it('drops an enterer filter that disappears when another week is loaded', async () => {
      apiMock.getMaterialFreshness
        .mockResolvedValueOnce(freshness([ngo, lysine]))
        .mockResolvedValueOnce(freshness([ngo]))
      const table = useMaterialFreshness()
      await table.load('2026-10-05')
      table.entererFilter.value = 'u-b'

      await table.load('2026-10-12')

      expect(table.entererFilter.value).toBeNull()
      expect(ids(table)).toEqual(['ngo'])
    })

    it.each([
      ['name', 1, ['bao', 'lys', 'ngo']],
      ['name', -1, ['ngo', 'lys', 'bao']],
      ['type', 1, ['bao', 'ngo', 'lys']],
      ['updateCount', 1, ['lys', 'bao', 'ngo']],
      ['updateCount', -1, ['ngo', 'lys', 'bao']],
      ['supplierCount', -1, ['ngo', 'lys', 'bao']],
      ['status', 1, ['lys', 'bao', 'ngo']],
      ['status', -1, ['ngo', 'bao', 'lys']],
      ['enterer', 1, ['ngo', 'lys', 'bao']], // chưa rõ luôn cuối
      ['enterer', -1, ['lys', 'ngo', 'bao']],
    ])('sorts by %s (order %s)', async (field, order, expected) => {
      const table = await loaded()

      await table.onSort({ sortField: field, sortOrder: order })

      expect(ids(table)).toEqual(expected)
      expect(table.sortField.value).toBe(field)
    })

    it.each([
      ['lastReceivedDate', 1, ['lys', 'ngo', 'bao']],
      ['lastReceivedDate', -1, ['ngo', 'lys', 'bao']],
      ['ageDays', 1, ['ngo', 'lys', 'bao']],
      ['ageDays', -1, ['lys', 'ngo', 'bao']],
    ])(
      'puts missing values last in both directions: %s (order %s)',
      async (field, order, expected) => {
        const table = await loaded()

        await table.onSort({ sortField: field, sortOrder: order })

        expect(ids(table)).toEqual(expected)
      },
    )

    it('sorts the interval and leaves unwatched materials (no interval) last', async () => {
      const unwatched = item({
        materialId: 'free',
        materialName: 'Không theo dõi',
        isWatched: false,
        expectedIntervalDays: null,
        status: 'updated',
        updateCount: 1,
      })
      apiMock.getMaterialFreshness.mockResolvedValue(
        freshness([unwatched, ngo, lysine, bao]),
      )
      const table = useMaterialFreshness()
      await table.load('2026-10-05')

      await table.onSort({ sortField: 'interval', sortOrder: 1 })
      expect(ids(table)).toEqual(['ngo', 'lys', 'bao', 'free'])
      await table.onSort({ sortField: 'interval', sortOrder: -1 })
      expect(ids(table)).toEqual(['bao', 'lys', 'ngo', 'free'])
    })

    it('goes back to the default order when the sort is cleared or the column is unknown', async () => {
      const table = await loaded()
      await table.onSort({ sortField: 'name', sortOrder: 1 })

      await table.onSort({ sortField: null, sortOrder: null })
      expect(ids(table)).toEqual(['lys', 'bao', 'ngo']) // quá hạn, chưa có giá, đã cập nhật
      expect(table.sortField.value).toBeNull()

      await table.onSort({ sortField: 'hacker', sortOrder: 1 })
      expect(table.sortField.value).toBeNull()
    })

    it('forgets the direction when the sort is cleared, so the next column starts ascending', async () => {
      const table = await loaded()
      await table.onSort({ sortField: 'name', sortOrder: -1 })

      await table.onSort({ sortField: null, sortOrder: -1 }) // ô chọn bị xóa khi đang giảm dần
      expect(table.sortOrder.value).toBe(1)
      await table.onSort({ sortField: 'status', sortOrder: 1 })
      expect(table.sortOrder.value).toBe(1)
    })

    it('keeps the sort across filters and across reloads', async () => {
      const table = await loaded()
      await table.onSort({ sortField: 'name', sortOrder: -1 })
      table.statusFilter.value = null
      table.searchText.value = 'n'
      expect(ids(table)).toEqual(['ngo', 'lys'])
      apiMock.getMaterialFreshness.mockResolvedValue(
        freshness([ngo, lysine, bao]),
      )

      await table.load('2026-10-12')

      expect(table.sortField.value).toBe('name')
      expect(ids(table)).toEqual(['ngo', 'lys'])
    })

    it('offers the sortable columns as options for small screens', async () => {
      const table = await loaded()

      expect(table.sortOptions.map((option) => option.value)).toEqual([
        'name',
        'type',
        'updateCount',
        'supplierCount',
        'lastReceivedDate',
        'ageDays',
        'interval',
        'status',
        'enterer',
      ])
    })
  })
})
