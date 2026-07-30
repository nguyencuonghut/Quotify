import type {
  QuoteDomain,
  QuoteDto,
  QuoteLineDomain,
  QuoteLineDto,
  QuoteVersionDomain,
  QuoteVersionDto,
  QuoteNoteDto,
  QuoteNoteDomain,
  QuoteFlattenedDto,
  QuoteFlattenedDomain,
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
    lineOrder: dto.line_order,
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
    correctionReason: dto.correction_reason,
    createdById: dto.created_by_id,
    confirmedAt: dto.confirmed_at,
    confirmedById: dto.confirmed_by_id,
    supersededAt: dto.superseded_at,
    supersededById: dto.superseded_by_id,
    supersededByVersionId: dto.superseded_by_version_id,
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

export function mapQuoteNoteDtoToDomain(dto: QuoteNoteDto): QuoteNoteDomain {
  return {
    id: dto.id,
    quoteId: dto.quote_id,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
    revisions: Array.isArray(dto.revisions)
      ? dto.revisions.map((r) => ({
          id: r.id,
          revisionNumber: r.revision_number,
          content: r.content,
          authorId: r.author_id,
          authorName: r.author_name,
          createdAt: r.created_at,
        }))
      : [],
  }
}

export function mapQuoteFlattenedDtoToDomain(dto: QuoteFlattenedDto): QuoteFlattenedDomain {
  return {
    id: dto.id,
    quoteId: dto.quote_id,
    quoteVersionId: dto.quote_version_id,
    supplierId: dto.supplier_id,
    supplierName: dto.supplier_name,
    supplierCode: dto.supplier_code,
    materialId: dto.material_id,
    material_name: dto.material_name, // Chú ý: backend trả material_name
    material_code: dto.material_code,
    material_type_name: dto.material_type_name,
    material_type_code: dto.material_type_code,
    materialName: dto.material_name,
    materialCode: dto.material_code,
    materialTypeName: dto.material_type_name,
    materialTypeCode: dto.material_type_code,
    receivedDate: dto.received_date,
    deliveryMonth: dto.delivery_month,
    priceOriginal: Number(dto.price_original),
    currency: dto.currency,
    unit: dto.unit,
    exchangeRate: dto.exchange_rate !== null ? Number(dto.exchange_rate) : null,
    exchangeRateSource: dto.exchange_rate_source,
    conversionCostVndPerKg: dto.conversion_cost_vnd_per_kg !== null ? Number(dto.conversion_cost_vnd_per_kg) : null,
    priceConvertedVndPerKg: Number(dto.price_converted_vnd_per_kg),
    purchased: dto.purchased,
    versionNumber: dto.version_number,
    versionStatus: dto.version_status,
    createdByName: dto.created_by_name,
    createdAt: dto.created_at,
  }
}
