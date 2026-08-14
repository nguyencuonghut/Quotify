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

const pushMock = vi.hoisted(() => vi.fn())

vi.mock('@/api/quotify-dashboard.api', () => dashboardApiMock)
vi.mock('@/api/materials.api', () => materialsApiMock)
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
}))

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
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 7, 13))

    const page = useDashboardPage()

    await page.bootstrap()

    expect(materialsApiMock.listMaterialsLookup).toHaveBeenCalledWith(
      'mock-access-token',
    )
    expect(dashboardApiMock.getQuotifyEntryKpis).toHaveBeenCalledWith(
      {
        materialId: 'material-1',
        // Mặc định "kỳ giao hàng" = tháng hiện tại + 2 (hôm nay 08/2026 →
        // 10/2026) — chart này giờ luôn cần 1 kỳ giao hàng cố định.
        deliveryMonth: '2026-10-01',
        receivedDateStart: null,
        receivedDateEnd: null,
        supplierType: null,
      },
      'mock-access-token',
    )

    vi.useRealTimers()
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
    expect(page.hasTrendData.value).toBe(true)
    // Trục X giờ là THÁNG NHẬN BÁO GIÁ (không phải kỳ giao hàng) cho 1 kỳ
    // giao hàng cố định — cả 3 điểm mẫu đều nhận trong 07/2026 (dù thuộc 2
    // kỳ giao hàng 08/2026 và 09/2026 khác nhau) nên gộp chung 1 bucket.
    expect(page.deliveryMonthBuckets.value.map((bucket) => bucket.label)).toEqual(
      ['07/2026'],
    )
    expect(page.deliveryMonthBuckets.value[0]).toMatchObject({
      minPrice: 10500,
      maxPrice: 12000,
      avgPrice: 34000 / 3,
      pointCount: 3,
      purchasedPrice: 10500,
    })
    expect(page.chartData.value.labels).toEqual(['07/2026'])
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

  it('clicking a point on the "Giá theo kỳ hàng về" chart navigates to /quotes with the fixed delivery month and the clicked received-date month range', async () => {
    const page = useDashboardPage()
    page.selectedMaterialId.value = 'material-1'
    page.deliveryMonth.value = new Date(2026, 9, 1)

    await page.bootstrap()

    page.chartOptions.value.onClick(null, [{ index: 0 }])

    expect(pushMock).toHaveBeenCalledWith({
      path: '/quotes',
      query: {
        materialId: 'material-1',
        deliveryMonth: '2026-10-01',
        receivedDateStart: '2026-07-01',
        receivedDateEnd: '2026-07-31',
      },
    })
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
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 7, 13))

    const page = useDashboardPage()
    page.selectedMaterialId.value = 'another-material'
    page.selectedSupplierType.value = 'domestic'
    page.deliveryMonth.value = new Date(2027, 2, 1)
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
    // "Xóa lọc" đưa kỳ giao hàng về lại mặc định (tháng hiện tại + 2), không
    // phải rỗng — chart này luôn cần 1 kỳ giao hàng cố định.
    expect(page.deliveryMonth.value).toEqual(new Date(2026, 9, 1))
    expect(dashboardApiMock.getQuotifyEntryKpis).toHaveBeenCalledWith(
      {
        materialId: 'material-1',
        deliveryMonth: '2026-10-01',
        receivedDateStart: null,
        receivedDateEnd: null,
        supplierType: null,
      },
      'mock-access-token',
    )

    vi.useRealTimers()
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

    it('fetches trends for each selected material in parallel with shared filters, ignoring the fixed delivery month of the sibling chart', async () => {
      const page = useDashboardPage()
      page.selectedSupplierType.value = 'international'
      // Chart này so sánh giá GIỮA CÁC kỳ hàng về, nên phải không bị ảnh
      // hưởng bởi kỳ giao hàng cố định của chart "Giá theo kỳ hàng về" cạnh
      // nó (dùng chung 1 bộ lọc "Kỳ giao hàng" ở panel trên) — nếu không,
      // trục X của chart này sẽ luôn chỉ còn 1 kỳ do bị lọc trùng.
      page.deliveryMonth.value = new Date(2026, 9, 1)
      page.comparisonMaterialIds.value = ['material-1', 'material-2']

      await page.loadMaterialComparison()

      expect(dashboardApiMock.getQuotifyPriceTrends).toHaveBeenCalledTimes(2)
      expect(dashboardApiMock.getQuotifyPriceTrends).toHaveBeenCalledWith(
        {
          materialId: 'material-1',
          receivedDateStart: null,
          receivedDateEnd: null,
          supplierType: 'international',
        },
        'mock-access-token',
      )
      expect(dashboardApiMock.getQuotifyPriceTrends).toHaveBeenCalledWith(
        {
          materialId: 'material-2',
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

  describe('price history by received date for a fixed delivery month', () => {
    it('does not fetch without a fixed delivery month, even with 2+ materials selected', async () => {
      const page = useDashboardPage()
      page.historyMaterialIds.value = ['material-1', 'material-2']
      page.historyDeliveryMonth.value = null

      await page.loadPriceHistory()

      expect(dashboardApiMock.getQuotifyPriceTrends).not.toHaveBeenCalled()
      expect(page.historyBuckets.value).toEqual([])
    })

    it('fetches each selected material with the fixed delivery month, in parallel', async () => {
      const page = useDashboardPage()
      page.historyMaterialIds.value = ['material-1', 'material-2']
      page.historyDeliveryMonth.value = new Date(2026, 11, 1)

      await page.loadPriceHistory()

      expect(dashboardApiMock.getQuotifyPriceTrends).toHaveBeenCalledTimes(2)
      expect(dashboardApiMock.getQuotifyPriceTrends).toHaveBeenCalledWith(
        { materialId: 'material-1', deliveryMonth: '2026-12-01' },
        'mock-access-token',
      )
      expect(dashboardApiMock.getQuotifyPriceTrends).toHaveBeenCalledWith(
        { materialId: 'material-2', deliveryMonth: '2026-12-01' },
        'mock-access-token',
      )
    })

    it('splits each received month into 3 finer buckets (kỳ 1: 1-10, kỳ 2: 11-20, kỳ 3: 21-cuối tháng), with gaps where a material has none', async () => {
      dashboardApiMock.getQuotifyPriceTrends.mockImplementation(async (query) => {
        if (query.materialId === 'material-1') {
          return {
            ...priceTrends,
            points: [
              { ...priceTrends.points[0], receivedDate: '2026-01-05', convertedPriceVndPerKg: 7000 },
              { ...priceTrends.points[0], receivedDate: '2026-01-15', convertedPriceVndPerKg: 7200 },
              { ...priceTrends.points[0], receivedDate: '2026-02-10', convertedPriceVndPerKg: 7400 },
            ],
          }
        }
        return {
          ...priceTrends,
          points: [
            { ...priceTrends.points[0], receivedDate: '2026-01-15', convertedPriceVndPerKg: 9000 },
          ],
        }
      })

      const page = useDashboardPage()
      page.materials.value = [
        { ...page.materials.value[0], id: 'material-1', name: 'Ngô hạt' },
        { ...page.materials.value[0], id: 'material-2', name: 'Khô đậu nành' },
      ]
      page.historyMaterialIds.value = ['material-1', 'material-2']
      page.historyDeliveryMonth.value = new Date(2026, 11, 1)

      await page.loadPriceHistory()

      // Ngày 05/01 (kỳ 1) và 15/01 (kỳ 2) giờ phải rơi vào 2 bucket KHÁC nhau
      // trong cùng tháng 1, không còn gộp chung 1 bucket "01/2026" như trước.
      expect(page.historyBuckets.value.map((bucket) => bucket.label)).toEqual([
        '01/01/2026',
        '11/01/2026',
        '01/02/2026',
      ])
      expect(page.historyBuckets.value[0].series).toEqual([
        {
          materialId: 'material-1',
          materialName: 'Ngô hạt',
          avgPrice: 7000,
          minPrice: 7000,
          maxPrice: 7000,
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
      expect(page.historyBuckets.value[1].series).toEqual([
        {
          materialId: 'material-1',
          materialName: 'Ngô hạt',
          avgPrice: 7200,
          minPrice: 7200,
          maxPrice: 7200,
          pointCount: 1,
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
      expect(page.historyBuckets.value[2].series).toEqual([
        {
          materialId: 'material-1',
          materialName: 'Ngô hạt',
          avgPrice: 7400,
          minPrice: 7400,
          maxPrice: 7400,
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

    it('reuses the price-difference callout for the received-date buckets', async () => {
      dashboardApiMock.getQuotifyPriceTrends.mockImplementation(async (query) => ({
        ...priceTrends,
        points: [
          {
            ...priceTrends.points[0],
            receivedDate: '2026-01-05',
            convertedPriceVndPerKg: query.materialId === 'material-1' ? 7200 : 9450,
          },
        ],
      }))

      const page = useDashboardPage()
      page.materials.value = [
        { ...page.materials.value[0], id: 'material-1', name: 'Ngô hạt' },
        { ...page.materials.value[0], id: 'material-2', name: 'Khô đậu nành' },
      ]
      page.historyMaterialIds.value = ['material-1', 'material-2']
      page.historyDeliveryMonth.value = new Date(2026, 11, 1)

      await page.loadPriceHistory()

      expect(page.historyBuckets.value[0].differenceLines).toEqual([
        'Khô đậu nành cao hơn Ngô hạt: +2,250.00 VNĐ/KG (+31.25%)',
      ])
    })

    it('builds one chart dataset per loaded material for the received-date x-axis', async () => {
      dashboardApiMock.getQuotifyPriceTrends.mockImplementation(async (query) => ({
        ...priceTrends,
        points: [
          {
            ...priceTrends.points[0],
            receivedDate: '2026-01-05',
            convertedPriceVndPerKg: query.materialId === 'material-1' ? 7200 : 9450,
          },
        ],
      }))

      const page = useDashboardPage()
      page.materials.value = [
        { ...page.materials.value[0], id: 'material-1', name: 'Ngô hạt' },
        { ...page.materials.value[0], id: 'material-2', name: 'Khô đậu nành' },
      ]
      page.historyMaterialIds.value = ['material-1', 'material-2']
      page.historyDeliveryMonth.value = new Date(2026, 11, 1)
      await page.loadPriceHistory()
      page.historyBandVisibility.value['material-1'] = false
      page.historyBandVisibility.value['material-2'] = false

      expect(page.historyChartData.value.labels).toEqual(['01/01/2026'])
      expect(page.historyChartData.value.datasets).toHaveLength(2)
      expect(page.historyChartData.value.datasets[0]).toMatchObject({
        label: 'Ngô hạt',
        data: [7200],
      })
      expect(page.historyChartData.value.datasets[1]).toMatchObject({
        label: 'Khô đậu nành',
        data: [9450],
      })
    })

    it('renders the tooltip from its own received-date buckets, not the delivery-month comparison buckets', async () => {
      dashboardApiMock.getQuotifyPriceTrends.mockImplementation(async (query) => ({
        ...priceTrends,
        points: [
          {
            ...priceTrends.points[0],
            receivedDate: '2026-01-05',
            convertedPriceVndPerKg: query.materialId === 'material-1' ? 7200 : 9450,
          },
        ],
      }))

      const page = useDashboardPage()
      page.materials.value = [
        { ...page.materials.value[0], id: 'material-1', name: 'Ngô hạt' },
        { ...page.materials.value[0], id: 'material-2', name: 'Khô đậu nành' },
      ]
      page.historyMaterialIds.value = ['material-1', 'material-2']
      page.historyDeliveryMonth.value = new Date(2026, 11, 1)
      await page.loadPriceHistory()

      // comparisonBuckets (the sibling "so sánh theo kỳ hàng về" chart) stays
      // empty here on purpose — the tooltip must read from this chart's own
      // historyBuckets, not fall back to the sibling chart's buckets.
      expect(page.comparisonBuckets.value).toEqual([])

      const canvas = document.createElement('canvas')
      document.createElement('div').appendChild(canvas)
      page.historyChartOptions.value.plugins.tooltip.external({
        chart: { canvas },
        tooltip: {
          opacity: 1,
          title: ['01/2026'],
          dataPoints: [{ dataIndex: 0 }],
          caretX: 10,
          caretY: 10,
        },
      })

      const tooltipEl = canvas.parentElement?.querySelector('.quotify-chart-tooltip')
      expect(tooltipEl?.textContent).toContain('Ngô hạt')
      expect(tooltipEl?.textContent).toContain('Khô đậu nành')
    })

    it('clicking a point navigates to /quotes with the ~10-day received-date range of that kỳ, not the whole month', async () => {
      dashboardApiMock.getQuotifyPriceTrends.mockImplementation(async (query) => ({
        ...priceTrends,
        points: [
          {
            ...priceTrends.points[0],
            receivedDate: '2026-01-15',
            convertedPriceVndPerKg: query.materialId === 'material-1' ? 7200 : 9450,
          },
        ],
      }))

      const page = useDashboardPage()
      page.materials.value = [
        { ...page.materials.value[0], id: 'material-1', name: 'Ngô hạt' },
        { ...page.materials.value[0], id: 'material-2', name: 'Khô đậu nành' },
      ]
      page.historyMaterialIds.value = ['material-1', 'material-2']
      page.historyDeliveryMonth.value = new Date(2026, 11, 1)
      await page.loadPriceHistory()

      page.historyChartOptions.value.onClick(null, [{ index: 0, datasetIndex: 0 }])

      expect(pushMock).toHaveBeenCalledWith({
        path: '/quotes',
        query: {
          materialId: 'material-1',
          deliveryMonth: '2026-12-01',
          receivedDateStart: '2026-01-11',
          receivedDateEnd: '2026-01-20',
        },
      })
    })
  })

  describe('seasonal comparison across years for a fixed material and month', () => {
    it('does not fetch without a material, a month, and at least 2 years selected', async () => {
      const page = useDashboardPage()

      page.seasonalMaterialId.value = 'material-1'
      page.seasonalMonth.value = 10
      page.seasonalYears.value = [2026]
      await page.loadSeasonalComparison()
      expect(dashboardApiMock.getQuotifyPriceTrends).not.toHaveBeenCalled()
      expect(page.seasonalBuckets.value).toEqual([])

      page.seasonalYears.value = [2025, 2026]
      page.seasonalMonth.value = null
      await page.loadSeasonalComparison()
      expect(dashboardApiMock.getQuotifyPriceTrends).not.toHaveBeenCalled()

      page.seasonalMonth.value = 10
      page.seasonalMaterialId.value = null
      await page.loadSeasonalComparison()
      expect(dashboardApiMock.getQuotifyPriceTrends).not.toHaveBeenCalled()
    })

    it('fetches each selected year with the fixed material and month, in parallel', async () => {
      const page = useDashboardPage()
      page.seasonalMaterialId.value = 'material-1'
      page.seasonalMonth.value = 10
      page.seasonalYears.value = [2025, 2026]

      await page.loadSeasonalComparison()

      expect(dashboardApiMock.getQuotifyPriceTrends).toHaveBeenCalledTimes(2)
      expect(dashboardApiMock.getQuotifyPriceTrends).toHaveBeenCalledWith(
        { materialId: 'material-1', deliveryMonth: '2025-10-01' },
        'mock-access-token',
      )
      expect(dashboardApiMock.getQuotifyPriceTrends).toHaveBeenCalledWith(
        { materialId: 'material-1', deliveryMonth: '2026-10-01' },
        'mock-access-token',
      )
    })

    it('splits each month into 3 finer buckets (kỳ 1: ngày 1-10, kỳ 2: 11-20, kỳ 3: 21-cuối tháng)', async () => {
      dashboardApiMock.getQuotifyPriceTrends.mockImplementation(async () => ({
        ...priceTrends,
        points: [
          { ...priceTrends.points[0], receivedDate: '2023-11-05', deliveryMonth: '2024-10-01', convertedPriceVndPerKg: 6800 },
          { ...priceTrends.points[0], receivedDate: '2023-11-25', deliveryMonth: '2024-10-01', convertedPriceVndPerKg: 7000 },
          { ...priceTrends.points[0], receivedDate: '2023-11-15', deliveryMonth: '2024-10-01', convertedPriceVndPerKg: 6900 },
        ],
      }))

      const page = useDashboardPage()
      page.seasonalMaterialId.value = 'material-1'
      page.seasonalMonth.value = 10
      page.seasonalYears.value = [2024, 2025]

      await page.loadSeasonalComparison()

      // Nhãn trục X (bucket.label) chỉ hiện tháng tương đối, không hiện kỳ —
      // nếu hiện, Chart.js autoSkip (bước nhảy ~3, khớp đúng 3 bucket/tháng)
      // sẽ khiến MỌI tick còn hiển thị vô tình rơi vào cùng 1 kỳ, trông như
      // lỗi (đã gặp thật, user báo "nhãn trục X toàn ghi kỳ 2" ngày
      // 13/08/2026). Kỳ cụ thể vẫn phân biệt được qua `groupKey` (dùng ở
      // tooltip qua formatSeriesRowLabel, xem test tooltip bên dưới).
      expect(page.seasonalBuckets.value.map((bucket) => bucket.label)).toEqual(['T-11', 'T-11', 'T-11'])
      expect(page.seasonalBuckets.value.map((bucket) => bucket.groupKey)).toEqual(['-33', '-32', '-31'])
      expect(page.seasonalBuckets.value.map((bucket) => bucket.series[0].avgPrice)).toEqual([6800, 6900, 7000])
    })

    it('groups months-before-delivery buckets sorted numerically, not lexically, across double-digit offsets', async () => {
      // Kỳ hàng về 10/2024: điểm nhận ngày 25/11/2023 (T-11, kỳ 3, khóa nhóm
      // số học "-31") phải xếp TRƯỚC điểm nhận ngày 05/12/2023 (T-10, kỳ 1,
      // khóa "-30") — nếu sắp theo localeCompare (chuỗi) thay vì số học,
      // "-30" < "-31" (so ký tự '0'<'1' ở vị trí thứ 3), cho thứ tự SAI.
      dashboardApiMock.getQuotifyPriceTrends.mockImplementation(async () => ({
        ...priceTrends,
        points: [
          { ...priceTrends.points[0], receivedDate: '2023-12-05', deliveryMonth: '2024-10-01', convertedPriceVndPerKg: 7000 },
          { ...priceTrends.points[0], receivedDate: '2023-11-25', deliveryMonth: '2024-10-01', convertedPriceVndPerKg: 6800 },
        ],
      }))

      const page = useDashboardPage()
      page.seasonalMaterialId.value = 'material-1'
      page.seasonalMonth.value = 10
      page.seasonalYears.value = [2024, 2025]

      await page.loadSeasonalComparison()

      expect(page.seasonalBuckets.value.map((bucket) => bucket.groupKey)).toEqual(['-31', '-30'])
      expect(page.seasonalBuckets.value.map((bucket) => bucket.label)).toEqual(['T-11', 'T-10'])
    })

    it('reuses the price-difference callout to compare years at the same offset', async () => {
      dashboardApiMock.getQuotifyPriceTrends.mockImplementation(async (query) => ({
        ...priceTrends,
        points: [
          {
            ...priceTrends.points[0],
            receivedDate: '2026-09-05',
            deliveryMonth: '2026-10-01',
            convertedPriceVndPerKg: query.deliveryMonth === '2026-10-01' ? 7200 : 6800,
          },
        ],
      }))

      const page = useDashboardPage()
      page.seasonalMaterialId.value = 'material-1'
      page.seasonalMonth.value = 10
      page.seasonalYears.value = [2025, 2026]

      await page.loadSeasonalComparison()

      expect(page.seasonalBuckets.value[0].differenceLines).toEqual(['2026 cao hơn 2025: +400.00 VNĐ/KG (+5.88%)'])
    })

    it('builds one chart dataset per selected year, labeled by year', async () => {
      dashboardApiMock.getQuotifyPriceTrends.mockImplementation(async (query) => ({
        ...priceTrends,
        points: [
          {
            ...priceTrends.points[0],
            receivedDate: '2026-09-05',
            deliveryMonth: '2026-10-01',
            convertedPriceVndPerKg: query.deliveryMonth === '2026-10-01' ? 7200 : 6800,
          },
        ],
      }))

      const page = useDashboardPage()
      page.seasonalMaterialId.value = 'material-1'
      page.seasonalMonth.value = 10
      page.seasonalYears.value = [2025, 2026]
      await page.loadSeasonalComparison()
      page.seasonalBandVisibility.value['2025'] = false
      page.seasonalBandVisibility.value['2026'] = false

      expect(page.seasonalChartData.value.labels).toEqual(['T-1'])
      expect(page.seasonalChartData.value.datasets).toHaveLength(2)
      expect(page.seasonalChartData.value.datasets[0]).toMatchObject({ label: '2025', data: [6800] })
      expect(page.seasonalChartData.value.datasets[1]).toMatchObject({ label: '2026', data: [7200] })
    })

    it('gives every year a distinct line color, even at the max of 5 selected years', async () => {
      dashboardApiMock.getQuotifyPriceTrends.mockResolvedValue({
        ...priceTrends,
        points: [{ ...priceTrends.points[0], receivedDate: '2026-09-05', deliveryMonth: '2026-10-01' }],
      })

      const page = useDashboardPage()
      page.seasonalMaterialId.value = 'material-1'
      page.seasonalMonth.value = 10
      page.seasonalYears.value = [2022, 2023, 2024, 2025, 2026]
      await page.loadSeasonalComparison()
      for (const year of page.seasonalYears.value) {
        page.seasonalBandVisibility.value[String(year)] = false
      }

      const colors = page.seasonalChartData.value.datasets.map((dataset) => dataset.borderColor)
      expect(colors).toHaveLength(5)
      expect(new Set(colors).size).toBe(5)
    })

    it('renders the tooltip from its own seasonal buckets, showing each year with its real calendar month', async () => {
      dashboardApiMock.getQuotifyPriceTrends.mockImplementation(async (query) => ({
        ...priceTrends,
        points: [
          {
            ...priceTrends.points[0],
            receivedDate: query.deliveryMonth === '2026-10-01' ? '2026-09-05' : '2025-09-05',
            deliveryMonth: query.deliveryMonth,
            convertedPriceVndPerKg: query.deliveryMonth === '2026-10-01' ? 7200 : 6800,
          },
        ],
      }))

      const page = useDashboardPage()
      page.seasonalMaterialId.value = 'material-1'
      page.seasonalMonth.value = 10
      page.seasonalYears.value = [2025, 2026]
      await page.loadSeasonalComparison()

      // comparisonBuckets/historyBuckets (2 chart khác) phải rỗng — tooltip
      // phải đọc từ seasonalBuckets của chính chart này, không rơi vào bẫy
      // đã gặp thật (đọc nhầm state chart khác sau khi tổng quát hóa).
      expect(page.comparisonBuckets.value).toEqual([])
      expect(page.historyBuckets.value).toEqual([])

      const canvas = document.createElement('canvas')
      document.createElement('div').appendChild(canvas)
      page.seasonalChartOptions.value.plugins.tooltip.external({
        chart: { canvas },
        tooltip: {
          opacity: 1,
          title: ['T-1'],
          dataPoints: [{ dataIndex: 0 }],
          caretX: 10,
          caretY: 10,
        },
      })

      const tooltipText = canvas.parentElement?.querySelector('.quotify-chart-tooltip')?.textContent
      expect(tooltipText).toContain('2025 (09/2025, kỳ 1)')
      expect(tooltipText).toContain('2026 (09/2026, kỳ 1)')
    })

    it('clicking a point navigates to /quotes with the fixed material, that year\'s delivery month, and the real received-date range for that offset', async () => {
      dashboardApiMock.getQuotifyPriceTrends.mockImplementation(async (query) => ({
        ...priceTrends,
        points: [
          {
            ...priceTrends.points[0],
            receivedDate: '2026-09-05',
            deliveryMonth: query.deliveryMonth,
            convertedPriceVndPerKg: 7200,
          },
        ],
      }))

      const page = useDashboardPage()
      page.seasonalMaterialId.value = 'material-1'
      page.seasonalMonth.value = 10
      page.seasonalYears.value = [2025, 2026]
      await page.loadSeasonalComparison()

      page.seasonalChartOptions.value.onClick(null, [{ index: 0, datasetIndex: 1 }])

      expect(pushMock).toHaveBeenCalledWith({
        path: '/quotes',
        query: {
          materialId: 'material-1',
          deliveryMonth: '2026-10-01',
          receivedDateStart: '2026-09-01',
          receivedDateEnd: '2026-09-10',
        },
      })
    })

    it('offers the 5 most recent years, including the current one, as selectable options', () => {
      vi.useFakeTimers()
      vi.setSystemTime(new Date(2026, 7, 13))

      const page = useDashboardPage()

      expect(page.seasonalAvailableYears.value).toEqual([2026, 2025, 2024, 2023, 2022])

      vi.useRealTimers()
    })
  })
})
