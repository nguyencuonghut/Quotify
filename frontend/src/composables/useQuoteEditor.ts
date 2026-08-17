import { ref, watch } from 'vue'
import { getUsdSellRateToday } from '@/api/exchange-rates.api'
import { getQuotifySettings } from '@/api/quotify-settings.api'
import { getSupplier } from '@/api/suppliers.api'
import type { SupplierMaterialDomain } from '@/types/suppliers'
import type { QuoteCreatePayload, QuoteDraftUpdatePayload, QuoteVersionDomain, QuoteDomain } from '@/types/quotes'

export function getTodayString(): string {
  const tzOffset = 7 * 60 // GMT+7
  const now = new Date()
  const utc = now.getTime() + now.getTimezoneOffset() * 60000
  const localNow = new Date(utc + tzOffset * 60000)
  const yyyy = localNow.getFullYear()
  const mm = String(localNow.getMonth() + 1).padStart(2, '0')
  const dd = String(localNow.getDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}

export function getCurrentMonthString(): string {
  const tzOffset = 7 * 60 // GMT+7
  const now = new Date()
  const utc = now.getTime() + now.getTimezoneOffset() * 60000
  const localNow = new Date(utc + tzOffset * 60000)
  const yyyy = localNow.getFullYear()
  const mm = String(localNow.getMonth() + 1).padStart(2, '0')
  return `${yyyy}-${mm}`
}

export function getNextMonthString(currentMonthStr: string): string {
  if (!currentMonthStr || !currentMonthStr.includes('-')) {
    return getCurrentMonthString()
  }
  const [yyyyStr, mmStr] = currentMonthStr.split('-')
  let year = parseInt(yyyyStr, 10)
  let month = parseInt(mmStr, 10)
  
  month += 1
  if (month > 12) {
    month = 1
    year += 1
  }
  
  return `${year}-${String(month).padStart(2, '0')}`
}

export interface QuoteEditorLine {
  id?: string
  materialId: string | null
  priceOriginal: number | null
  currency: string
  unit: string
  deliveryMonth: string // YYYY-MM format
  exchangeRate: number | null
  exchangeRateSource?: string | null
  exchangeRateManualReason: string | null
  snapshotReceivedDate?: string | null
  snapshotExchangeRate?: number | null
  snapshotExchangeRateSource?: string | null
  snapshotExchangeRateSourceMode?: 'auto' | 'manual_past' | 'manual_fallback' | null
  snapshotExchangeRateManualReason?: string | null
  
  // UI states
  rateSourceMode: 'auto' | 'manual_past' | 'manual_fallback' | null
  autoRateFetched: number | null
  isRateLoading: boolean
}


export function useQuoteEditor(accessToken: string | null) {
  const supplierId = ref<string | null>(null)
  const receivedDate = ref<string>(getTodayString())
  const isBackfilled = ref<boolean>(false)
  const backfillReason = ref<string | null>(null)
  const correctionReason = ref<string | null>(null)
  
  const lines = ref<QuoteEditorLine[]>([])
  
  const supplierMaterials = ref<SupplierMaterialDomain[]>([])
  const importTaxRatePercent = ref<number>(0) // default fallback 0%
  const processingCost = ref<number>(200) // default fallback 200 VND/KG
  const systemUsdRate = ref<number | null>(null)
  const systemUsdRateError = ref<boolean>(false)
  
  const isSupplierLoading = ref<boolean>(false)
  const isSettingsLoading = ref<boolean>(false)
  const isSubmitting = ref<boolean>(false)
  const errorMsg = ref<string | null>(null)

  // Initialize master data
  const initSettings = async () => {
    isSettingsLoading.value = true
    try {
      const settings = await getQuotifySettings(accessToken)
      importTaxRatePercent.value = Number(settings.importTaxRatePercent)
      processingCost.value = Number(settings.processingCostVndPerKg)
    } catch {
      // Keep defaults
    } finally {
      isSettingsLoading.value = false
    }
  }

  // Load today's USD rate
  const fetchUsdRateToday = async () => {
    systemUsdRateError.value = false
    try {
      const rateData = await getUsdSellRateToday(accessToken)
      systemUsdRate.value = Number(rateData.rate)
    } catch {
      systemUsdRate.value = null
      systemUsdRateError.value = true
    }
  }

  // Load supplier materials
  watch(supplierId, async (newVal) => {
    if (!newVal) {
      supplierMaterials.value = []
      return
    }
    isSupplierLoading.value = true
    try {
      const supplier = await getSupplier(newVal, accessToken)
      supplierMaterials.value = supplier.materials
    } catch {
      supplierMaterials.value = []
    } finally {
      isSupplierLoading.value = false
    }
  })

  // Watch received date & line options to recalculate rate status
  const evaluateRateModeForLine = (line: QuoteEditorLine) => {
    if (line.currency.toUpperCase() !== 'USD' || line.unit.toUpperCase() !== 'MT') {
      line.rateSourceMode = null
      line.exchangeRate = null
      line.exchangeRateSource = ''
      line.exchangeRateManualReason = null
      return
    }

    if (line.snapshotReceivedDate && receivedDate.value === line.snapshotReceivedDate) {
      line.rateSourceMode = line.snapshotExchangeRateSourceMode ?? null
      line.exchangeRate = line.snapshotExchangeRate ?? null
      line.exchangeRateSource = line.snapshotExchangeRateSource || ''
      line.exchangeRateManualReason = line.snapshotExchangeRateManualReason ?? null
      return
    }

    const today = getTodayString()
    if (receivedDate.value > today) {
      line.rateSourceMode = null
      line.exchangeRateSource = ''
      return
    }

    if (receivedDate.value === today) {
      if (systemUsdRate.value !== null) {
        line.rateSourceMode = 'auto'
        line.exchangeRate = systemUsdRate.value
        line.exchangeRateSource = 'Vietcombank USD bán ra'
        line.exchangeRateManualReason = null
      } else if (systemUsdRateError.value) {
        line.rateSourceMode = 'manual_fallback'
        line.exchangeRateSource = 'Nhập tay do không lấy được tỷ giá tự động'
        if (line.rateSourceMode !== 'manual_fallback') {
          line.exchangeRate = null
        }
      }
    } else {
      line.rateSourceMode = 'manual_past'
      line.exchangeRateSource = 'Nhập tay'
      line.exchangeRateManualReason = null
    }
  }

  watch([receivedDate, systemUsdRate, systemUsdRateError], () => {
    lines.value.forEach(evaluateRateModeForLine)
  }, { deep: true })

  // Watch for line currency or unit updates to evaluate rate mode immediately
  watch(
    () => lines.value.map((l) => `${l.currency}_${l.unit}`),
    (newVal, oldVal) => {
      lines.value.forEach((line, index) => {
        const oldKey = oldVal?.[index]
        const newKey = newVal[index]
        if (newKey !== oldKey) {
          evaluateRateModeForLine(line)
        }
      })
    }
  )

  // Trigger evaluate backfill flags
  const evaluateBackfill = () => {
    const today = getTodayString()
    const firstDayCurrent = today.substring(0, 7) + '-01'
    
    let needsBackfill = receivedDate.value < today
    
    if (!needsBackfill) {
      for (const line of lines.value) {
        if (line.deliveryMonth) {
          const lineDelivFirstDay = line.deliveryMonth + '-01'
          if (lineDelivFirstDay < firstDayCurrent) {
            needsBackfill = true
            break
          }
        }
      }
    }

    isBackfilled.value = needsBackfill
    if (!needsBackfill) {
      backfillReason.value = null
    }
  }

  watch([receivedDate, lines], () => {
    evaluateBackfill()
  }, { deep: true })

  const addLine = () => {
    const defaultLine: QuoteEditorLine = {
      materialId: null,
      priceOriginal: null,
      currency: 'VND',
      unit: 'KG',
      deliveryMonth: getCurrentMonthString(),
      exchangeRate: null,
      exchangeRateSource: '',
      exchangeRateManualReason: null,
      rateSourceMode: null,
      autoRateFetched: null,
      isRateLoading: false,
    }
    evaluateRateModeForLine(defaultLine)
    lines.value.push(defaultLine)
  }

  const removeLine = (index: number) => {
    lines.value.splice(index, 1)
  }

  const duplicateLine = (index: number) => {
    const sourceLine = lines.value[index]
    if (!sourceLine) return
    const nextMonth = sourceLine.deliveryMonth
      ? getNextMonthString(sourceLine.deliveryMonth)
      : getCurrentMonthString()
    const clonedLine: QuoteEditorLine = {
      materialId: sourceLine.materialId,
      priceOriginal: sourceLine.priceOriginal,
      currency: sourceLine.currency,
      unit: sourceLine.unit,
      deliveryMonth: nextMonth,
      exchangeRate: sourceLine.exchangeRate,
      exchangeRateSource: sourceLine.exchangeRateSource || '',
      exchangeRateManualReason: sourceLine.exchangeRateManualReason,
      snapshotReceivedDate: null,
      snapshotExchangeRate: null,
      snapshotExchangeRateSource: null,
      snapshotExchangeRateSourceMode: null,
      snapshotExchangeRateManualReason: null,
      rateSourceMode: sourceLine.rateSourceMode,
      autoRateFetched: sourceLine.autoRateFetched,
      isRateLoading: false,
    }
    lines.value.splice(index + 1, 0, clonedLine)
  }

  // Pre-fill editor from an existing draft or for version clone
  const loadVersionData = async (version: QuoteVersionDomain, quote?: QuoteDomain) => {
    if (quote) {
      supplierId.value = quote.supplierId
    }
    receivedDate.value = version.receivedDate
    isBackfilled.value = version.isBackfilled
    backfillReason.value = version.backfillReason
    correctionReason.value = version.correctionReason
    
    lines.value = version.lines.map((line) => {
      const editorLine: QuoteEditorLine = {
        id: line.id,
        materialId: line.materialId,
        priceOriginal: line.priceOriginal,
        currency: line.currency,
        unit: line.unit,
        deliveryMonth: line.deliveryMonth.substring(0, 7), // convert YYYY-MM-DD to YYYY-MM
        exchangeRate: line.exchangeRate,
        exchangeRateSource: line.exchangeRateSource || '',
        exchangeRateManualReason: line.exchangeRateManualReason,
        snapshotReceivedDate: version.receivedDate,
        snapshotExchangeRate: line.exchangeRate,
        snapshotExchangeRateSource: line.exchangeRateSource || '',
        snapshotExchangeRateSourceMode: line.exchangeRateSourceMode as any,
        snapshotExchangeRateManualReason: line.exchangeRateManualReason,
        rateSourceMode: line.exchangeRateSourceMode as any,
        autoRateFetched: null,
        isRateLoading: false,
      }
      return editorLine
    })
  }


  // Preview converted price calculation
  const getLinePreviewPrice = (line: QuoteEditorLine): number | null => {
    const price = Number(line.priceOriginal)
    if (line.priceOriginal === null || isNaN(price)) {
      return null
    }
    if (line.currency.toUpperCase() === 'VND' && line.unit.toUpperCase() === 'KG') {
      return Number(price.toFixed(2))
    }
    if (line.currency.toUpperCase() === 'USD' && line.unit.toUpperCase() === 'MT') {
      const rate = Number(line.exchangeRate)
      if (line.exchangeRate === null || isNaN(rate)) {
        return null
      }
      const tax = Number(importTaxRatePercent.value)
      const cost = Number(processingCost.value)
      const rawConverted = (price / 1000) * (1 + tax / 100) * rate + cost
      return Number(rawConverted.toFixed(2))
    }
    return null
  }

  // Form schemas validation
  const validateForm = (): boolean => {
    errorMsg.value = null
    if (!supplierId.value) {
      errorMsg.value = 'Vui lòng chọn Nhà cung cấp.'
      return false
    }
    if (!receivedDate.value) {
      errorMsg.value = 'Vui lòng chọn Ngày nhận báo giá.'
      return false
    }
    if (lines.value.length === 0) {
      errorMsg.value = 'Báo giá phải có ít nhất một dòng vật tư.'
      return false
    }

    // Validate duplicates & details values
    const uniqueKeys = new Set<string>()
    for (let i = 0; i < lines.value.length; i++) {
      const line = lines.value[i]
      if (!line.materialId) {
        errorMsg.value = `Dòng #${i + 1} chưa chọn vật tư.`
        return false
      }
      if (line.priceOriginal === null || line.priceOriginal <= 0) {
        errorMsg.value = `Dòng #${i + 1} có giá gốc phải lớn hơn 0.`
        return false
      }
      if (!line.deliveryMonth) {
        errorMsg.value = `Dòng #${i + 1} chưa chọn tháng giao hàng.`
        return false
      }

      // Check duplicate material + delivery month
      const key = `${line.materialId}_${line.deliveryMonth}`
      if (uniqueKeys.has(key)) {
        errorMsg.value = 'Không được khai báo trùng lặp vật tư và tháng giao hàng trong cùng một phiên bản.'
        return false
      }
      uniqueKeys.add(key)

      // USD check
      if (line.currency.toUpperCase() === 'USD' && line.unit.toUpperCase() === 'MT') {
        if (line.exchangeRate === null || line.exchangeRate <= 0) {
          errorMsg.value = `Dòng #${i + 1} (USD/MT) thiếu thông tin tỷ giá quy đổi.`
          return false
        }
        if (line.rateSourceMode === 'manual_fallback' && (!line.exchangeRateManualReason || !line.exchangeRateManualReason.trim())) {
          errorMsg.value = `Dòng #${i + 1} đang nhập tỷ giá thủ công do lỗi hệ thống, vui lòng nhập lý do.`
          return false
        }
      } else {
        // VND checks
        if (line.currency.toUpperCase() !== 'VND' || line.unit.toUpperCase() !== 'KG') {
          errorMsg.value = `Dòng #${i + 1} có đơn vị ${line.currency}/${line.unit} không hợp lệ. Chỉ hỗ trợ VND/KG hoặc USD/MT.`
          return false
        }
      }
    }

    return true
  }

  const prepareCreatePayload = (): QuoteCreatePayload => {
    return {
      supplier_id: supplierId.value!,
      received_date: receivedDate.value,
      is_backfilled: isBackfilled.value,
      backfill_reason: null,
      lines: lines.value.map((l) => ({
        material_id: l.materialId!,
        price_original: l.priceOriginal!,
        currency: l.currency,
        unit: l.unit,
        delivery_month: l.deliveryMonth + '-01', // append first day of month
        exchange_rate: l.exchangeRate,
        exchange_rate_manual_reason: l.exchangeRateManualReason,
      })),
    }
  }

  const prepareUpdatePayload = (): QuoteDraftUpdatePayload => {
    return {
      received_date: receivedDate.value,
      is_backfilled: isBackfilled.value,
      backfill_reason: null,
      correction_reason: correctionReason.value,
      lines: lines.value.map((l) => ({
        material_id: l.materialId!,
        price_original: l.priceOriginal!,
        currency: l.currency,
        unit: l.unit,
        delivery_month: l.deliveryMonth + '-01',
        exchange_rate: l.exchangeRate,
        exchange_rate_manual_reason: l.exchangeRateManualReason,
      })),
    }
  }

  return {
    supplierId,
    receivedDate,
    isBackfilled,
    backfillReason,
    correctionReason,
    lines,
    supplierMaterials,
    importTaxRatePercent,
    processingCost,
    systemUsdRate,
    systemUsdRateError,
    isSupplierLoading,
    isSettingsLoading,
    isSubmitting,
    errorMsg,
    initSettings,
    fetchUsdRateToday,
    addLine,
    removeLine,
    duplicateLine,
    loadVersionData,
    getLinePreviewPrice,
    validateForm,
    prepareCreatePayload,
    prepareUpdatePayload,
    evaluateRateModeForLine,
    evaluateBackfill,
  }
}
