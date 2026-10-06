import type {
  AnomalyConflictDomain,
  AnomalyDomain,
  AnomalyItemDto,
  AnomalyListDomain,
  AnomalyListDto,
  AnomalyReviewDomain,
  AnomalyReviewDto,
  AnomalyReviewStatus,
  AnomalyTagSeverity,
} from '@/types/price-alert-anomalies'

const TIMEZONE = import.meta.env.VITE_APP_TIMEZONE || 'Asia/Ho_Chi_Minh'

const dateTimeFormatter = new Intl.DateTimeFormat('vi-VN', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
  timeZone: TIMEZONE,
})
const numberFormatter = new Intl.NumberFormat('vi-VN', {
  maximumFractionDigits: 0,
})
const percentFormatter = new Intl.NumberFormat('vi-VN', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

const STATUS_LABELS: Record<AnomalyReviewStatus, string> = {
  pending: 'Chờ duyệt',
  accepted: 'Đã xác nhận giá đúng',
  rejected: 'Đã đánh dấu nhập sai',
  expired: 'Hết hạn',
}
const STATUS_SEVERITY: Record<AnomalyReviewStatus, AnomalyTagSeverity> = {
  pending: 'warn',
  accepted: 'success',
  rejected: 'danger',
  expired: 'secondary',
}

function formatDateTime(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : dateTimeFormatter.format(date)
}

function formatPrice(value: string): string {
  return numberFormatter.format(Number(value))
}

function formatMonth(value: string): string {
  const [year, month] = value.split('-')
  return `${month}/${year}`
}

function formatDay(value: string): string {
  const [year, month, day] = value.split('-')
  return `${day}/${month}/${year}`
}

function formatPercent(value: string): {
  label: string
  direction: 'up' | 'down'
} {
  const number = Number(value)
  const direction = number < 0 ? 'down' : 'up'
  const arrow = number === 0 ? '' : direction === 'up' ? '▲' : '▼'
  return {
    label: `${arrow}${percentFormatter.format(Math.abs(number))}%`,
    direction,
  }
}

function formatAge(days: number): string {
  return days <= 0 ? 'Hôm nay' : `${days} ngày làm việc`
}

function reviewerLabel(name: string | null, at: string | null): string | null {
  if (!name) {
    return null
  }
  return at ? `${name} · ${formatDateTime(at)}` : name
}

export function mapAnomalyItemDtoToDomain(dto: AnomalyItemDto): AnomalyDomain {
  const percent = formatPercent(dto.percent_change)
  return {
    id: dto.id,
    materialId: dto.material_id,
    materialName: dto.material_name,
    deliveryMonthLabel: formatMonth(dto.delivery_month),
    receivedDateLabel: formatDay(dto.received_date),
    priceLabel: formatPrice(dto.price_new),
    medianLabel: formatPrice(dto.median),
    percentLabel: percent.label,
    direction: percent.direction,
    referenceLabel: dto.reference_prices.map(formatPrice).join(' · '),
    lowConfidence: dto.reference_point_count === 1,
    quoteId: dto.quote_id,
    enteredByName: dto.entered_by_name || 'Không rõ',
    status: dto.review_status,
    statusLabel: STATUS_LABELS[dto.review_status],
    statusSeverity: STATUS_SEVERITY[dto.review_status],
    isPending: dto.review_status === 'pending',
    attachedCount: dto.attached_count,
    ageLabel: formatAge(dto.age_working_days),
    createdAtLabel: formatDateTime(dto.created_at),
    reviewerLabel: reviewerLabel(dto.reviewed_by_name, dto.reviewed_at),
  }
}

export function mapAnomalyListDtoToDomain(
  dto: AnomalyListDto,
): AnomalyListDomain {
  return { items: dto.items.map(mapAnomalyItemDtoToDomain), total: dto.total }
}

export function mapAnomalyReviewDtoToDomain(
  dto: AnomalyReviewDto,
): AnomalyReviewDomain {
  return {
    id: dto.id,
    status: dto.review_status,
    statusLabel: STATUS_LABELS[dto.review_status],
    reviewerLabel: reviewerLabel(dto.reviewed_by_name, dto.reviewed_at),
  }
}

/** Đọc thân lỗi 409 của API duyệt; trả `null` nếu không đúng dạng có cấu trúc. */
export function mapAnomalyConflictPayload(
  payload: unknown,
): AnomalyConflictDomain | null {
  if (
    typeof payload !== 'object' ||
    payload === null ||
    !('detail' in payload)
  ) {
    return null
  }
  const detail = (payload as { detail: unknown }).detail
  if (typeof detail !== 'object' || detail === null) {
    return null
  }
  const body = detail as {
    review_status?: AnomalyReviewStatus | null
    reviewed_by_name?: string | null
    reviewed_at?: string | null
  }
  return {
    statusLabel: body.review_status
      ? STATUS_LABELS[body.review_status]
      : 'Đã xử lý',
    reviewerName: body.reviewed_by_name ?? null,
    reviewedAtLabel: body.reviewed_at ? formatDateTime(body.reviewed_at) : null,
  }
}
