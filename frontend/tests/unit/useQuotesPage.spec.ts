import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useQuotesPage } from '@/composables/useQuotesPage'
import { useAuthStore } from '@/stores/auth.store'
import { ApiError } from '@/api/http'

const quotesApiMock = vi.hoisted(() => ({
  getQuotesList: vi.fn(),
  listSuppliers: vi.fn(),
  listMaterials: vi.fn(),
  listMaterialTypesLookup: vi.fn(),
  downloadQuotesExport: vi.fn(),
}))

vi.mock('@/api/quotes.api', () => ({
  getQuotesList: quotesApiMock.getQuotesList,
  downloadQuotesExport: quotesApiMock.downloadQuotesExport,
}))

describe('useQuotesPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()

    const authStore = useAuthStore()
    authStore.accessToken = 'mock-token'
  })

  it('initializes filter and state variables correctly', () => {
    const page = useQuotesPage(() => 'mock-token')

    expect(page.items.value).toEqual([])
    expect(page.total.value).toBe(0)
    expect(page.isLoading.value).toBe(false)
    expect(page.globalSearch.value).toBe('')
    expect(page.supplierId.value).toBeNull()
    expect(page.materialId.value).toBeNull()
    expect(page.sortField.value).toBe('received_date')
    expect(page.sortOrder.value).toBe('desc')
  })

  it('can fetch flat quotes list from API with active parameters', async () => {
    const mockRes = {
      items: [
        {
          id: 'line-1',
          quoteId: 'quote-1',
          quoteVersionId: 'version-1',
          supplierId: 'supp-1',
          supplierName: 'Supp A',
          supplierCode: 'SA',
          materialId: 'mat-1',
          materialName: 'Corn',
          materialCode: 'MC',
          materialTypeName: 'NL',
          materialTypeCode: 'NL',
          receivedDate: '2026-07-29',
          deliveryMonth: '2026-08-01',
          priceOriginal: 250,
          currency: 'USD',
          unit: 'MT',
          exchangeRate: 25450,
          exchangeRateSource: 'VCB',
          importTaxRatePercent: 0,
          processingCostVndPerKg: 150,
          priceConvertedVndPerKg: 6525.23,
          purchased: true,
          versionNumber: 1,
          versionStatus: 'confirmed',
          createdByName: 'Admin',
          createdAt: '2026-07-29T00:00:00Z',
        },
      ],
      total: 1,
    }

    quotesApiMock.getQuotesList.mockResolvedValue(mockRes)

    const page = useQuotesPage(() => 'mock-token')
    page.globalSearch.value = 'Supp A'
    page.supplierId.value = 'supp-1'
    page.purchased.value = true

    await page.loadQuotesData()

    expect(quotesApiMock.getQuotesList).toHaveBeenCalledWith(
      expect.objectContaining({
        globalSearch: 'Supp A',
        supplierId: 'supp-1',
        purchased: true,
        limit: 10,
        offset: 0,
        sortBy: 'received_date',
        sortOrder: 'desc',
      }),
      'mock-token',
    )

    expect(page.items.value).toEqual(mockRes.items)
    expect(page.total.value).toBe(1)
  })

  it('can reset filters and reload list', async () => {
    quotesApiMock.getQuotesList.mockResolvedValue({ items: [], total: 0 })

    const page = useQuotesPage(() => 'mock-token')
    page.globalSearch.value = 'Text'
    page.purchased.value = true

    page.resetFilters()

    expect(page.globalSearch.value).toBe('')
    expect(page.purchased.value).toBeNull()
    expect(quotesApiMock.getQuotesList).toHaveBeenCalledWith(
      expect.objectContaining({
        limit: 10,
        offset: 0,
        sortBy: 'received_date',
        sortOrder: 'desc',
      }),
      'mock-token',
    )
  })

  it('reads the access token live on every call, instead of a stale snapshot from creation', async () => {
    quotesApiMock.getQuotesList.mockResolvedValue({ items: [], total: 0 })

    const authStore = useAuthStore()
    const page = useQuotesPage(() => authStore.accessToken)

    // Token rotates (e.g. after a silent refresh) sau khi composable đã tạo —
    // request tiếp theo phải dùng token MỚI, không phải token chụp lúc tạo.
    authStore.accessToken = 'renewed-token'
    await page.loadQuotesData()

    expect(quotesApiMock.getQuotesList).toHaveBeenCalledWith(
      expect.any(Object),
      'renewed-token',
    )
  })

  it('shows a friendly session-expired message instead of the raw backend 401 detail', async () => {
    quotesApiMock.getQuotesList.mockRejectedValue(
      new ApiError('Invalid authentication credentials.', 401),
    )

    const page = useQuotesPage(() => 'mock-token')
    await page.loadQuotesData()

    expect(page.errorMsg.value).toBe(
      'Phiên đăng nhập đã hết hạn, vui lòng tải lại trang.',
    )
  })

  it('exports quotes to Excel using the currently applied filters', async () => {
    quotesApiMock.downloadQuotesExport.mockResolvedValue(undefined)

    const page = useQuotesPage(() => 'mock-token')
    page.supplierId.value = 'supp-1'
    page.purchased.value = true

    expect(page.isExporting.value).toBe(false)
    await page.exportQuotes()

    expect(quotesApiMock.downloadQuotesExport).toHaveBeenCalledWith(
      expect.objectContaining({ supplierId: 'supp-1', purchased: true }),
      'mock-token',
    )
    expect(page.isExporting.value).toBe(false)
  })

  it('shows a friendly message when the export request fails', async () => {
    quotesApiMock.downloadQuotesExport.mockRejectedValue(
      new ApiError('Invalid authentication credentials.', 401),
    )

    const page = useQuotesPage(() => 'mock-token')
    await page.exportQuotes()

    expect(page.errorMsg.value).toBe(
      'Phiên đăng nhập đã hết hạn, vui lòng tải lại trang.',
    )
    expect(page.isExporting.value).toBe(false)
  })
})
