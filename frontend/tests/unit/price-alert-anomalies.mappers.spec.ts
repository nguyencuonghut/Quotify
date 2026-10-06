import { describe, expect, it } from 'vitest'

import {
  mapAnomalyConflictPayload,
  mapAnomalyItemDtoToDomain,
  mapAnomalyReviewDtoToDomain,
} from '@/api/price-alert-anomalies.mappers'
import type { AnomalyItemDto } from '@/types/price-alert-anomalies'

function dto(overrides: Partial<AnomalyItemDto> = {}): AnomalyItemDto {
  return {
    id: 'event-1',
    material_id: 'material-1',
    material_name: 'Threonine',
    delivery_month: '2026-11-01',
    received_date: '2026-09-15',
    price_new: '970.00',
    median: '25600.00',
    percent_change: '-96.21',
    reference_prices: ['25600.00', '25435.00', '25900.00'],
    reference_point_count: 3,
    quote_id: 'quote-1',
    entered_by_name: 'Lê Thị Hồng',
    review_status: 'pending',
    attached_count: 2,
    age_working_days: 3,
    created_at: '2026-09-15T03:00:00+00:00',
    reviewed_by_name: null,
    reviewed_at: null,
    ...overrides,
  }
}

describe('price alert anomaly mappers', () => {
  it('maps a pending card to readable Vietnamese labels', () => {
    const item = mapAnomalyItemDtoToDomain(dto())

    expect(item).toMatchObject({
      id: 'event-1',
      materialName: 'Threonine',
      deliveryMonthLabel: '11/2026',
      receivedDateLabel: '15/09/2026',
      priceLabel: '970',
      medianLabel: '25.600',
      percentLabel: '▼96,21%',
      direction: 'down',
      referenceLabel: '25.600 · 25.435 · 25.900',
      lowConfidence: false,
      enteredByName: 'Lê Thị Hồng',
      status: 'pending',
      statusLabel: 'Chờ duyệt',
      statusSeverity: 'warn',
      isPending: true,
      attachedCount: 2,
      ageLabel: '3 ngày làm việc',
      reviewerLabel: null,
    })
    expect(item.createdAtLabel).toBe('10:00 15/09/2026')
  })

  it('marks an upward move, a single reference point and a missing enterer', () => {
    const item = mapAnomalyItemDtoToDomain(
      dto({
        percent_change: '41.03',
        reference_point_count: 1,
        entered_by_name: null,
        age_working_days: 0,
      }),
    )

    expect(item.percentLabel).toBe('▲41,03%')
    expect(item.direction).toBe('up')
    expect(item.lowConfidence).toBe(true)
    expect(item.enteredByName).toBe('Không rõ')
    expect(item.ageLabel).toBe('Hôm nay')
  })

  it('labels each review outcome and who decided', () => {
    const accepted = mapAnomalyItemDtoToDomain(
      dto({
        review_status: 'accepted',
        reviewed_by_name: 'Tony',
        reviewed_at: '2026-10-05T06:24:00+00:00',
      }),
    )
    const rejected = mapAnomalyItemDtoToDomain(
      dto({ review_status: 'rejected' }),
    )
    const expired = mapAnomalyItemDtoToDomain(dto({ review_status: 'expired' }))

    expect(accepted.statusLabel).toBe('Đã xác nhận giá đúng')
    expect(accepted.statusSeverity).toBe('success')
    expect(accepted.isPending).toBe(false)
    expect(accepted.reviewerLabel).toBe('Tony · 13:24 05/10/2026')
    expect(rejected.statusLabel).toBe('Đã đánh dấu nhập sai')
    expect(rejected.statusSeverity).toBe('danger')
    expect(expired.statusLabel).toBe('Hết hạn')
    expect(expired.statusSeverity).toBe('secondary')
  })

  it('maps the review response and a 409 conflict payload', () => {
    expect(
      mapAnomalyReviewDtoToDomain({
        id: 'event-1',
        review_status: 'rejected',
        reviewed_by_name: 'Tony',
        reviewed_at: '2026-10-05T06:24:00+00:00',
      }),
    ).toMatchObject({
      id: 'event-1',
      status: 'rejected',
      statusLabel: 'Đã đánh dấu nhập sai',
    })

    const conflict = mapAnomalyConflictPayload({
      detail: {
        message: 'Điểm giá này đã được xử lý.',
        review_status: 'accepted',
        reviewed_by_name: 'An',
        reviewed_at: '2026-10-05T06:24:00+00:00',
      },
    })
    expect(conflict).toMatchObject({
      statusLabel: 'Đã xác nhận giá đúng',
      reviewerName: 'An',
    })
    expect(conflict?.reviewedAtLabel).toBe('13:24 05/10/2026')
    expect(mapAnomalyConflictPayload({ detail: 'x' })).toBeNull()
    expect(mapAnomalyConflictPayload(null)).toBeNull()
  })
})
