export interface QuoteLineDto {
  id: string
  material_id: string
  material_code: string
  material_name: string
  price_original: string
  currency: string
  unit: string
  delivery_month: string
  line_order: number
  exchange_rate: string | null
  exchange_rate_source: string | null
  exchange_rate_source_mode: string | null
  exchange_rate_entered_at: string | null
  exchange_rate_manual_reason: string | null
  exchange_rate_actor_id: string | null
  import_tax_rate_percent: string | null
  processing_cost_vnd_per_kg: string | null
  price_converted_vnd_per_kg: string
  note: string | null
  purchase_marked_at: string | null
  purchase_marked_by_id: string | null
}

export interface QuoteLineDomain {
  id: string
  materialId: string
  materialCode: string
  materialName: string
  priceOriginal: number
  currency: string
  unit: string
  deliveryMonth: string
  lineOrder: number
  exchangeRate: number | null
  exchangeRateSource: string | null
  exchangeRateSourceMode: string | null
  exchangeRateEnteredAt: string | null
  exchangeRateManualReason: string | null
  exchangeRateActorId: string | null
  importTaxRatePercent: number | null
  processingCostVndPerKg: number | null
  priceConvertedVndPerKg: number
  note: string | null
  purchaseMarkedAt: string | null
  purchaseMarkedById: string | null
}

export interface QuoteVersionDto {
  id: string
  quote_id: string
  version_number: number
  received_date: string
  status: string
  file_id: string | null
  is_backfilled: boolean
  backfill_reason: string | null
  correction_reason: string | null
  created_by_id: string | null
  created_by_name: string | null
  confirmed_at: string | null
  confirmed_by_id: string | null
  superseded_at: string | null
  superseded_by_id: string | null
  superseded_by_version_id: string | null
  created_at: string
  updated_at: string
  lines: QuoteLineDto[]
}

export interface QuoteVersionDomain {
  id: string
  quoteId: string
  versionNumber: number
  receivedDate: string
  status: string
  fileId: string | null
  isBackfilled: boolean
  backfillReason: string | null
  correctionReason: string | null
  createdById: string | null
  createdByName: string | null
  confirmedAt: string | null
  confirmedById: string | null
  supersededAt: string | null
  supersededById: string | null
  supersededByVersionId: string | null
  createdAt: string
  updatedAt: string
  lines: QuoteLineDomain[]
}

export interface QuoteDto {
  id: string
  supplier_id: string
  supplier_name: string
  supplier_code: string
  created_by_id: string | null
  created_at: string
  updated_at: string
  versions: QuoteVersionDto[]
}

export interface QuoteDomain {
  id: string
  supplierId: string
  supplierName: string
  supplierCode: string
  createdById: string | null
  createdAt: string
  updatedAt: string
  versions: QuoteVersionDomain[]
}

export interface QuoteLineCreatePayload {
  material_id: string
  price_original: number
  currency: string
  unit: string
  delivery_month: string
  exchange_rate?: number | null
  exchange_rate_manual_reason?: string | null
}

export interface QuoteCreatePayload {
  supplier_id: string
  received_date: string
  is_backfilled: boolean
  backfill_reason: string | null
  lines: QuoteLineCreatePayload[]
}

export interface QuoteDraftUpdatePayload {
  received_date: string
  is_backfilled: boolean
  backfill_reason: string | null
  correction_reason?: string | null
  lines: QuoteLineCreatePayload[]
}

export interface QuoteLinePurchaseTogglePayload {
  purchase: boolean
  purchase_date?: string | null
}

export interface QuoteNoteRevisionDto {
  id: string
  revision_number: number
  content: string
  author_id: string | null
  author_name: string | null
  author_avatar_url: string | null
  created_at: string
}

export interface QuoteNoteDto {
  id: string
  quote_id: string
  created_at: string
  updated_at: string
  revisions: QuoteNoteRevisionDto[]
}

export interface QuoteNoteRevisionDomain {
  id: string
  revisionNumber: number
  content: string
  authorId: string | null
  authorName: string | null
  authorAvatarUrl: string | null
  createdAt: string
}

export interface QuoteNoteDomain {
  id: string
  quoteId: string
  createdAt: string
  updatedAt: string
  revisions: QuoteNoteRevisionDomain[]
}

export interface QuoteFlattenedDto {
  id: string
  quote_id: string
  quote_version_id: string
  supplier_id: string
  supplier_name: string
  supplier_code: string
  material_id: string
  material_name: string
  material_code: string
  material_type_name: string
  material_type_code: string
  received_date: string
  delivery_month: string
  price_original: string
  currency: string
  unit: string
  exchange_rate: string | null
  exchange_rate_source: string | null
  import_tax_rate_percent: string | null
  processing_cost_vnd_per_kg: string | null
  price_converted_vnd_per_kg: string
  purchased: boolean
  version_number: number
  version_status: string
  created_by_name: string | null
  created_at: string
}

export interface QuoteFlattenedDomain {
  id: string
  quoteId: string
  quoteVersionId: string
  supplierId: string
  supplierName: string
  supplierCode: string
  materialId: string
  materialName: string
  materialCode: string
  materialTypeName: string
  materialTypeCode: string
  receivedDate: string
  deliveryMonth: string
  priceOriginal: number
  currency: string
  unit: string
  exchangeRate: number | null
  exchangeRateSource: string | null
  importTaxRatePercent: number | null
  processingCostVndPerKg: number | null
  priceConvertedVndPerKg: number
  purchased: boolean
  versionNumber: number
  versionStatus: string
  createdByName: string | null
  createdAt: string
}
