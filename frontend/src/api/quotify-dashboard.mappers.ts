import type {
  QuotifyEntryKpis,
  QuotifyEntryKpisDto,
  QuotifyEntryUserKpi,
  QuotifyEntryUserKpiDto,
  QuotifyPriceSummary,
  QuotifyPriceSummaryDto,
  QuotifyPriceTrendPoint,
  QuotifyPriceTrendPointDto,
  QuotifyPriceTrends,
  QuotifyPriceTrendsDto,
  QuotifyPurchaseContext,
  QuotifyPurchaseContextDto,
} from '@/types/quotify-dashboard'

function mapNullableMoney(value: string | null): number | null {
  return value === null ? null : Number(value)
}

export function mapPriceSummaryDtoToDomain(
  dto: QuotifyPriceSummaryDto,
): QuotifyPriceSummary {
  return {
    minPrice: mapNullableMoney(dto.min_price),
    maxPrice: mapNullableMoney(dto.max_price),
    avgPrice: mapNullableMoney(dto.avg_price),
    totalLines: dto.total_lines,
    totalQuotes: dto.total_quotes,
    purchasedLines: dto.purchased_lines,
  }
}

export function mapEntryUserKpiDtoToDomain(
  dto: QuotifyEntryUserKpiDto,
): QuotifyEntryUserKpi {
  return {
    userId: dto.user_id,
    userEmail: dto.user_email,
    userFullName: dto.user_full_name,
    userLabel: dto.user_label,
    quoteCount: dto.quote_count,
  }
}

export function mapEntryKpisDtoToDomain(
  dto: QuotifyEntryKpisDto,
): QuotifyEntryKpis {
  return {
    totalQuoteCount: dto.total_quote_count,
    userKpis: Array.isArray(dto.user_kpis)
      ? dto.user_kpis.map(mapEntryUserKpiDtoToDomain)
      : [],
  }
}

export function mapPriceTrendPointDtoToDomain(
  dto: QuotifyPriceTrendPointDto,
): QuotifyPriceTrendPoint {
  return {
    receivedDate: dto.received_date,
    deliveryMonth: dto.delivery_month,
    convertedPriceVndPerKg: Number(dto.converted_price_vnd_per_kg),
    supplierId: dto.supplier_id,
    supplierName: dto.supplier_name,
    supplierCode: dto.supplier_code,
    supplierType: dto.supplier_type,
    supplierLabel: dto.supplier_label,
    materialId: dto.material_id,
    materialName: dto.material_name,
    materialCode: dto.material_code,
    quoteId: dto.quote_id,
    quoteVersionId: dto.quote_version_id,
    lineId: dto.line_id,
    purchased: dto.purchased,
    purchaseMarkedAt: dto.purchase_marked_at,
    confirmedAt: dto.confirmed_at,
  }
}

export function mapPurchaseContextDtoToDomain(
  dto: QuotifyPurchaseContextDto,
): QuotifyPurchaseContext {
  return {
    purchasedLineId: dto.purchased_line_id,
    quoteId: dto.quote_id,
    materialId: dto.material_id,
    deliveryMonth: dto.delivery_month,
    purchaseMarkedAt: dto.purchase_marked_at,
    atPurchase: mapPriceSummaryDtoToDomain(dto.at_purchase),
    afterPurchase: mapPriceSummaryDtoToDomain(dto.after_purchase),
  }
}

export function mapPriceTrendsDtoToDomain(
  dto: QuotifyPriceTrendsDto,
): QuotifyPriceTrends {
  return {
    summary: mapPriceSummaryDtoToDomain(dto.summary),
    points: Array.isArray(dto.points)
      ? dto.points.map(mapPriceTrendPointDtoToDomain)
      : [],
    purchaseContexts: Array.isArray(dto.purchase_contexts)
      ? dto.purchase_contexts.map(mapPurchaseContextDtoToDomain)
      : [],
  }
}
