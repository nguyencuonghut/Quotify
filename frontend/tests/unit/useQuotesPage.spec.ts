import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useQuotesPage } from '@/composables/useQuotesPage'
import { useAuthStore } from '@/stores/auth.store'

const quotesApiMock = vi.hoisted(() => ({
  getQuotesList: vi.fn(),
  listSuppliers: vi.fn(),
  listMaterials: vi.fn(),
  listMaterialTypesLookup: vi.fn(),
}))

vi.mock('@/api/quotes.api', () => ({
  getQuotesList: quotesApiMock.getQuotesList,
}))

describe('useQuotesPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()

    const authStore = useAuthStore()
    authStore.accessToken = 'mock-token'
  })

  it('initializes filter and state variables correctly', () => {
    const page = useQuotesPage('mock-token')

    expect(page.items.value).toEqual([])
    expect(page.total.value).toBe(0)
    expect(page.isLoading.value).toBe(false)
    expect(page.globalSearch.value).toBe('')
    expect(page.supplierId.value).toBeNull()
    expect(page.materialId.value).toBeNull()
    expect(page.sortField.value).toBe('created_at')
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

    const page = useQuotesPage('mock-token')
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
        sortBy: 'created_at',
        sortOrder: 'desc',
      }),
      'mock-token',
    )

    expect(page.items.value).toEqual(mockRes.items)
    expect(page.total.value).toBe(1)
  })

  it('can reset filters and reload list', async () => {
    quotesApiMock.getQuotesList.mockResolvedValue({ items: [], total: 0 })

    const page = useQuotesPage('mock-token')
    page.globalSearch.value = 'Text'
    page.purchased.value = true

    page.resetFilters()

    expect(page.globalSearch.value).toBe('')
    expect(page.purchased.value).toBeNull()
    expect(quotesApiMock.getQuotesList).toHaveBeenCalledWith(
      expect.objectContaining({
        limit: 10,
        offset: 0,
        sortBy: 'created_at',
        sortOrder: 'desc',
      }),
      'mock-token',
    )
  })
})
