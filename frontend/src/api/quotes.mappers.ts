import type {
  QuoteDomain,
  QuoteDto,
  QuoteLineDomain,
  QuoteLineDto,
  QuoteVersionDomain,
  QuoteVersionDto,
} from '@/types/quotes'

export function mapQuoteLineDtoToDomain(dto: QuoteLineDto): QuoteLineDomain {
  return {
    id: dto.id,
    materialId: dto.material_id,
    materialCode: dto.material_code,
    materialName: dto.material_name,
    priceOriginal: Number(dto.price_original),
    currency: dto.currency,
    unit: dto.unit,
    deliveryMonth: dto.delivery_month,
    exchangeRate: dto.exchange_rate !== null ? Number(dto.exchange_rate) : null,
    exchangeRateSource: dto.exchange_rate_source,
    exchangeRateSourceMode: dto.exchange_rate_source_mode,
    exchangeRateEnteredAt: dto.exchange_rate_entered_at,
    exchangeRateManualReason: dto.exchange_rate_manual_reason,
    exchangeRateActorId: dto.exchange_rate_actor_id,
    conversionCostVndPerKg:
      dto.conversion_cost_vnd_per_kg !== null
        ? Number(dto.conversion_cost_vnd_per_kg)
        : null,
    priceConvertedVndPerKg: Number(dto.price_converted_vnd_per_kg),
    purchaseMarkedAt: dto.purchase_marked_at,
    purchaseMarkedById: dto.purchase_marked_by_id,
  }
}

export function mapQuoteVersionDtoToDomain(dto: QuoteVersionDto): QuoteVersionDomain {
  return {
    id: dto.id,
    quoteId: dto.quote_id,
    versionNumber: dto.version_number,
    receivedDate: dto.received_date,
    status: dto.status,
    fileId: dto.file_id,
    isBackfilled: dto.is_backfilled,
    backfillReason: dto.backfill_reason,
    createdById: dto.created_by_id,
    confirmedAt: dto.confirmed_at,
    confirmedById: dto.confirmed_by_id,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
    lines: Array.isArray(dto.lines) ? dto.lines.map(mapQuoteLineDtoToDomain) : [],
  }
}

export function mapQuoteDtoToDomain(dto: QuoteDto): QuoteDomain {
  return {
    id: dto.id,
    supplierId: dto.supplier_id,
    supplierName: dto.supplier_name,
    supplierCode: dto.supplier_code,
    createdById: dto.created_by_id,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
    versions: Array.isArray(dto.versions)
      ? dto.versions.map(mapQuoteVersionDtoToDomain)
      : [],
  }
}
