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
      priceOriginal: 10500,
      currency: 'VND',
      unit: 'KG',
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
      priceOriginal: 11500,
      currency: 'VND',
      unit: 'KG',
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
      priceOriginal: 12000,
      currency: 'VND',
      unit: 'KG',
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
        // Mặc định khoảng ngày nhận báo giá = 6 tháng gần nhất (hôm nay
        // 13/08/2026 → từ 13/02/2026), không còn để trống như trước.
        receivedDateStart: '2026-02-13',
        receivedDateEnd: '2026-08-13',
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
    // Mỗi ngày nhận báo giá riêng biệt là 1 điểm (giá THẤP NHẤT trong ngày
    // đó) — 3 điểm mẫu ở 3 ngày khác nhau (07-20, 07-22, 07-25) nên ra 3
    // điểm, sắp theo thứ tự thời gian tăng dần.
    expect(page.periodDailyPoints.value.map((entry) => entry.date)).toEqual([
      '2026-07-20',
      '2026-07-22',
      '2026-07-25',
    ])
    expect(page.periodDailyPoints.value.map((entry) => entry.price)).toEqual([
      10500, 11500, 12000,
    ])
    expect(page.chartData.value.labels).toEqual([
      '2026-07-20',
      '2026-07-22',
      '2026-07-25',
    ])
    expect(page.chartData.value.datasets.map((dataset) => dataset.label)).toEqual([
      'Giá thấp nhất trong ngày',
    ])
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

  it('clicking a point on the "Giá theo kỳ hàng về" chart navigates to /quotes with the fixed delivery month and the clicked day', async () => {
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
        receivedDateStart: '2026-07-20',
        receivedDateEnd: '2026-07-20',
      },
    })
  })

  it('ticking "Giá CNF" keeps only USD/MT quotes and switches the chart to their original USD price', async () => {
    dashboardApiMock.getQuotifyPriceTrends.mockResolvedValue({
      ...priceTrends,
      points: [
        {
          ...priceTrends.points[0],
          lineId: 'line-vnd',
          currency: 'VND',
          unit: 'KG',
          convertedPriceVndPerKg: 7000,
          priceOriginal: 7000,
        },
        {
          ...priceTrends.points[0],
          lineId: 'line-usd-1',
          currency: 'USD',
          unit: 'MT',
          convertedPriceVndPerKg: 11000,
          priceOriginal: 400,
          purchased: false,
        },
        {
          ...priceTrends.points[0],
          lineId: 'line-usd-2',
          currency: 'USD',
          unit: 'MT',
          convertedPriceVndPerKg: 11500,
          priceOriginal: 420,
          purchased: false,
        },
      ],
    })

    const page = useDashboardPage()
    await page.bootstrap()

    // Cả 3 điểm mẫu cùng nhận 1 ngày (đều spread từ `priceTrends.points[0]`)
    // — chưa tick "Giá CNF" thì lấy giá quy đổi VNĐ/KG, MIN trong ngày là
    // điểm VND/KG (7000).
    expect(page.periodDailyPoints.value).toHaveLength(1)
    expect(page.periodDailyPoints.value[0]).toMatchObject({ price: 7000 })

    // Tick "Giá CNF" chỉ lọc lại dữ liệu ĐÃ CÓ ở client — không cần gọi lại
    // API — nên điểm MIN trong ngày phải đổi ngay, phản ứng thuần theo
    // `showCnfOnly` (giờ chỉ còn 2 điểm USD/MT, MIN là giá gốc 400).
    page.showCnfOnly.value = true

    expect(page.periodDailyPoints.value).toHaveLength(1)
    expect(page.periodDailyPoints.value[0]).toMatchObject({ price: 400 })
  })

  it('formats the "Giá theo kỳ hàng về" period stats and chart data in USD when "Giá CNF" is ticked', async () => {
    dashboardApiMock.getQuotifyPriceTrends.mockResolvedValue({
      ...priceTrends,
      points: [
        {
          ...priceTrends.points[0],
          lineId: 'line-usd-1',
          currency: 'USD',
          unit: 'MT',
          convertedPriceVndPerKg: 11000,
          priceOriginal: 400,
          purchased: true,
        },
      ],
    })

    const page = useDashboardPage()
    await page.bootstrap()
    page.showCnfOnly.value = true

    expect(page.periodStatsFormatted.value.avg).toBe('$400.00 USD/MT')
    expect(page.chartData.value.datasets[0].data).toEqual([400])
  })

  it('shows a floating box with the received date and price when hovering a point on the "Giá theo kỳ hàng về" chart', async () => {
    const page = useDashboardPage()
    await page.bootstrap()

    const canvas = document.createElement('canvas')
    document.createElement('div').appendChild(canvas)
    page.chartOptions.value.plugins.tooltip.external({
      chart: { canvas },
      tooltip: {
        opacity: 1,
        dataPoints: [{ dataIndex: 0 }],
        caretX: 10,
        caretY: 10,
      },
    })

    const tooltipText = canvas.parentElement?.querySelector('.quotify-chart-tooltip')?.textContent
    // Điểm đầu tiên (index 0) là ngày 20/07/2026, giá thấp nhất trong ngày
    // 10500 — xem `periodDailyPoints` ở test bootstrap phía trên.
    expect(tooltipText).toContain('20/07/2026')
    expect(tooltipText).toContain('10,500.00 VNĐ/KG')
  })

  it('sends selected material, month and received date filters to dashboard APIs', async () => {
    const page = useDashboardPage()

    page.selectedMaterialId.value = 'material-1'
    page.deliveryMonth.value = new Date(2026, 7, 1)
    page.receivedDateStart.value = new Date(2026, 6, 1)
    page.receivedDateEnd.value = new Date(2026, 6, 31)

    await page.applyFilters()

    const expectedQuery = {
      materialId: 'material-1',
      deliveryMonth: '2026-08-01',
      receivedDateStart: '2026-07-01',
      receivedDateEnd: '2026-07-31',
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
    // "Xóa lọc" đưa kỳ giao hàng về lại mặc định (tháng hiện tại + 2), không
    // phải rỗng — chart này luôn cần 1 kỳ giao hàng cố định.
    expect(page.deliveryMonth.value).toEqual(new Date(2026, 9, 1))
    // "Xóa lọc" cũng đưa khoảng ngày nhận báo giá về lại mặc định 6 tháng
    // gần nhất, không phải để trống như trước.
    expect(page.periodRangeKey.value).toBe('6m')
    expect(dashboardApiMock.getQuotifyEntryKpis).toHaveBeenCalledWith(
      {
        materialId: 'material-1',
        deliveryMonth: '2026-10-01',
        receivedDateStart: '2026-02-13',
        receivedDateEnd: '2026-08-13',
      },
      'mock-access-token',
    )

    vi.useRealTimers()
  })

  it('clicking a period-range quick button sets the received-date filters to that range and reloads', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 7, 20))

    const page = useDashboardPage()
    page.selectedMaterialId.value = 'material-1'
    page.deliveryMonth.value = new Date(2026, 9, 1)

    await page.applyPeriodRange('1m')

    expect(page.periodRangeKey.value).toBe('1m')
    expect(page.receivedDateStart.value).toEqual(new Date(2026, 6, 20))
    expect(page.receivedDateEnd.value).toEqual(new Date(2026, 7, 20))
    expect(dashboardApiMock.getQuotifyEntryKpis).toHaveBeenCalledWith(
      {
        materialId: 'material-1',
        deliveryMonth: '2026-10-01',
        receivedDateStart: '2026-07-20',
        receivedDateEnd: '2026-08-20',
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

    it('ticking "Giá CNF" on this chart keeps only USD/MT quotes and uses their original USD price for the buckets', async () => {
      dashboardApiMock.getQuotifyPriceTrends.mockImplementation(async (query) => {
        if (query.materialId === 'material-1') {
          return {
            ...priceTrends,
            points: [
              { ...priceTrends.points[0], receivedDate: '2026-01-05', currency: 'VND', unit: 'KG', convertedPriceVndPerKg: 7000, priceOriginal: 7000 },
              { ...priceTrends.points[0], receivedDate: '2026-01-06', currency: 'USD', unit: 'MT', convertedPriceVndPerKg: 11000, priceOriginal: 400 },
            ],
          }
        }
        return {
          ...priceTrends,
          points: [
            { ...priceTrends.points[0], receivedDate: '2026-01-07', currency: 'USD', unit: 'MT', convertedPriceVndPerKg: 11500, priceOriginal: 420 },
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

      expect(page.historyBuckets.value).toHaveLength(1)

      page.historyShowCnfOnly.value = true

      expect(page.historyBuckets.value).toHaveLength(1)
      expect(page.historyBuckets.value[0].series).toEqual([
        {
          materialId: 'material-1',
          materialName: 'Ngô hạt',
          avgPrice: 400,
          minPrice: 400,
          maxPrice: 400,
          pointCount: 1,
        },
        {
          materialId: 'material-2',
          materialName: 'Khô đậu nành',
          avgPrice: 420,
          minPrice: 420,
          maxPrice: 420,
          pointCount: 1,
        },
      ])
    })

    it('formats the tooltip price range in USD/MT when "Giá CNF" is ticked on this chart', async () => {
      dashboardApiMock.getQuotifyPriceTrends.mockImplementation(async () => ({
        ...priceTrends,
        points: [
          { ...priceTrends.points[0], receivedDate: '2026-01-05', currency: 'USD', unit: 'MT', convertedPriceVndPerKg: 11000, priceOriginal: 400 },
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
      page.historyShowCnfOnly.value = true

      page.historyChartOptions.value.plugins.tooltip.external({
        tooltip: {
          opacity: 1,
          title: ['01/2026'],
          dataPoints: [{ dataIndex: 0 }],
        },
      })

      const unitLabels = page.historyHoverInfo.value?.rows.map((row) => row.metrics?.unitLabel)
      expect(unitLabels).toContain('USD/MT')
      expect(unitLabels).not.toContain('VNĐ/KG')
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
        {
          label: 'Khô đậu nành cao hơn Ngô hạt',
          diffValue: '+2,250.00 VNĐ/KG',
          percent: '+31.25%',
        },
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

      page.historyChartOptions.value.plugins.tooltip.external({
        tooltip: {
          opacity: 1,
          title: ['01/2026'],
          dataPoints: [{ dataIndex: 0 }],
        },
      })

      const hoverText = page.historyHoverInfo.value?.rows.map((row) => row.label).join(' ')
      expect(hoverText).toContain('Ngô hạt')
      expect(hoverText).toContain('Khô đậu nành')
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

    it('ticking "Giá CNF" on this chart keeps only USD/MT quotes and uses their original USD price for the buckets', async () => {
      dashboardApiMock.getQuotifyPriceTrends.mockImplementation(async (query) => ({
        ...priceTrends,
        points: [
          {
            ...priceTrends.points[0],
            receivedDate: '2023-11-05',
            deliveryMonth: '2024-10-01',
            currency: query.deliveryMonth === '2024-10-01' ? 'USD' : 'VND',
            unit: query.deliveryMonth === '2024-10-01' ? 'MT' : 'KG',
            convertedPriceVndPerKg: query.deliveryMonth === '2024-10-01' ? 11000 : 6800,
            priceOriginal: query.deliveryMonth === '2024-10-01' ? 400 : 6800,
          },
        ],
      }))

      const page = useDashboardPage()
      page.seasonalMaterialId.value = 'material-1'
      page.seasonalMonth.value = 10
      page.seasonalYears.value = [2024, 2025]

      await page.loadSeasonalComparison()

      expect(page.seasonalBuckets.value).toHaveLength(1)

      page.seasonalShowCnfOnly.value = true

      expect(page.seasonalBuckets.value).toHaveLength(1)
      expect(page.seasonalBuckets.value[0].series).toEqual([
        { materialId: '2024', materialName: '2024', avgPrice: 400, minPrice: 400, maxPrice: 400, pointCount: 1 },
        { materialId: '2025', materialName: '2025', avgPrice: null, minPrice: null, maxPrice: null, pointCount: 0 },
      ])
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

      expect(page.seasonalBuckets.value[0].differenceLines).toEqual([
        { label: '2026 cao hơn 2025', diffValue: '+400.00 VNĐ/KG', percent: '+5.88%' },
      ])
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

      // historyBuckets (chart khác) phải rỗng — tooltip phải đọc từ
      // seasonalBuckets của chính chart này, không rơi vào bẫy đã gặp thật
      // (đọc nhầm state chart khác sau khi tổng quát hóa).
      expect(page.historyBuckets.value).toEqual([])

      page.seasonalChartOptions.value.plugins.tooltip.external({
        tooltip: {
          opacity: 1,
          title: ['T-1'],
          dataPoints: [{ dataIndex: 0 }],
        },
      })

      const hoverText = page.seasonalHoverInfo.value?.rows.map((row) => row.label).join(' ')
      expect(hoverText).toContain('2025 (09/2025, kỳ 1)')
      expect(hoverText).toContain('2026 (09/2026, kỳ 1)')
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
