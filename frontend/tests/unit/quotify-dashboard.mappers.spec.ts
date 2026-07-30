import { describe, expect, it } from 'vitest'

import {
  mapEntryKpisDtoToDomain,
  mapPriceTrendsDtoToDomain,
  mapWeeklyEntryActivityDtoToDomain,
} from '@/api/quotify-dashboard.mappers'
import type {
  QuotifyEntryKpisDto,
  QuotifyPriceTrendsDto,
  QuotifyWeeklyEntryActivityDto,
} from '@/types/quotify-dashboard'

describe('quotify dashboard mappers', () => {
  it('maps entry KPI dto to frontend domain fields', () => {
    const dto: QuotifyEntryKpisDto = {
      total_quote_count: 12,
      user_kpis: [
        {
          user_id: 'user-1',
          user_email: 'buyer@example.com',
          user_full_name: 'Nguyễn Văn Mua',
          user_label: 'Nguyễn Văn Mua',
          quote_count: 8,
        },
      ],
    }

    expect(mapEntryKpisDtoToDomain(dto)).toEqual({
      totalQuoteCount: 12,
      userKpis: [
        {
          userId: 'user-1',
          userEmail: 'buyer@example.com',
          userFullName: 'Nguyễn Văn Mua',
          userLabel: 'Nguyễn Văn Mua',
          quoteCount: 8,
        },
      ],
    })
  })

  it('maps weekly entry activity dto including warning rows', () => {
    const dto: QuotifyWeeklyEntryActivityDto = {
      week_start: '2026-07-27',
      week_end: '2026-08-02',
      total_quote_count: 7,
      active_user_count: 2,
      users_with_quotes: 1,
      users_without_quotes: 1,
      user_activities: [
        {
          user_id: 'user-1',
          user_email: 'buyer@example.com',
          user_full_name: 'Nguyễn Văn Mua',
          user_label: 'Nguyễn Văn Mua',
          quote_count: 7,
          last_quote_created_at: '2026-07-29T02:00:00+00:00',
          has_warning: false,
        },
        {
          user_id: 'user-2',
          user_email: 'quiet@example.com',
          user_full_name: 'Người chưa nhập',
          user_label: 'Người chưa nhập',
          quote_count: 0,
          last_quote_created_at: null,
          has_warning: true,
        },
      ],
    }

    expect(mapWeeklyEntryActivityDtoToDomain(dto)).toEqual({
      weekStart: '2026-07-27',
      weekEnd: '2026-08-02',
      totalQuoteCount: 7,
      activeUserCount: 2,
      usersWithQuotes: 1,
      usersWithoutQuotes: 1,
      userActivities: [
        {
          userId: 'user-1',
          userEmail: 'buyer@example.com',
          userFullName: 'Nguyễn Văn Mua',
          userLabel: 'Nguyễn Văn Mua',
          quoteCount: 7,
          lastQuoteCreatedAt: '2026-07-29T02:00:00+00:00',
          hasWarning: false,
        },
        {
          userId: 'user-2',
          userEmail: 'quiet@example.com',
          userFullName: 'Người chưa nhập',
          userLabel: 'Người chưa nhập',
          quoteCount: 0,
          lastQuoteCreatedAt: null,
          hasWarning: true,
        },
      ],
    })
  })

  it('maps price trend dto and converts decimal strings to numbers', () => {
    const dto: QuotifyPriceTrendsDto = {
      summary: {
        min_price: '10200.50',
        max_price: '11800.75',
        avg_price: '11001.25',
        total_lines: 4,
        total_quotes: 3,
        purchased_lines: 1,
      },
      points: [
        {
          received_date: '2026-07-20',
          delivery_month: '2026-08-01',
          converted_price_vnd_per_kg: '10500.25',
          supplier_id: 'supplier-1',
          supplier_name: 'Nhà cung cấp A',
          supplier_code: 'NCC-A',
          supplier_type: 'domestic',
          supplier_label: 'NCC-A - Nhà cung cấp A',
          material_id: 'material-1',
          material_name: 'Bắp hạt',
          material_code: 'BAP',
          quote_id: 'quote-1',
          quote_version_id: 'version-1',
          line_id: 'line-1',
          purchased: true,
          purchase_marked_at: '2026-07-20T03:00:00+00:00',
          confirmed_at: '2026-07-20T02:00:00+00:00',
        },
      ],
      purchase_contexts: [
        {
          purchased_line_id: 'line-1',
          quote_id: 'quote-1',
          material_id: 'material-1',
          delivery_month: '2026-08-01',
          purchase_marked_at: '2026-07-20T03:00:00+00:00',
          at_purchase: {
            min_price: '10200.50',
            max_price: '10500.25',
            avg_price: '10350.38',
            total_lines: 2,
            total_quotes: 2,
            purchased_lines: 1,
          },
          after_purchase: {
            min_price: null,
            max_price: null,
            avg_price: null,
            total_lines: 0,
            total_quotes: 0,
            purchased_lines: 0,
          },
        },
      ],
    }

    expect(mapPriceTrendsDtoToDomain(dto)).toMatchObject({
      summary: {
        minPrice: 10200.5,
        maxPrice: 11800.75,
        avgPrice: 11001.25,
        totalLines: 4,
        totalQuotes: 3,
        purchasedLines: 1,
      },
      points: [
        {
          convertedPriceVndPerKg: 10500.25,
          supplierType: 'domestic',
          supplierLabel: 'NCC-A - Nhà cung cấp A',
          purchased: true,
          purchaseMarkedAt: '2026-07-20T03:00:00+00:00',
        },
      ],
      purchaseContexts: [
        {
          purchasedLineId: 'line-1',
          atPurchase: {
            avgPrice: 10350.38,
          },
          afterPurchase: {
            avgPrice: null,
          },
        },
      ],
    })
  })
})
