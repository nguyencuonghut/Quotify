import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useDashboardPage } from '@/composables/useDashboardPage'
import { useAuthStore } from '@/stores/auth.store'

const dashboardApiMock = vi.hoisted(() => ({
  getQuotifyEntryKpis: vi.fn(),
  getQuotifyPriceTrends: vi.fn(),
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
    expect(page.materials.value).toHaveLength(1)
    expect(page.selectedMaterialId.value).toBe('material-1')
    expect(page.userKpis.value[0].quoteCount).toBe(7)
    expect(page.metricCards.value.map((card) => card.label)).toEqual([
      'Giá thấp nhất',
      'Giá cao nhất',
      'Giá trung bình',
      'Tổng báo giá',
    ])
    expect(page.metricCards.value[0].value).toBe('10.200,00 VNĐ/KG')
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
})
