import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useDashboardPage } from '@/composables/useDashboardPage'
import { useAuthStore } from '@/stores/auth.store'

const dashboardApiMock = vi.hoisted(() => ({
  getQuotifyEntryKpis: vi.fn(),
  getQuotifyPriceTrends: vi.fn(),
  getQuotifyWeeklyEntryActivity: vi.fn(),
}))

const materialsApiMock = vi.hoisted(() => ({
  listMaterialsLookup: vi.fn(),
}))

vi.mock('@/api/quotify-dashboard.api', () => dashboardApiMock)
vi.mock('@/api/materials.api', () => materialsApiMock)

const entryKpis = {
  totalQuoteCount: 7,
  userKpis: [
    {
      userId: 'user-1',
      userEmail: 'buyer@example.com',
      userFullName: 'Người mua hàng',
      userLabel: 'Người mua hàng',
      quoteCount: 7,
    },
  ],
}

const priceTrends = {
  summary: {
    minPrice: 10200,
    maxPrice: 11800,
    avgPrice: 11000,
    totalLines: 9,
    totalQuotes: 7,
    purchasedLines: 2,
  },
  points: [
    {
      receivedDate: '2026-07-20',
      deliveryMonth: '2026-08-01',
      convertedPriceVndPerKg: 10500,
      supplierId: 'supplier-1',
      supplierName: 'Nhà cung cấp A',
      supplierCode: 'NCC-A',
      supplierType: 'domestic',
      supplierLabel: 'NCC-A - Nhà cung cấp A',
      materialId: 'material-1',
      materialName: 'Bắp hạt',
      materialCode: 'BAP',
      quoteId: 'quote-1',
      quoteVersionId: 'version-1',
      lineId: 'line-1',
      purchased: true,
      purchaseMarkedAt: '2026-07-20T03:00:00+00:00',
      confirmedAt: '2026-07-20T02:00:00+00:00',
    },
    {
      receivedDate: '2026-07-22',
      deliveryMonth: '2026-08-01',
      convertedPriceVndPerKg: 11500,
      supplierId: 'supplier-2',
      supplierName: 'Nhà cung cấp B',
      supplierCode: 'NCC-B',
      supplierType: 'international',
      supplierLabel: 'NCC-B - Nhà cung cấp B',
      materialId: 'material-1',
      materialName: 'Ngô hạt',
      materialCode: 'CORN',
      quoteId: 'quote-2',
      quoteVersionId: 'version-2',
      lineId: 'line-2',
      purchased: false,
      purchaseMarkedAt: null,
      confirmedAt: '2026-07-22T02:00:00+00:00',
    },
    {
      receivedDate: '2026-07-25',
      deliveryMonth: '2026-09-01',
      convertedPriceVndPerKg: 12000,
      supplierId: 'supplier-1',
      supplierName: 'Nhà cung cấp A',
      supplierCode: 'NCC-A',
      supplierType: 'domestic',
      supplierLabel: 'NCC-A - Nhà cung cấp A',
      materialId: 'material-1',
      materialName: 'Ngô hạt',
      materialCode: 'CORN',
      quoteId: 'quote-3',
      quoteVersionId: 'version-3',
      lineId: 'line-3',
      purchased: false,
      purchaseMarkedAt: null,
      confirmedAt: '2026-07-25T02:00:00+00:00',
    },
  ],
  purchaseContexts: [],
}

const weeklyEntryActivity = {
  weekStart: '2026-07-27',
  weekEnd: '2026-08-02',
  totalQuoteCount: 7,
  activeUserCount: 2,
  usersWithQuotes: 1,
  usersWithoutQuotes: 1,
  userActivities: [
    {
      userId: 'user-1',
      userEmail: 'buyer@example.com',
      userFullName: 'Người mua hàng',
      userLabel: 'Người mua hàng',
      quoteCount: 7,
      lastQuoteCreatedAt: '2026-07-29T02:00:00+00:00',
      hasWarning: false,
    },
    {
      userId: 'user-2',
      userEmail: 'quiet@example.com',
      userFullName: 'Người chưa nhập',
      userLabel: 'Người chưa nhập',
      quoteCount: 0,
      lastQuoteCreatedAt: null,
      hasWarning: true,
    },
  ],
}

