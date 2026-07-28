import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useQuoteEditor } from '@/composables/useQuoteEditor'
import { useAuthStore } from '@/stores/auth.store'

const exchangeRatesApiMock = vi.hoisted(() => ({
  getUsdSellRateToday: vi.fn(),
}))

const quotifySettingsApiMock = vi.hoisted(() => ({
  getQuotifySettings: vi.fn(),
}))

const suppliersApiMock = vi.hoisted(() => ({
  getSupplier: vi.fn(),
}))

vi.mock('@/api/exchange-rates.api', () => exchangeRatesApiMock)
vi.mock('@/api/quotify-settings.api', () => quotifySettingsApiMock)
vi.mock('@/api/suppliers.api', () => suppliersApiMock)

describe('useQuoteEditor', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()

    const authStore = useAuthStore()
    authStore.accessToken = 'mock-token'
  })

  it('initializes state correctly', () => {
    const editor = useQuoteEditor('mock-token')

    expect(editor.supplierId.value).toBeNull()
    expect(editor.receivedDate.value).toBeDefined()
    expect(editor.isBackfilled.value).toBe(false)
    expect(editor.backfillReason.value).toBeNull()
    expect(editor.lines.value).toEqual([])
  })

  it('can add and remove lines', () => {
    const editor = useQuoteEditor('mock-token')
    
    editor.addLine()
    expect(editor.lines.value).toHaveLength(1)
    expect(editor.lines.value[0].currency).toBe('VND')
    expect(editor.lines.value[0].unit).toBe('KG')

    editor.addLine()
    expect(editor.lines.value).toHaveLength(2)

    editor.removeLine(0)
    expect(editor.lines.value).toHaveLength(1)
  })

  it('performs calculations of preview price correctly', async () => {
    // Setup Mock settings
    quotifySettingsApiMock.getQuotifySettings.mockResolvedValue({
      id: 'settings-1',
      conversionCostVndPerKg: '250.00',
    })

    const editor = useQuoteEditor('mock-token')
    await editor.initSettings()
    
    // Test VND/KG preview
    const vndLine = {
      materialId: 'mat-1',
      priceOriginal: 15000,
      currency: 'VND',
      unit: 'KG',
      deliveryMonth: '2026-08',
      exchangeRate: null,
      exchangeRateManualReason: null,
      rateSourceMode: null,
      autoRateFetched: null,
      isRateLoading: false,
    }
    expect(editor.getLinePreviewPrice(vndLine)).toBe(15000)

    // Test USD/MT preview with exchange rate
    const usdLine = {
      materialId: 'mat-2',
      priceOriginal: 120, // 120 USD/MT
      currency: 'USD',
      unit: 'MT',
      deliveryMonth: '2026-08',
      exchangeRate: 26000, // 26000 VND/USD
      exchangeRateManualReason: null,
      rateSourceMode: 'auto' as const,
      autoRateFetched: null,
      isRateLoading: false,
    }
    // Expected: (120 / 1000) * 26000 + 250 = 3120 + 250 = 3370
    expect(editor.getLinePreviewPrice(usdLine)).toBe(3370)
  })

  it('detects backfill correctly for past received date', () => {
    const editor = useQuoteEditor('mock-token')
    
    // Set received date to past
    editor.receivedDate.value = '2020-01-01'
    editor.addLine()
    
    editor.evaluateBackfill()
    expect(editor.isBackfilled.value).toBe(true)
  })

  it('validates form fields and stops invalid submits', () => {
    const editor = useQuoteEditor('mock-token')

    // 1. Missing supplier
    expect(editor.validateForm()).toBe(false)
    expect(editor.errorMsg.value).toBe('Vui lòng chọn Nhà cung cấp.')

    // 2. Missing lines
    editor.supplierId.value = 'supp-1'
    expect(editor.validateForm()).toBe(false)
    expect(editor.errorMsg.value).toBe('Báo giá phải có ít nhất một dòng vật tư.')

    // 3. Line missing material
    editor.addLine()
    expect(editor.validateForm()).toBe(false)
    expect(editor.errorMsg.value).toContain('chưa chọn vật tư')

    // 4. Line price original invalid
    editor.lines.value[0].materialId = 'mat-1'
    editor.lines.value[0].priceOriginal = -10
    expect(editor.validateForm()).toBe(false)
    expect(editor.errorMsg.value).toContain('phải lớn hơn 0')

    // 5. Duplicate material and delivery month
    editor.lines.value[0].priceOriginal = 500
    editor.addLine()
    editor.lines.value[1].materialId = 'mat-1'
    editor.lines.value[1].priceOriginal = 600
    // Both lines have mat-1 and default current delivery month
    expect(editor.validateForm()).toBe(false)
    expect(editor.errorMsg.value).toContain('Không được khai báo trùng lặp')
  })
})
