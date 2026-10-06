import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/http'
import { usePriceAlertAnomaliesPage } from '@/composables/usePriceAlertAnomaliesPage'
import { useAuthStore } from '@/stores/auth.store'
import type { AnomalyDomain } from '@/types/price-alert-anomalies'

const apiMock = vi.hoisted(() => ({
  listAnomalies: vi.fn(),
  reviewAnomaly: vi.fn(),
}))

vi.mock('@/api/price-alert-anomalies.api', () => apiMock)

function item(overrides: Partial<AnomalyDomain> = {}): AnomalyDomain {
  return {
    id: 'event-1',
    materialId: 'material-1',
    materialName: 'Threonine',
    deliveryMonthLabel: '11/2026',
    receivedDateLabel: '15/09/2026',
    priceLabel: '970',
    medianLabel: '25.600',
    percentLabel: '▼96,21%',
    direction: 'down',
    referenceLabel: '25.600 · 25.435',
    lowConfidence: false,
    quoteId: 'quote-1',
    enteredByName: 'Hồng',
    status: 'pending',
    statusLabel: 'Chờ duyệt',
    statusSeverity: 'warn',
    isPending: true,
    attachedCount: 0,
    ageLabel: 'Hôm nay',
    createdAtLabel: '10:00 15/09/2026',
    reviewerLabel: null,
    ...overrides,
  }
}

function conflict() {
  return new ApiError('conflict', 409, {
    detail: {
      message: 'Điểm giá này đã được xử lý.',
      review_status: 'accepted',
      reviewed_by_name: 'An',
      reviewed_at: '2026-10-05T06:24:00+00:00',
    },
  })
}

describe('usePriceAlertAnomaliesPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useAuthStore().accessToken = 'token-1'
    vi.clearAllMocks()
    apiMock.listAnomalies.mockResolvedValue({ items: [item()], total: 1 })
  })

  it('loads the pending queue with the access token', async () => {
    const page = usePriceAlertAnomaliesPage()

    await page.fetchAnomalies()

    expect(apiMock.listAnomalies).toHaveBeenCalledWith(
      { status: 'pending', limit: 10, offset: 0 },
      'token-1',
    )
    expect(page.anomalies.value).toHaveLength(1)
    expect(page.total.value).toBe(1)
    expect(page.generalError.value).toBeNull()
  })

  it('confirms a card after the dialog and refreshes the list', async () => {
    apiMock.reviewAnomaly.mockResolvedValue({
      id: 'event-1',
      status: 'accepted',
      statusLabel: 'Đã xác nhận giá đúng',
      reviewerLabel: 'Tony · 13:24 05/10/2026',
    })
    const page = usePriceAlertAnomaliesPage()
    await page.fetchAnomalies()

    page.openConfirm(item(), 'accepted')
    expect(page.confirmVisible.value).toBe(true)
    await page.confirmDecision()

    expect(apiMock.reviewAnomaly).toHaveBeenCalledWith(
      'event-1',
      'accepted',
      'token-1',
    )
    expect(apiMock.listAnomalies).toHaveBeenCalledTimes(2)
    expect(page.confirmVisible.value).toBe(false)
    expect(page.successMessage.value).toContain('Threonine')
    expect(page.successMessage.value).toContain('giá đúng')
    expect(page.errorMessage.value).toBeNull()
  })

  it('says who already decided when the card was handled meanwhile (409)', async () => {
    apiMock.reviewAnomaly.mockRejectedValue(conflict())
    const page = usePriceAlertAnomaliesPage()
    await page.fetchAnomalies()

    page.openConfirm(item(), 'rejected')
    await page.confirmDecision()

    expect(page.errorMessage.value).toBe(
      'Điểm giá này đã được xử lý: Đã xác nhận giá đúng bởi An lúc 13:24 05/10/2026.',
    )
    expect(page.confirmVisible.value).toBe(false)
    expect(apiMock.listAnomalies).toHaveBeenCalledTimes(2)
  })

  it.each([
    [403, 'Bạn không có quyền duyệt giá bất thường.'],
    [404, 'Điểm giá không còn tồn tại hoặc không thể duyệt riêng.'],
    [500, 'Không thể xử lý yêu cầu. Vui lòng thử lại.'],
  ])(
    'shows a fixed message for status %s and never the server detail',
    async (status, text) => {
      apiMock.reviewAnomaly.mockRejectedValue(
        new ApiError('secret server detail', status, {
          detail: 'secret server detail',
        }),
      )
      const page = usePriceAlertAnomaliesPage()
      await page.fetchAnomalies()

      page.openConfirm(item(), 'accepted')
      await page.confirmDecision()

      expect(page.errorMessage.value).toBe(text)
      expect(page.errorMessage.value).not.toContain('secret')
    },
  )

  it('ignores a second confirm while one is in flight', async () => {
    let finish: (value: unknown) => void = () => undefined
    apiMock.reviewAnomaly.mockReturnValue(
      new Promise((resolve) => (finish = resolve)),
    )
    const page = usePriceAlertAnomaliesPage()
    await page.fetchAnomalies()
    page.openConfirm(item(), 'accepted')

    const first = page.confirmDecision()
    await page.confirmDecision()
    finish({
      id: 'event-1',
      status: 'accepted',
      statusLabel: '',
      reviewerLabel: null,
    })
    await first

    expect(apiMock.reviewAnomaly).toHaveBeenCalledTimes(1)
  })

  it('switches between the queue and the history and goes back to page one', async () => {
    const page = usePriceAlertAnomaliesPage()
    await page.fetchAnomalies()
    await page.onPageChange({ first: 10, rows: 10 })

    await page.setTab('resolved')

    expect(apiMock.listAnomalies).toHaveBeenLastCalledWith(
      { status: 'resolved', limit: 10, offset: 0 },
      'token-1',
    )
    expect(page.first.value).toBe(0)
    expect(page.tab.value).toBe('resolved')
  })

  it('pages with the offset and keeps a load failure as a fixed message', async () => {
    const page = usePriceAlertAnomaliesPage()
    await page.onPageChange({ first: 20, rows: 20 })
    expect(apiMock.listAnomalies).toHaveBeenLastCalledWith(
      { status: 'pending', limit: 20, offset: 20 },
      'token-1',
    )

    apiMock.listAnomalies.mockRejectedValue(new Error('boom'))
    await page.fetchAnomalies()

    expect(page.generalError.value).toBe(
      'Không thể tải danh sách giá bất thường.',
    )
    expect(page.anomalies.value).toEqual([])
  })

  it('ignores a slower response from an older request (tab switched while loading)', async () => {
    let resolvePending: (value: unknown) => void = () => undefined
    apiMock.listAnomalies.mockImplementation((params: { status: string }) =>
      params.status === 'pending'
        ? new Promise((resolve) => (resolvePending = resolve))
        : Promise.resolve({
            items: [item({ id: 'resolved-1', isPending: false })],
            total: 1,
          }),
    )
    const page = usePriceAlertAnomaliesPage()

    const slow = page.fetchAnomalies()
    await page.setTab('resolved')
    resolvePending({
      items: [item({ id: 'pending-1' }), item({ id: 'pending-2' })],
      total: 2,
    })
    await slow

    expect(page.tab.value).toBe('resolved')
    expect(page.anomalies.value.map((row) => row.id)).toEqual(['resolved-1'])
    expect(page.total.value).toBe(1)
    expect(page.loading.value).toBe(false)
  })

  it('steps back a page when the last row of the last page was reviewed', async () => {
    apiMock.listAnomalies.mockImplementation(({ offset }: { offset: number }) =>
      Promise.resolve(
        offset === 0
          ? { items: [item({ id: 'row-1' })], total: 10 }
          : { items: [], total: 10 },
      ),
    )
    apiMock.reviewAnomaly.mockResolvedValue({
      id: 'event-1',
      status: 'accepted',
      statusLabel: '',
      reviewerLabel: null,
    })
    const page = usePriceAlertAnomaliesPage()
    page.first.value = 10

    await page.fetchAnomalies()

    expect(apiMock.listAnomalies).toHaveBeenLastCalledWith(
      { status: 'pending', limit: 10, offset: 0 },
      'token-1',
    )
    expect(page.first.value).toBe(0)
    expect(page.anomalies.value.map((row) => row.id)).toEqual(['row-1'])
  })

  it('does not let the dialog be closed or replaced while a review is running', async () => {
    let finish: (value: unknown) => void = () => undefined
    apiMock.reviewAnomaly.mockReturnValue(
      new Promise((resolve) => (finish = resolve)),
    )
    const page = usePriceAlertAnomaliesPage()
    await page.fetchAnomalies()
    page.openConfirm(item(), 'accepted')

    const running = page.confirmDecision()
    page.closeConfirm()
    expect(page.confirmVisible.value).toBe(true)

    finish({
      id: 'event-1',
      status: 'accepted',
      statusLabel: '',
      reviewerLabel: null,
    })
    await running

    expect(page.confirmVisible.value).toBe(false)
    expect(page.confirmTarget.value).toBeNull()
  })
})