describe('useDashboardPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()

    const authStore = useAuthStore()
    authStore.accessToken = 'mock-access-token'

    materialsApiMock.listMaterialsLookup.mockResolvedValue([
      {
        id: 'material-1',
        code: 'CORN',
        name: 'Ngô hạt',
        materialTypeId: 'type-1',
        materialTypeCode: 'NL',
        materialTypeName: 'Nguyên liệu',
        status: 'active',
        note: null,
        createdAt: '2026-07-01T00:00:00+00:00',
        updatedAt: '2026-07-01T00:00:00+00:00',
      },
    ])
    dashboardApiMock.getQuotifyEntryKpis.mockResolvedValue(entryKpis)
    dashboardApiMock.getQuotifyPriceTrends.mockResolvedValue(priceTrends)
    dashboardApiMock.getQuotifyWeeklyEntryActivity.mockResolvedValue(
      weeklyEntryActivity,
    )
  })

  it('bootstraps lookups, KPI data, trend data and metric cards', async () => {
    const page = useDashboardPage()

    await page.bootstrap()

    expect(materialsApiMock.listMaterialsLookup).toHaveBeenCalledWith(
      'mock-access-token',
    )
    expect(dashboardApiMock.getQuotifyEntryKpis).toHaveBeenCalledWith(
      {
        materialId: 'material-1',
        deliveryMonth: null,
        receivedDateStart: null,
        receivedDateEnd: null,
        supplierType: null,
      },
      'mock-access-token',
    )
    expect(dashboardApiMock.getQuotifyWeeklyEntryActivity).toHaveBeenCalledWith(
      {
        weekStart: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
        userId: null,
      },
      'mock-access-token',
    )
    expect(page.materials.value).toHaveLength(1)
    expect(page.selectedMaterialId.value).toBe('material-1')
    expect(page.userKpis.value[0].quoteCount).toBe(7)
    expect(page.metricCards.value.map((card) => card.label)).toEqual([
      'Giá thấp nhất',
      'Giá cao nhất',
      'Giá trung bình',
      'Tổng báo giá',
    ])
    expect(page.metricCards.value.slice(0, 3).map((card) => card.value)).toEqual([
      '10,200.00 VNĐ/KG',
      '11,800.00 VNĐ/KG',
      '11,000.00 VNĐ/KG',
    ])
    expect(page.hasTrendData.value).toBe(true)
    expect(page.deliveryMonthBuckets.value.map((bucket) => bucket.label)).toEqual(
      ['08/2026', '09/2026'],
    )
    expect(page.deliveryMonthBuckets.value[0]).toMatchObject({
      minPrice: 10500,
      maxPrice: 11500,
      avgPrice: 11000,
      pointCount: 2,
      purchasedPrice: 10500,
    })
    expect(page.chartData.value.labels).toEqual(['08/2026', '09/2026'])
    expect(page.chartData.value.datasets.map((dataset) => dataset.label)).toEqual(
      ['Giá trung bình', 'Giá thấp nhất', 'Giá cao nhất', 'Đã chốt mua'],
    )
    expect(
      page.chartData.value.datasets.find((dataset) => dataset.label === 'Đã chốt mua'),
    ).toMatchObject({
      borderColor: '#ef4444',
      backgroundColor: '#ef4444',
      pointBackgroundColor: '#ef4444',
    })
    expect(page.weeklyEntryMetricCards.value.map((card) => card.label)).toEqual([
      'Báo giá tuần',
      'User đã nhập',
      'User chưa nhập',
    ])
    expect(page.weeklyWarningUsers.value).toHaveLength(1)
    expect(page.weeklyEntryChartData.value.labels).toEqual([
      'Người mua hàng',
      'Người chưa nhập',
    ])
    expect(page.weeklyEntryChartData.value.datasets[0].data).toEqual([7, 0])
  })

  it('sends selected material, month and received date filters to dashboard APIs', async () => {
    const page = useDashboardPage()

    page.selectedMaterialId.value = 'material-1'
    page.selectedSupplierType.value = 'international'
    page.deliveryMonth.value = new Date(2026, 7, 1)
    page.receivedDateStart.value = new Date(2026, 6, 1)
    page.receivedDateEnd.value = new Date(2026, 6, 31)

    await page.applyFilters()

    const expectedQuery = {
      materialId: 'material-1',
      deliveryMonth: '2026-08-01',
      receivedDateStart: '2026-07-01',
      receivedDateEnd: '2026-07-31',
      supplierType: 'international',
    }

    expect(dashboardApiMock.getQuotifyEntryKpis).toHaveBeenCalledWith(
      expectedQuery,
      'mock-access-token',
    )
    expect(dashboardApiMock.getQuotifyPriceTrends).toHaveBeenCalledWith(
      expectedQuery,
      'mock-access-token',
    )
  })

  it('clears filters and reloads dashboard data', async () => {
    const page = useDashboardPage()
    page.selectedMaterialId.value = 'another-material'
    page.selectedSupplierType.value = 'domestic'
    page.deliveryMonth.value = new Date(2026, 7, 1)
    page.materials.value = [
      {
        id: 'material-1',
        code: 'CORN',
        name: 'Ngô hạt',
        materialTypeId: 'type-1',
        materialTypeCode: 'NL',
        materialTypeName: 'Nguyên liệu',
        status: 'active',
        note: null,
        createdAt: '2026-07-01T00:00:00+00:00',
        updatedAt: '2026-07-01T00:00:00+00:00',
      },
    ]

    await page.resetFilters()

    expect(page.selectedMaterialId.value).toBe('material-1')
    expect(page.selectedSupplierType.value).toBeNull()
    expect(page.deliveryMonth.value).toBeNull()
    expect(dashboardApiMock.getQuotifyEntryKpis).toHaveBeenCalledWith(
      {
        materialId: 'material-1',
        deliveryMonth: null,
        receivedDateStart: null,
        receivedDateEnd: null,
        supplierType: null,
      },
      'mock-access-token',
    )
  })

  it('loads weekly entry activity with selected week and user filters', async () => {
    const page = useDashboardPage()

    page.selectedWeek.value = new Date(2026, 6, 29)
    page.selectedWeeklyUserId.value = 'user-1'

    await page.applyWeeklyEntryFilters()

    expect(dashboardApiMock.getQuotifyWeeklyEntryActivity).toHaveBeenCalledWith(
      {
        weekStart: '2026-07-27',
        userId: 'user-1',
      },
      'mock-access-token',
    )
  })

  describe('material price comparison', () => {
    it('does not fetch or build comparison buckets with fewer than 2 selected materials', async () => {
      const page = useDashboardPage()
      page.comparisonMaterialIds.value = ['material-1']

      await page.loadMaterialComparison()

      expect(dashboardApiMock.getQuotifyPriceTrends).not.toHaveBeenCalled()
      expect(page.comparisonBuckets.value).toEqual([])
    })

    it('fetches trends for each selected material in parallel with shared filters', async () => {
      const page = useDashboardPage()
      page.selectedSupplierType.value = 'international'
      page.comparisonMaterialIds.value = ['material-1', 'material-2']

      await page.loadMaterialComparison()

      expect(dashboardApiMock.getQuotifyPriceTrends).toHaveBeenCalledTimes(2)
      expect(dashboardApiMock.getQuotifyPriceTrends).toHaveBeenCalledWith(
        {
          materialId: 'material-1',
          deliveryMonth: null,
          receivedDateStart: null,
          receivedDateEnd: null,
          supplierType: 'international',
        },
        'mock-access-token',
      )
      expect(dashboardApiMock.getQuotifyPriceTrends).toHaveBeenCalledWith(
        {
          materialId: 'material-2',
          deliveryMonth: null,
          receivedDateStart: null,
          receivedDateEnd: null,
          supplierType: 'international',
        },
        'mock-access-token',
      )
    })

    it('merges per-material trends into buckets with average price and quote count per month', async () => {
      dashboardApiMock.getQuotifyPriceTrends.mockImplementation(async (query) => {
        if (query.materialId === 'material-1') {
          return {
            ...priceTrends,
            points: [
              { ...priceTrends.points[0], deliveryMonth: '2026-08-01', convertedPriceVndPerKg: 10000 },
              { ...priceTrends.points[0], deliveryMonth: '2026-08-01', convertedPriceVndPerKg: 11000 },
              { ...priceTrends.points[0], deliveryMonth: '2026-09-01', convertedPriceVndPerKg: 12000 },
            ],
          }
        }
        return {
          ...priceTrends,
          points: [
            { ...priceTrends.points[0], deliveryMonth: '2026-08-01', convertedPriceVndPerKg: 9000 },
          ],
        }
      })

      const page = useDashboardPage()
      page.materials.value = [
        { ...page.materials.value[0], id: 'material-1', name: 'Ngô hạt' },
        { ...page.materials.value[0], id: 'material-2', name: 'Khô đậu nành' },
      ]
      page.comparisonMaterialIds.value = ['material-1', 'material-2']

      await page.loadMaterialComparison()

      expect(page.comparisonBuckets.value.map((bucket) => bucket.label)).toEqual([
        '08/2026',
        '09/2026',
      ])
      expect(page.comparisonBuckets.value[0].series).toEqual([
        {
          materialId: 'material-1',
          materialName: 'Ngô hạt',
          avgPrice: 10500,
          minPrice: 10000,
          maxPrice: 11000,
          pointCount: 2,
        },
        {
          materialId: 'material-2',
          materialName: 'Khô đậu nành',
          avgPrice: 9000,
          minPrice: 9000,
          maxPrice: 9000,
          pointCount: 1,
        },
      ])
      expect(page.comparisonBuckets.value[1].series).toEqual([
        {
          materialId: 'material-1',
          materialName: 'Ngô hạt',
          avgPrice: 12000,
          minPrice: 12000,
          maxPrice: 12000,
          pointCount: 1,
        },
        {
          materialId: 'material-2',
          materialName: 'Khô đậu nành',
          avgPrice: null,
          minPrice: null,
          maxPrice: null,
          pointCount: 0,
        },
      ])
    })

    it('builds a price-difference callout comparing the two selected materials directly', async () => {
      dashboardApiMock.getQuotifyPriceTrends.mockImplementation(async (query) => ({
        ...priceTrends,
        points: [
          {
            ...priceTrends.points[0],
            deliveryMonth: '2026-08-01',
            convertedPriceVndPerKg: query.materialId === 'material-1' ? 7200 : 9450,
          },
        ],
      }))

      const page = useDashboardPage()
      page.materials.value = [
        { ...page.materials.value[0], id: 'material-1', name: 'Ngô hạt' },
        { ...page.materials.value[0], id: 'material-2', name: 'Khô đậu nành' },
      ]
      page.comparisonMaterialIds.value = ['material-1', 'material-2']

      await page.loadMaterialComparison()

      expect(page.comparisonBuckets.value[0].differenceLines).toEqual([
        'Khô đậu nành cao hơn Ngô hạt: +2,250.00 VNĐ/KG (+31.25%)',
      ])
    })

    it('builds a price-difference callout comparing each material against the cheapest one, for 3 materials', async () => {
      dashboardApiMock.getQuotifyPriceTrends.mockImplementation(async (query) => {
        const priceByMaterial: Record<string, number> = {
          'material-1': 7200,
          'material-2': 9450,
          'material-3': 7500,
        }
        return {
          ...priceTrends,
          points: [
            {
              ...priceTrends.points[0],
              deliveryMonth: '2026-08-01',
              convertedPriceVndPerKg: priceByMaterial[query.materialId],
            },
          ],
        }
      })

      const page = useDashboardPage()
      page.materials.value = [
        { ...page.materials.value[0], id: 'material-1', name: 'Ngô hạt' },
        { ...page.materials.value[0], id: 'material-2', name: 'Khô đậu nành' },
        { ...page.materials.value[0], id: 'material-3', name: 'Lúa mì' },
      ]
      page.comparisonMaterialIds.value = ['material-1', 'material-2', 'material-3']

      await page.loadMaterialComparison()

      expect(page.comparisonBuckets.value[0].differenceLines).toEqual([
        'Khô đậu nành cao hơn Ngô hạt: +2,250.00 VNĐ/KG (+31.25%)',
        'Lúa mì cao hơn Ngô hạt: +300.00 VNĐ/KG (+4.17%)',
      ])
    })

    it('skips the price-difference callout for a month with fewer than 2 materials priced', async () => {
      dashboardApiMock.getQuotifyPriceTrends.mockImplementation(async (query) => ({
        ...priceTrends,
        points:
          query.materialId === 'material-1'
            ? [{ ...priceTrends.points[0], deliveryMonth: '2026-08-01', convertedPriceVndPerKg: 7200 }]
            : [],
      }))

      const page = useDashboardPage()
      page.materials.value = [
        { ...page.materials.value[0], id: 'material-1', name: 'Ngô hạt' },
        { ...page.materials.value[0], id: 'material-2', name: 'Khô đậu nành' },
      ]
      page.comparisonMaterialIds.value = ['material-1', 'material-2']

      await page.loadMaterialComparison()

      expect(page.comparisonBuckets.value[0].differenceLines).toEqual([])
    })

    it('only fetches the first 3 materials if more are somehow selected', async () => {
      const page = useDashboardPage()
      page.comparisonMaterialIds.value = ['material-1', 'material-2', 'material-3', 'material-4']

      await page.loadMaterialComparison()

      expect(dashboardApiMock.getQuotifyPriceTrends).toHaveBeenCalledTimes(3)
      expect(dashboardApiMock.getQuotifyPriceTrends).not.toHaveBeenCalledWith(
        expect.objectContaining({ materialId: 'material-4' }),
        expect.anything(),
      )
    })

    it('builds one chart dataset per loaded material with distinct colors and gaps as null', async () => {
      dashboardApiMock.getQuotifyPriceTrends.mockImplementation(async (query) => ({
        ...priceTrends,
        points:
          query.materialId === 'material-1'
            ? [
                { ...priceTrends.points[0], deliveryMonth: '2026-08-01', convertedPriceVndPerKg: 7200 },
                { ...priceTrends.points[0], deliveryMonth: '2026-09-01', convertedPriceVndPerKg: 7300 },
              ]
            : [{ ...priceTrends.points[0], deliveryMonth: '2026-08-01', convertedPriceVndPerKg: 9450 }],
      }))

      const page = useDashboardPage()
      page.materials.value = [
        { ...page.materials.value[0], id: 'material-1', name: 'Ngô hạt' },
        { ...page.materials.value[0], id: 'material-2', name: 'Khô đậu nành' },
      ]
      page.comparisonMaterialIds.value = ['material-1', 'material-2']

      await page.loadMaterialComparison()
      // Tắt dải giá thấp-cao để cô lập test này vào đúng hành vi của đường
      // trung bình (dải giá thấp-cao có test riêng bên dưới).
      page.comparisonBandVisibility.value['material-1'] = false
      page.comparisonBandVisibility.value['material-2'] = false

      expect(page.comparisonChartData.value.labels).toEqual(['08/2026', '09/2026'])
      expect(page.comparisonChartData.value.datasets).toHaveLength(2)
      expect(page.comparisonChartData.value.datasets[0]).toMatchObject({
        label: 'Ngô hạt',
        data: [7200, 7300],
        spanGaps: false,
      })
      expect(page.comparisonChartData.value.datasets[1]).toMatchObject({
        label: 'Khô đậu nành',
        data: [9450, null],
        spanGaps: false,
      })
      expect(page.comparisonChartData.value.datasets[0].borderColor).not.toBe(
        page.comparisonChartData.value.datasets[1].borderColor,
      )
    })

    it('defaults to showing the min-max band for every newly loaded material', async () => {
      const page = useDashboardPage()
      page.comparisonMaterialIds.value = ['material-1', 'material-2']

      await page.loadMaterialComparison()

      expect(page.comparisonBandVisibility.value['material-1']).toBe(true)
      expect(page.comparisonBandVisibility.value['material-2']).toBe(true)
    })

    it('adds min-max band datasets for a material by default, and removes them once toggled off', async () => {
      dashboardApiMock.getQuotifyPriceTrends.mockImplementation(async (query) => ({
        ...priceTrends,
        points:
          query.materialId === 'material-1'
            ? [
                { ...priceTrends.points[0], deliveryMonth: '2026-08-01', convertedPriceVndPerKg: 7000 },
                { ...priceTrends.points[0], deliveryMonth: '2026-08-01', convertedPriceVndPerKg: 7400 },
              ]
            : [{ ...priceTrends.points[0], deliveryMonth: '2026-08-01', convertedPriceVndPerKg: 9450 }],
      }))

      const page = useDashboardPage()
      page.materials.value = [
        { ...page.materials.value[0], id: 'material-1', name: 'Ngô hạt' },
        { ...page.materials.value[0], id: 'material-2', name: 'Khô đậu nành' },
      ]
      page.comparisonMaterialIds.value = ['material-1', 'material-2']
      await page.loadMaterialComparison()

      // Mặc định: 1 dataset avg + 2 dataset band (min/max) cho mỗi mặt hàng = 6.
      expect(page.comparisonChartData.value.datasets).toHaveLength(6)
      const bandDatasetLabels = page.comparisonChartData.value.datasets.map(
        (dataset: { label?: string }) => dataset.label,
      )
      expect(bandDatasetLabels).toContain('Ngô hạt (cao nhất)')
      expect(bandDatasetLabels).toContain('Ngô hạt (thấp nhất)')

      page.comparisonBandVisibility.value['material-1'] = false

      expect(page.comparisonChartData.value.datasets).toHaveLength(4)
      expect(
        page.comparisonChartData.value.datasets.map((dataset: { label?: string }) => dataset.label),
      ).toEqual(['Ngô hạt', 'Khô đậu nành (cao nhất)', 'Khô đậu nành (thấp nhất)', 'Khô đậu nành'])
    })
  })
})
