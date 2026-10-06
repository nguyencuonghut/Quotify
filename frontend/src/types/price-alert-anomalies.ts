export type AnomalyStatusFilter = 'pending' | 'resolved' | 'all'
export type AnomalyReviewStatus =
  | 'pending'
  | 'accepted'
  | 'rejected'
  | 'expired'
export type AnomalyDecision = 'accepted' | 'rejected'

export interface AnomalyItemDto {
  id: string
  material_id: string
  material_name: string
  delivery_month: string
  received_date: string
  price_new: string
  median: string
  percent_change: string
  reference_prices: string[]
  reference_point_count: number | null
  quote_id: string
  entered_by_name: string | null
  review_status: AnomalyReviewStatus
  attached_count: number
  age_working_days: number
  created_at: string
  reviewed_by_name: string | null
  reviewed_at: string | null
}

export interface AnomalyListDto {
  items: AnomalyItemDto[]
  total: number
}

export interface AnomalyReviewDto {
  id: string
  review_status: AnomalyReviewStatus
  reviewed_by_name: string | null
  reviewed_at: string | null
}

export type AnomalyTagSeverity = 'warn' | 'success' | 'danger' | 'secondary'

export interface AnomalyDomain {
  id: string
  materialId: string
  materialName: string
  deliveryMonthLabel: string
  receivedDateLabel: string
  priceLabel: string
  medianLabel: string
  percentLabel: string
  direction: 'up' | 'down'
  referenceLabel: string
  lowConfidence: boolean
  quoteId: string
  enteredByName: string
  status: AnomalyReviewStatus
  statusLabel: string
  statusSeverity: AnomalyTagSeverity
  isPending: boolean
  attachedCount: number
  ageLabel: string
  createdAtLabel: string
  reviewerLabel: string | null
}

export interface AnomalyListDomain {
  items: AnomalyDomain[]
  total: number
}

export interface AnomalyReviewDomain {
  id: string
  status: AnomalyReviewStatus
  statusLabel: string
  reviewerLabel: string | null
}

export interface AnomalyListQueryParams {
  status: AnomalyStatusFilter
  limit: number
  offset: number
  materialId?: string
}

/** Chi tiết lỗi 409 khi thẻ đã được người khác xử lý. */
export interface AnomalyConflictDomain {
  statusLabel: string
  reviewerName: string | null
  reviewedAtLabel: string | null
}
