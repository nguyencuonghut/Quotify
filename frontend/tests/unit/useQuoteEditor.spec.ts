import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getTodayString, useQuoteEditor } from '@/composables/useQuoteEditor'
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

  it('does not require or submit a backfill reason', () => {
    const editor = useQuoteEditor('mock-token')

    editor.supplierId.value = 'supplier-1'
    editor.receivedDate.value = '2020-01-01'
    editor.addLine()
    editor.lines.value[0].materialId = 'mat-1'
    editor.lines.value[0].priceOriginal = 15000
    editor.lines.value[0].deliveryMonth = '2026-08'
    editor.evaluateBackfill()

    expect(editor.validateForm()).toBe(true)
    expect(editor.prepareCreatePayload()).toMatchObject({
      is_backfilled: true,
      backfill_reason: null,
    })
  })

  it('preserves cloned quote version rate snapshot while received date is unchanged', async () => {
    exchangeRatesApiMock.getUsdSellRateToday.mockResolvedValue({
      rate: 27000,
      source: 'Vietcombank USD bán ra',
      retrievedAt: '2026-07-30T08:00:00+07:00',
    })
    const today = getTodayString()
    const editor = useQuoteEditor('mock-token')
    await editor.fetchUsdRateToday()

    await editor.loadVersionData({
      id: 'version-1',
      quoteId: 'quote-1',
      versionNumber: 1,
      receivedDate: today,
      status: 'confirmed',
      fileId: null,
      isBackfilled: false,
      backfillReason: null,
      correctionReason: null,
      createdById: 'user-1',
      confirmedAt: null,
      confirmedById: null,
      supersededAt: null,
      supersededById: null,
      supersededByVersionId: null,
      createdAt: today,
      updatedAt: today,
      lines: [{
        id: 'line-1',
        materialId: 'mat-1',
        materialCode: 'MAT-1',
        materialName: 'Ngô hạt',
        priceOriginal: 700,
        currency: 'USD',
        unit: 'MT',
        deliveryMonth: '2026-08-01',
        lineOrder: 0,
        exchangeRate: 26000,
        exchangeRateSource: 'Vietcombank USD bán ra',
        exchangeRateSourceMode: 'auto',
        exchangeRateEnteredAt: '2026-07-30T08:00:00+07:00',
        exchangeRateManualReason: null,
        exchangeRateActorId: null,
        conversionCostVndPerKg: 150,
        priceConvertedVndPerKg: 18350,
        purchaseMarkedAt: null,
        purchaseMarkedById: null,
      }],
    })
    editor.evaluateRateModeForLine(editor.lines.value[0])

    expect(editor.lines.value[0].exchangeRate).toBe(26000)
    expect(editor.lines.value[0].rateSourceMode).toBe('auto')
  })

  it('switches cloned quote version rate to automatic when received date changes to today', async () => {
    exchangeRatesApiMock.getUsdSellRateToday.mockResolvedValue({
      rate: 27000,
      source: 'Vietcombank USD bán ra',
      retrievedAt: '2026-07-30T08:00:00+07:00',
    })
    const today = getTodayString()
    const editor = useQuoteEditor('mock-token')
    await editor.fetchUsdRateToday()

    await editor.loadVersionData({
      id: 'version-1',
      quoteId: 'quote-1',
      versionNumber: 1,
      receivedDate: '2026-07-27',
      status: 'confirmed',
      fileId: null,
      isBackfilled: true,
      backfillReason: 'Nhập lại báo giá cũ.',
      correctionReason: null,
      createdById: 'user-1',
      confirmedAt: null,
      confirmedById: null,
      supersededAt: null,
      supersededById: null,
      supersededByVersionId: null,
      createdAt: '2026-07-27',
      updatedAt: '2026-07-27',
      lines: [{
        id: 'line-1',
        materialId: 'mat-1',
        materialCode: 'MAT-1',
        materialName: 'Ngô hạt',
        priceOriginal: 700,
        currency: 'USD',
        unit: 'MT',
        deliveryMonth: '2026-08-01',
        lineOrder: 0,
        exchangeRate: 25000,
        exchangeRateSource: 'Nhập tay',
        exchangeRateSourceMode: 'manual_past',
        exchangeRateEnteredAt: '2026-07-27T08:00:00+07:00',
        exchangeRateManualReason: 'Tỷ giá tại ngày nhận báo giá.',
        exchangeRateActorId: 'user-1',
        conversionCostVndPerKg: 150,
        priceConvertedVndPerKg: 17650,
        purchaseMarkedAt: null,
        purchaseMarkedById: null,
      }],
    })
    editor.receivedDate.value = today
    editor.evaluateRateModeForLine(editor.lines.value[0])

    expect(editor.lines.value[0].exchangeRate).toBe(27000)
    expect(editor.lines.value[0].rateSourceMode).toBe('auto')
    expect(editor.lines.value[0].exchangeRateManualReason).toBeNull()
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
