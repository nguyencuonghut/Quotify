import { describe, expect, it } from 'vitest'
import {
  getPriceAlertStatusBadge,
  mapQuoteLineDtoToDomain,
  mapQuoteVersionDtoToDomain,
  mapQuoteDtoToDomain,
} from '@/api/quotes.mappers'
import type { QuoteLineDto, QuoteVersionDto, QuoteDto } from '@/types/quotes'

describe('quotes.mappers', () => {
  describe('mapQuoteLineDtoToDomain', () => {
    it('correctly maps line DTO to Domain with string number conversion', () => {
      const dto: QuoteLineDto = {
        id: 'line-1',
        material_id: 'mat-1',
        material_code: 'M01',
        material_name: 'Material 1',
        price_original: '120.50',
        currency: 'USD',
        unit: 'MT',
        delivery_month: '2026-08-01',
        line_order: 0,
        exchange_rate: '26120.00',
        exchange_rate_source: 'Vietcombank',
        exchange_rate_source_mode: 'auto',
        exchange_rate_entered_at: '2026-07-28T02:00:00Z',
        exchange_rate_manual_reason: null,
        exchange_rate_actor_id: 'user-1',
        import_tax_rate_percent: '5.00',
        processing_cost_vnd_per_kg: '250.00',
        price_converted_vnd_per_kg: '3397.06',
        note: 'Nhập lại từ báo giá cũ.',
        purchase_marked_at: null,
        purchase_marked_by_id: null,
      }

      const domain = mapQuoteLineDtoToDomain(dto)

      expect(domain.id).toBe('line-1')
      expect(domain.materialId).toBe('mat-1')
      expect(domain.priceOriginal).toBe(120.5)
      expect(domain.exchangeRate).toBe(26120)
      expect(domain.importTaxRatePercent).toBe(5)
      expect(domain.processingCostVndPerKg).toBe(250)
      expect(domain.priceConvertedVndPerKg).toBe(3397.06)
      expect(domain.deliveryMonth).toBe('2026-08-01')
      expect(domain.lineOrder).toBe(0)
      expect(domain.note).toBe('Nhập lại từ báo giá cũ.')
    })

    it('carries the price alert review state of a line and defaults to none', () => {
      const base: QuoteLineDto = {
        id: 'line-3',
        material_id: 'mat-3',
        material_code: 'M03',
        material_name: 'Material 3',
        price_original: '970.00',
        currency: 'VND',
        unit: 'KG',
        delivery_month: '2026-11-01',
        line_order: 0,
        exchange_rate: null,
        exchange_rate_source: null,
        exchange_rate_source_mode: null,
        exchange_rate_entered_at: null,
        exchange_rate_manual_reason: null,
        exchange_rate_actor_id: null,
        import_tax_rate_percent: null,
        processing_cost_vnd_per_kg: null,
        price_converted_vnd_per_kg: '970.00',
        note: null,
        purchase_marked_at: null,
        purchase_marked_by_id: null,
      }

      expect(mapQuoteLineDtoToDomain(base).priceAlertStatus).toBeNull()
      expect(
        mapQuoteLineDtoToDomain({ ...base, price_alert_status: 'pending' }).priceAlertStatus,
      ).toBe('pending')
    })

    it('describes each review state as a badge and shows nothing for a normal line', () => {
      expect(getPriceAlertStatusBadge(null)).toBeNull()
      expect(getPriceAlertStatusBadge('pending')).toMatchObject({
        label: 'Nghi nhập sai, chờ duyệt',
        severity: 'warn',
      })
      expect(getPriceAlertStatusBadge('rejected')).toMatchObject({
        label: 'Đã đánh dấu nhập sai',
        severity: 'danger',
      })
      expect(getPriceAlertStatusBadge('rejected')?.title).toContain('phiếu không bị thay đổi')
      expect(getPriceAlertStatusBadge('accepted')).toMatchObject({
        label: 'Giá đã được xác nhận',
        severity: 'success',
      })
      expect(getPriceAlertStatusBadge('expired')).toMatchObject({
        label: 'Nghi nhập sai, hết hạn duyệt',
        severity: 'secondary',
      })
    })

    it('handles null values for exchange_rate, import_tax_rate_percent and processing_cost', () => {
      const dto: QuoteLineDto = {
        id: 'line-2',
        material_id: 'mat-2',
        material_code: 'M02',
        material_name: 'Material 2',
        price_original: '1000.00',
        currency: 'VND',
        unit: 'KG',
        delivery_month: '2026-08-01',
        line_order: 1,
        exchange_rate: null,
        exchange_rate_source: null,
        exchange_rate_source_mode: null,
        exchange_rate_entered_at: null,
        exchange_rate_manual_reason: null,
        exchange_rate_actor_id: null,
        import_tax_rate_percent: null,
        processing_cost_vnd_per_kg: null,
        price_converted_vnd_per_kg: '1000.00',
        note: null,
        purchase_marked_at: null,
        purchase_marked_by_id: null,
      }

      const domain = mapQuoteLineDtoToDomain(dto)

      expect(domain.exchangeRate).toBeNull()
      expect(domain.importTaxRatePercent).toBeNull()
      expect(domain.processingCostVndPerKg).toBeNull()
      expect(domain.priceConvertedVndPerKg).toBe(1000)
    })
  })

  describe('mapQuoteVersionDtoToDomain', () => {
    it('correctly maps version DTO containing lines', () => {
      const dto: QuoteVersionDto = {
        id: 'v-1',
        quote_id: 'quote-1',
        version_number: 1,
        received_date: '2026-07-28',
        status: 'draft',
        file_id: null,
        is_backfilled: false,
        backfill_reason: null,
        created_by_id: 'user-1',
        created_by_name: 'Nguyễn Văn A',
        confirmed_at: null,
        confirmed_by_id: null,
        created_at: '2026-07-28T02:00:00Z',
        updated_at: '2026-07-28T02:00:00Z',
        lines: [
          {
            id: 'line-1',
            material_id: 'mat-1',
            material_code: 'M01',
            material_name: 'Material 1',
            price_original: '500',
            currency: 'VND',
            unit: 'KG',
            delivery_month: '2026-08-01',
            line_order: 0,
            exchange_rate: null,
            exchange_rate_source: null,
            exchange_rate_source_mode: null,
            exchange_rate_entered_at: null,
            exchange_rate_manual_reason: null,
            exchange_rate_actor_id: null,
            import_tax_rate_percent: null,
            processing_cost_vnd_per_kg: null,
            price_converted_vnd_per_kg: '500',
            note: null,
            purchase_marked_at: null,
            purchase_marked_by_id: null,
          },
        ],
      }

      const domain = mapQuoteVersionDtoToDomain(dto)

      expect(domain.id).toBe('v-1')
      expect(domain.versionNumber).toBe(1)
      expect(domain.createdByName).toBe('Nguyễn Văn A')
      expect(domain.lines).toHaveLength(1)
      expect(domain.lines[0].priceOriginal).toBe(500)
    })
  })

  describe('mapQuoteDtoToDomain', () => {
    it('correctly maps quote DTO containing versions', () => {
      const dto: QuoteDto = {
        id: 'q-1',
        supplier_id: 'supplier-1',
        supplier_name: 'Supplier A',
        supplier_code: 'SUPA',
        created_by_id: 'user-1',
        created_at: '2026-07-28T02:00:00Z',
        updated_at: '2026-07-28T02:00:00Z',
        versions: [],
      }

      const domain = mapQuoteDtoToDomain(dto)

      expect(domain.id).toBe('q-1')
      expect(domain.supplierName).toBe('Supplier A')
      expect(domain.versions).toEqual([])
    })
  })
})
