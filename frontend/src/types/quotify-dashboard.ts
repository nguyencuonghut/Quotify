export type QuotifyDashboardSupplierType = 'domestic' | 'international'

export interface QuotifyPriceSummaryDto {
  min_price: string | null
  max_price: string | null
  avg_price: string | null
  total_lines: number
  total_quotes: number
  purchased_lines: number
}

export interface QuotifyEntryUserKpiDto {
  user_id: string | null
  user_email: string | null
  user_full_name: string | null
  user_label: string
  quote_count: number
}

export interface QuotifyEntryKpisDto {
  total_quote_count: number
  user_kpis: QuotifyEntryUserKpiDto[]
}

export interface QuotifyPriceTrendPointDto {
  received_date: string
  delivery_month: string
  converted_price_vnd_per_kg: string
  supplier_id: string
  supplier_name: string
  supplier_code: string
  supplier_type: QuotifyDashboardSupplierType
  supplier_label: string
  material_id: string
  material_name: string
  material_code: string
  quote_id: string
  quote_version_id: string
  line_id: string
  purchased: boolean
  purchase_marked_at: string | null
  confirmed_at: string
}

export interface QuotifyPurchaseContextDto {
  purchased_line_id: string
  quote_id: string
  material_id: string
  delivery_month: string
  purchase_marked_at: string
  at_purchase: QuotifyPriceSummaryDto
  after_purchase: QuotifyPriceSummaryDto
}

export interface QuotifyPriceTrendsDto {
  summary: QuotifyPriceSummaryDto
  points: QuotifyPriceTrendPointDto[]
  purchase_contexts: QuotifyPurchaseContextDto[]
}

export interface QuotifyPriceSummary {
  minPrice: number | null
  maxPrice: number | null
  avgPrice: number | null
  totalLines: number
  totalQuotes: number
  purchasedLines: number
}

export interface QuotifyEntryUserKpi {
  userId: string | null
  userEmail: string | null
  userFullName: string | null
  userLabel: string
  quoteCount: number
}

export interface QuotifyEntryKpis {
  totalQuoteCount: number
  userKpis: QuotifyEntryUserKpi[]
}

export interface QuotifyPriceTrendPoint {
  receivedDate: string
  deliveryMonth: string
  convertedPriceVndPerKg: number
  supplierId: string
  supplierName: string
  supplierCode: string
  supplierType: QuotifyDashboardSupplierType
  supplierLabel: string
  materialId: string
  materialName: string
  materialCode: string
  quoteId: string
  quoteVersionId: string
  lineId: string
  purchased: boolean
  purchaseMarkedAt: string | null
  confirmedAt: string
}

export interface QuotifyPurchaseContext {
  purchasedLineId: string
  quoteId: string
  materialId: string
  deliveryMonth: string
  purchaseMarkedAt: string
  atPurchase: QuotifyPriceSummary
  afterPurchase: QuotifyPriceSummary
}

export interface QuotifyPriceTrends {
  summary: QuotifyPriceSummary
  points: QuotifyPriceTrendPoint[]
  purchaseContexts: QuotifyPurchaseContext[]
}

export interface QuotifyDashboardQuery {
  materialId?: string | null
  deliveryMonth?: string | null
  receivedDateStart?: string | null
  receivedDateEnd?: string | null
  supplierType?: QuotifyDashboardSupplierType | null
}
