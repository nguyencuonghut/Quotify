import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import {
  getQuotifyEntryKpis,
  getQuotifyPriceTrends,
  getQuotifyWeeklyEntryActivity,
} from '@/api/quotify-dashboard.api'
import { listMaterialsLookup } from '@/api/materials.api'
import { useAuthStore } from '@/stores/auth.store'
import { useThemeStore } from '@/stores/theme.store'
import type { MaterialDomain } from '@/types/materials'
import type {
  QuotifyDashboardQuery,
  QuotifyDashboardSupplierType,
  QuotifyEntryKpis,
  QuotifyPriceTrendPoint,
  QuotifyPriceTrends,
  QuotifyWeeklyEntryActivity,
  QuotifyWeeklyEntryActivityQuery,
  QuotifyWeeklyEntryUserActivity,
} from '@/types/quotify-dashboard'

interface DashboardMetricCard {
  label: string
  value: string
  detail: string
  icon: string
  tone: 'primary' | 'success' | 'info' | 'warn'
}

interface DashboardUserOption {
  label: string
  value: string
}

interface DeliveryMonthBucket {
  // Tháng NHẬN báo giá (không phải kỳ giao hàng — kỳ giao hàng giờ luôn cố
  // định qua bộ lọc "Kỳ giao hàng", xem `getDefaultDeliveryMonth`), dạng
  // "YYYY-MM-01".
  receivedMonth: string
  label: string
  minPrice: number
  maxPrice: number
  avgPrice: number
  pointCount: number
  purchasedPrice: number | null
  points: QuotifyPriceTrendPoint[]
}

const MAX_COMPARISON_MATERIALS = 3
const MAX_COMPARISON_YEARS = 5
const preferredMaterialCodes = ['CORN']
const preferredMaterialNames = ['ngô hạt', 'ngo hat', 'bắp hạt', 'bap hat']

function formatMoney(value: number | null): string {
  if (value === null || Number.isNaN(value)) {
    return 'Chưa có dữ liệu'
  }

  return `${new Intl.NumberFormat('en-US', {
    maximumFractionDigits: 2,
    minimumFractionDigits: 2,
  }).format(value)} VNĐ/KG`
}

/** Dùng cho chế độ "Giá CNF" — hiện giá gốc USD/MT thay vì giá quy đổi
 * VNĐ/KG, cùng quy ước hiển thị "$..." đã dùng ở nơi khác (ví dụ
 * `formatOriginalPrice` trong QuotesPage.vue). */
function formatUsdPerMt(value: number | null): string {
  if (value === null || Number.isNaN(value)) {
    return 'Chưa có dữ liệu'
  }

  return `$${new Intl.NumberFormat('en-US', {
    maximumFractionDigits: 2,
    minimumFractionDigits: 2,
  }).format(value)} USD/MT`
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat('en-US', {
    maximumFractionDigits: 2,
    minimumFractionDigits: 2,
  }).format(value)
}

function formatInteger(value: number): string {
  return new Intl.NumberFormat('vi-VN').format(value)
}

function formatDateLabel(value: string): string {
  if (!value) {
    return ''
  }

  const [year, month, day] = value.split('-')
  return day && month && year ? `${day}/${month}/${year}` : value
}

function formatMonthLabel(value: string): string {
  if (!value) {
    return ''
  }

  const [year, month] = value.split('-')
  return month && year ? `${month}/${year}` : value
}

/** Ngày cuối cùng của tháng `monthStart` ("YYYY-MM-01"), dạng "YYYY-MM-DD" —
 * dùng cho `receivedDateEnd` khi click-through từ chart "Giá theo kỳ hàng
 * về" (trục X giờ là tháng nhận báo giá, xem `buildDeliveryMonthBuckets`). */
function getMonthEnd(monthStart: string): string {
  const [year, month] = monthStart.split('-').map(Number)
  const lastDay = new Date(year, month, 0).getDate()
  return `${year}-${String(month).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`
}

/** Số tháng `receivedDate` cách kỳ hàng về `deliveryMonth` — dùng làm trục X
 * "tương đối" cho chart mùa vụ (xem docs/quotify/plan-year-over-year-seasonal-comparison-chart.md
 * mục 2): mỗi năm có khoảng ngày nhận báo giá nằm ở vị trí lịch khác nhau
 * hoàn toàn, quy về số tháng trước kỳ giao hàng thì mới so sánh được. Luôn
 * ≤ 0 trong trường hợp bình thường (nhận báo giá trước hoặc đúng tháng hàng
 * về). */
function computeMonthsBeforeDelivery(receivedDate: string, deliveryMonth: string): number {
  const [receivedYear, receivedMonth] = receivedDate.slice(0, 7).split('-').map(Number)
  const [deliveryYear, deliveryMonthNumber] = deliveryMonth.slice(0, 7).split('-').map(Number)
  return (receivedYear * 12 + receivedMonth) - (deliveryYear * 12 + deliveryMonthNumber)
}

/** Chia 1 tháng thành 3 "kỳ" theo quy ước phổ biến trong báo cáo kinh doanh
 * VN: kỳ 1 = ngày 1-10, kỳ 2 = ngày 11-20, kỳ 3 = ngày 21-cuối tháng. */
function computeThirdOfMonth(day: number): number {
  if (day <= 10) return 0
  if (day <= 20) return 1
  return 2
}

/** Khóa nhóm mịn hơn cho chart mùa vụ: số tháng trước kỳ giao hàng
 * (`computeMonthsBeforeDelivery`) nhân 3 rồi cộng thêm kỳ trong tháng (0-2)
 * — vẫn là 1 số nguyên tuyến tính theo thời gian (mỗi lần tăng 1 đơn vị là
 * qua 1 kỳ ~10 ngày), nên vẫn sắp đúng bằng so sánh số học thông thường. */
function computeThirdsBeforeDelivery(receivedDate: string, deliveryMonth: string): number {
  const monthOffset = computeMonthsBeforeDelivery(receivedDate, deliveryMonth)
  const day = Number(receivedDate.slice(8, 10))
  return monthOffset * 3 + computeThirdOfMonth(day)
}

/** Ngược lại `computeThirdsBeforeDelivery`: tách khóa nhóm gộp thành số
 * tháng trước kỳ giao hàng + kỳ trong tháng (0-2), dùng cho label và
 * click-through. Dùng `Math.floor` (không phải chia nguyên thông thường) để
 * ra đúng kết quả cho `combinedOffset` âm. */
function decomposeThirdOffset(combinedOffset: number): { monthOffset: number; third: number } {
  const monthOffset = Math.floor(combinedOffset / 3)
  const third = combinedOffset - monthOffset * 3
  return { monthOffset, third }
}

/** Nhãn trục X CHỈ hiện tháng tương đối (`T-11`, `T0 (giao hàng)`), KHÔNG hiện
 * kỳ trong tháng — dù mỗi tháng có 3 bucket (`computeThirdsBeforeDelivery`),
 * ghi thêm "(kỳ N)" vào label khiến tick nào cũng hiện thông tin kỳ, và vì
 * Chart.js tự bỏ bớt tick để tránh chật (autoSkip), bước nhảy ~3 khớp đúng số
 * bucket/tháng nên MỌI tick còn hiện ra vô tình rơi vào cùng 1 kỳ tương đối
 * (luôn "kỳ 2") — trông như lỗi dù dữ liệu bên dưới vẫn đúng (mỗi điểm trên
 * đường vẫn đúng vị trí, tooltip hover từng điểm vẫn đúng kỳ của điểm đó).
 * Kỳ cụ thể vẫn hiện đầy đủ trong tooltip qua `formatSeriesRowLabel`. */
function formatThirdOffsetLabel(offsetKey: string): string {
  const { monthOffset } = decomposeThirdOffset(Number(offsetKey))
  return monthOffset === 0 ? 'T0 (giao hàng)' : `T${monthOffset}`
}

/** Khoảng ngày nhận báo giá thực tế của 1 kỳ (0-2) trong tháng `monthStart`
 * ("YYYY-MM-01") — dùng để lọc `/quotes` đúng khoảng ~10 ngày đã click, thay
 * vì cả tháng, vì trục X giờ đã mịn hơn theo kỳ. */
function getThirdOfMonthDateRange(monthStart: string, third: number): { start: string; end: string } {
  const [year, month] = monthStart.slice(0, 7).split('-').map(Number)
  const monthPrefix = `${year}-${String(month).padStart(2, '0')}`
  if (third === 0) {
    return { start: `${monthPrefix}-01`, end: `${monthPrefix}-10` }
  }
  if (third === 1) {
    return { start: `${monthPrefix}-11`, end: `${monthPrefix}-20` }
  }
  const lastDay = new Date(year, month, 0).getDate()
  return { start: `${monthPrefix}-21`, end: `${monthPrefix}-${String(lastDay).padStart(2, '0')}` }
}

/** Khóa nhóm mịn hơn cho chart "diễn biến theo ngày báo giá": ngày bắt đầu
 * của kỳ (0-2, xem `computeThirdOfMonth`) chứa `date` — "YYYY-MM-01"/"-11"/
 * "-21". Vẫn là chuỗi ISO nên `localeCompare` mặc định của
 * `buildGroupedComparisonBuckets` sắp đúng thứ tự thời gian, không cần
 * `compareKeys` tùy chỉnh như chart mùa vụ (khóa ở đó là số âm dạng chuỗi). */
function computeThirdPeriodStart(date: string): string {
  const [year, month] = date.slice(0, 7).split('-')
  const day = Number(date.slice(8, 10))
  const third = computeThirdOfMonth(day)
  const startDay = third === 0 ? '01' : third === 1 ? '11' : '21'
  return `${year}-${month}-${startDay}`
}

/** Ngày cuối của kỳ mà `periodStart` (kết quả của `computeThirdPeriodStart`)
 * đại diện — dùng cho `receivedDateEnd` khi click-through, để lọc `/quotes`
 * đúng khoảng ~10 ngày đã click thay vì cả tháng. */
function getThirdPeriodEnd(periodStart: string): string {
  const [year, month] = periodStart.slice(0, 7).split('-')
  const day = Number(periodStart.slice(8, 10))
  const third = computeThirdOfMonth(day)
  return getThirdOfMonthDateRange(`${year}-${month}-01`, third).end
}

/** Cộng `months` (có thể âm) vào `monthStart` (dạng "YYYY-MM-01" hoặc
 * "YYYY-MM-DD", chỉ dùng phần năm-tháng), trả về "YYYY-MM-01" của tháng kết
 * quả — dùng để suy ra tháng lịch thực tế từ 1 offset tương đối. */
function addMonthsToMonthStart(monthStart: string, months: number): string {
  const [year, month] = monthStart.slice(0, 7).split('-').map(Number)
  const totalMonths = year * 12 + (month - 1) + months
  const resultYear = Math.floor(totalMonths / 12)
  const resultMonth = totalMonths - resultYear * 12 + 1
  return `${resultYear}-${String(resultMonth).padStart(2, '0')}-01`
}

function toDateInputValue(value: Date | null): string | null {
  if (!value) {
    return null
  }

  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

/** Mặc định "kỳ giao hàng" cho chart "Giá theo kỳ hàng về" = tháng hiện tại
 * + 2 (ví dụ hôm nay tháng 8 → mặc định tháng 10) — chart này giờ luôn cần 1
 * kỳ giao hàng cố định để làm trục X thành tháng nhận báo giá. */
function getDefaultDeliveryMonth(): Date {
  const now = new Date()
  return new Date(now.getFullYear(), now.getMonth() + 2, 1)
}

function getWeekStartDate(value: Date): Date {
  const weekStart = new Date(value.getFullYear(), value.getMonth(), value.getDate())
  const day = weekStart.getDay()
  const diff = day === 0 ? -6 : 1 - day
  weekStart.setDate(weekStart.getDate() + diff)
  weekStart.setHours(0, 0, 0, 0)
  return weekStart
}

function normalizeLookupText(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim()
}

function formatSupplierType(value: QuotifyDashboardSupplierType): string {
  return value
    .split(',')
    .map((type) => (type === 'domestic' ? 'Nội địa' : 'Quốc tế'))
    .join(', ')
}

function formatDateTimeLabel(value: string | null): string {
  if (!value) {
    return '-'
  }

  const parsedDate = new Date(value)
  if (Number.isNaN(parsedDate.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat('vi-VN', {
    dateStyle: 'short',
    timeStyle: 'short',
    timeZone: 'Asia/Ho_Chi_Minh',
  }).format(parsedDate)
}

function formatWeekRangeLabel(weekStart: string, weekEnd: string): string {
  return `${formatDateLabel(weekStart)} - ${formatDateLabel(weekEnd)}`
}

function findDefaultMaterialId(materials: MaterialDomain[]): string | null {
  const byCode = materials.find((material) =>
    preferredMaterialCodes.includes(material.code.toUpperCase()),
  )
  if (byCode) {
    return byCode.id
  }

  const byName = materials.find((material) =>
    preferredMaterialNames.includes(normalizeLookupText(material.name)),
  )
  return byName?.id ?? null
}

function cssVar(name: string, fallback: string): string {
  if (typeof window === 'undefined') {
    return fallback
  }

  return (
    getComputedStyle(document.documentElement).getPropertyValue(name).trim() ||
    fallback
  )
}

function buildTooltipLabel(
  point: QuotifyPriceTrendPoint,
  getPrice: (point: QuotifyPriceTrendPoint) => number = (point) => point.convertedPriceVndPerKg,
  formatPrice: (value: number | null) => string = formatMoney,
): string {
  return [
    point.supplierLabel,
    formatSupplierType(point.supplierType),
    formatDateLabel(point.receivedDate),
    formatMonthLabel(point.deliveryMonth),
    formatPrice(getPrice(point)),
  ].join(' | ')
}

/** Tooltip HTML dùng chung 1 phần tử, tái sử dụng giữa các lần render thay
 * vì tạo/xóa DOM mỗi lần hover — theo đúng ví dụ chính thức của Chart.js cho
 * external tooltip. */
function getOrCreateChartTooltipElement(canvas: HTMLCanvasElement): HTMLDivElement {
  const parent = canvas.parentNode as HTMLElement
  let tooltipEl = parent.querySelector<HTMLDivElement>('.quotify-chart-tooltip')
  if (!tooltipEl) {
    tooltipEl = document.createElement('div')
    tooltipEl.className = 'quotify-chart-tooltip'
    parent.appendChild(tooltipEl)
  }
  return tooltipEl
}

function buildTooltipRowElement(text: string, swatchColor: string): HTMLDivElement {
  const row = document.createElement('div')
  row.className = 'quotify-chart-tooltip__row'

  const swatch = document.createElement('span')
  swatch.className = 'quotify-chart-tooltip__swatch'
  swatch.style.backgroundColor = swatchColor

  const label = document.createElement('span')
  label.textContent = text

  row.append(swatch, label)
  return row
}

const TOOLTIP_SAMPLE_SIZE = 5

interface RepresentativeTooltipPoint {
  point: QuotifyPriceTrendPoint
  role: string | null
}

/** Chọn tối đa 5 báo giá tiêu biểu nhất cho tooltip (thay vì 5 dòng đầu theo
 * thứ tự ngẫu nhiên): giá thấp nhất, giá cao nhất, báo giá mới nhất, và các
 * báo giá gần giá trung bình nhất (ưu tiên NCC khác nhau để đa dạng nguồn).
 * Mỗi dòng được gắn nhãn vai trò (`role`) để người dùng thấy ngay dòng nào
 * là giá thấp nhất/cao nhất — không chỉ ngầm định qua vị trí — theo phản hồi
 * người dùng ngày 12/08/2026 ("báo giá có giá thấp nhất nên được hiển thị"). */
function pickRepresentativeTooltipPoints(
  points: QuotifyPriceTrendPoint[],
  avgPrice: number,
  getPrice: (point: QuotifyPriceTrendPoint) => number = (point) => point.convertedPriceVndPerKg,
): RepresentativeTooltipPoint[] {
  const selected: RepresentativeTooltipPoint[] = []
  const usedIds = new Set<string>()
  const usedSupplierIds = new Set<string>()

  const take = (point: QuotifyPriceTrendPoint | undefined, role: string | null) => {
    if (!point || usedIds.has(point.lineId)) {
      return
    }
    selected.push({ point, role })
    usedIds.add(point.lineId)
    usedSupplierIds.add(point.supplierId)
  }

  const byPriceAsc = [...points].sort((left, right) => getPrice(left) - getPrice(right))
  take(byPriceAsc[0], 'Giá thấp nhất')
  take(byPriceAsc[byPriceAsc.length - 1], 'Giá cao nhất')

  if (points.length <= TOOLTIP_SAMPLE_SIZE) {
    for (const point of points) {
      take(point, null)
    }
    return selected
  }

  const byReceivedDateDesc = [...points].sort((left, right) =>
    right.receivedDate.localeCompare(left.receivedDate),
  )
  take(byReceivedDateDesc[0], 'Mới nhất')

  const byDistanceToAvg = [...points].sort(
    (left, right) =>
      Math.abs(getPrice(left) - avgPrice) - Math.abs(getPrice(right) - avgPrice),
  )
  for (const point of byDistanceToAvg) {
    if (selected.length >= TOOLTIP_SAMPLE_SIZE) {
      break
    }
    if (!usedSupplierIds.has(point.supplierId)) {
      take(point, 'Gần giá trung bình')
    }
  }
  for (const point of byDistanceToAvg) {
    if (selected.length >= TOOLTIP_SAMPLE_SIZE) {
      break
    }
    take(point, 'Gần giá trung bình')
  }

  return selected
}

function buildDeliveryMonthBuckets(
  points: QuotifyPriceTrendPoint[],
  // Mặc định lấy giá quy đổi VNĐ/KG; chế độ "Giá CNF" truyền vào
  // `(point) => point.priceOriginal` để dùng giá gốc USD thay thế.
  getPrice: (point: QuotifyPriceTrendPoint) => number = (point) => point.convertedPriceVndPerKg,
): DeliveryMonthBucket[] {
  const bucketMap = new Map<string, QuotifyPriceTrendPoint[]>()
  for (const point of points) {
    const receivedMonthKey = `${point.receivedDate.slice(0, 7)}-01`
    bucketMap.set(receivedMonthKey, [
      ...(bucketMap.get(receivedMonthKey) ?? []),
      point,
    ])
  }

  return Array.from(bucketMap.entries())
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([receivedMonthKey, bucketPoints]) => {
      const prices = bucketPoints.map(getPrice)
      const purchasedPoint = bucketPoints.find((point) => point.purchased)

      return {
        receivedMonth: receivedMonthKey,
        label: formatMonthLabel(receivedMonthKey),
        minPrice: Math.min(...prices),
        maxPrice: Math.max(...prices),
        avgPrice:
          prices.reduce((total, current) => total + current, 0) / prices.length,
        pointCount: bucketPoints.length,
        purchasedPrice: purchasedPoint ? getPrice(purchasedPoint) : null,
        points: bucketPoints,
      }
    })
}

export interface MaterialTrendResult {
  materialId: string
  materialName: string
  points: QuotifyPriceTrendPoint[]
}

interface MaterialComparisonSeriesPoint {
  materialId: string
  materialName: string
  avgPrice: number | null
  minPrice: number | null
  maxPrice: number | null
  pointCount: number
}

interface MaterialComparisonBucket {
  // Khóa nhóm dùng chung cho cả 2 chart: chart "theo kỳ hàng về" nhóm theo
  // deliveryMonth, chart "diễn biến theo ngày báo giá" nhóm theo tháng của
  // receivedDate — tên trung tính để 1 hàm build dùng được cho cả hai.
  groupKey: string
  label: string
  series: MaterialComparisonSeriesPoint[]
  differenceLines: string[]
}

function formatPercent(value: number): string {
  return `${value.toFixed(2)}%`
}

/** So chênh lệch giá giữa các mặt hàng được chọn tại 1 kỳ giao hàng — bỏ
 * qua mặt hàng chưa có báo giá tháng đó (avgPrice null). Lấy mặt hàng rẻ
 * nhất làm mốc so sánh cho các mặt hàng còn lại — hữu ích cho quyết định
 * thay thế nguyên liệu, không chỉ đơn thuần liệt kê giá. */
function buildPriceDifferenceLines(
  series: MaterialComparisonSeriesPoint[],
  // "Giá CNF": giá trong `series` đã tính theo giá gốc USD (xem `getPrice` ở
  // `buildGroupedComparisonBuckets`) — chỉ cần đổi formatter hiển thị sang
  // `formatUsdPerMt` để đơn vị khớp với phần còn lại của tooltip.
  formatPrice: (value: number) => string = formatMoney,
): string[] {
  const priced = series.filter(
    (entry): entry is MaterialComparisonSeriesPoint & { avgPrice: number } =>
      entry.avgPrice !== null,
  )
  if (priced.length < 2) {
    return []
  }

  const cheapest = priced.reduce((lowest, entry) =>
    entry.avgPrice < lowest.avgPrice ? entry : lowest,
  )

  return priced
    .filter((entry) => entry.materialId !== cheapest.materialId)
    .map((entry) => {
      const diff = entry.avgPrice - cheapest.avgPrice
      const percent = (diff / cheapest.avgPrice) * 100
      return `${entry.materialName} cao hơn ${cheapest.materialName}: +${formatPrice(diff)} (+${formatPercent(percent)})`
    })
}

/** Nhóm điểm dữ liệu của nhiều mặt hàng (hoặc nhiều năm, xem chart mùa vụ)
 * theo 1 khóa bất kỳ (kỳ giao hàng, tháng nhận báo giá, hoặc số tháng trước
 * kỳ giao hàng — do `getGroupKey` quyết định), tính avg/min/max/số báo giá +
 * callout chênh lệch mỗi nhóm. Dùng chung cho 3 chart so sánh trên Dashboard.
 *
 * `compareKeys`/`formatLabel` mặc định đúng cho khóa là chuỗi ngày lịch ISO
 * (`"2026-07-01"` sắp đúng thứ tự thời gian bằng `localeCompare`) — nhưng
 * SAI cho khóa là số nguyên có dấu dạng chuỗi (ví dụ chart mùa vụ dùng
 * "-11"/"-10": so ký tự cho "-10" > "-11", ngược thứ tự số học đúng là
 * -11 < -10) — truyền tham số tùy chỉnh cho các trường hợp đó. */
function buildGroupedComparisonBuckets(
  materialResults: MaterialTrendResult[],
  getGroupKey: (point: QuotifyPriceTrendPoint) => string,
  options?: {
    compareKeys?: (left: string, right: string) => number
    formatLabel?: (groupKey: string) => string
    // "Giá CNF": truyền `(point) => point.priceOriginal` để tính avg/min/max
    // theo giá gốc USD thay vì giá quy đổi VNĐ/KG mặc định.
    getPrice?: (point: QuotifyPriceTrendPoint) => number
    // "Giá CNF": truyền `formatUsdPerMt` để callout chênh lệch giá hiện đúng
    // đơn vị USD/MT thay vì VNĐ/KG mặc định.
    formatPrice?: (value: number) => string
  },
): MaterialComparisonBucket[] {
  const compareKeys = options?.compareKeys ?? ((left, right) => left.localeCompare(right))
  const formatLabel = options?.formatLabel ?? formatMonthLabel
  const getPrice = options?.getPrice ?? ((point) => point.convertedPriceVndPerKg)
  const formatPrice = options?.formatPrice ?? formatMoney

  const groupKeys = new Set<string>()
  for (const result of materialResults) {
    for (const point of result.points) {
      groupKeys.add(getGroupKey(point))
    }
  }

  return Array.from(groupKeys)
    .sort(compareKeys)
    .map((groupKey) => {
      const series = materialResults.map((result) => {
        const pointsInGroup = result.points.filter((point) => getGroupKey(point) === groupKey)
        const pointCount = pointsInGroup.length
        const prices = pointsInGroup.map(getPrice)
        const avgPrice =
          pointCount === 0 ? null : prices.reduce((total, price) => total + price, 0) / pointCount

        return {
          materialId: result.materialId,
          materialName: result.materialName,
          avgPrice,
          minPrice: pointCount === 0 ? null : Math.min(...prices),
          maxPrice: pointCount === 0 ? null : Math.max(...prices),
          pointCount,
        }
      })

      return {
        groupKey,
        label: formatLabel(groupKey),
        series,
        differenceLines: buildPriceDifferenceLines(series, formatPrice),
      }
    })
}

/** "Giá CNF": chỉ các báo giá chào bằng USD/MT mới có ý nghĩa so sánh theo
 * giá gốc (CNF) — bỏ báo giá VND/KG khi bật chế độ này. Dùng chung cho cả 3
 * chart có tick "Giá CNF" (chart đơn 1 mặt hàng + 2 chart so sánh nhiều mặt
 * hàng/năm). */
function filterCnfPoints(
  points: QuotifyPriceTrendPoint[],
  onlyCnf: boolean,
): QuotifyPriceTrendPoint[] {
  if (!onlyCnf) {
    return points
  }
  return points.filter(
    (point) => point.currency.toUpperCase() === 'USD' && point.unit.toUpperCase() === 'MT',
  )
}

/** Định dạng dòng tóm tắt TB/Thấp/Cao trong tooltip của 2 chart so sánh
 * nhiều mặt hàng/năm — chuyển sang giá gốc USD/MT khi "Giá CNF" bật (giá trị
 * trong `entry` đã được tính đúng theo field USD nhờ `getPrice` truyền vào
 * `buildGroupedComparisonBuckets`, ở đây chỉ cần đổi cách hiển thị). */
function formatComparisonPriceTriplet(
  entry: MaterialComparisonSeriesPoint,
  onlyCnf: boolean,
): string {
  if (entry.avgPrice === null || entry.minPrice === null || entry.maxPrice === null) {
    return 'Chưa có báo giá'
  }
  const formatValue = onlyCnf ? (value: number) => `$${formatNumber(value)}` : formatNumber
  const unitLabel = onlyCnf ? 'USD/MT' : 'VNĐ/KG'
  return `TB ${formatValue(entry.avgPrice)} (Thấp ${formatValue(entry.minPrice)} – Cao ${formatValue(entry.maxPrice)}) ${unitLabel} (${entry.pointCount} báo giá)`
}

export function useDashboardPage() {
  const authStore = useAuthStore()
  const themeStore = useThemeStore()
  const router = useRouter()

  const entryKpis = ref<QuotifyEntryKpis | null>(null)
  const priceTrends = ref<QuotifyPriceTrends | null>(null)
  const weeklyEntryActivity = ref<QuotifyWeeklyEntryActivity | null>(null)
  const materials = ref<MaterialDomain[]>([])
  const weeklyUserOptions = ref<DashboardUserOption[]>([])
  const isLoading = ref(false)
  const isLoadingWeeklyEntry = ref(false)
  const isLoadingLookups = ref(false)
  const errorMessage = ref<string | null>(null)

  const selectedMaterialId = ref<string | null>(null)
  const deliveryMonth = ref<Date | null>(getDefaultDeliveryMonth())
  const receivedDateStart = ref<Date | null>(null)
  const receivedDateEnd = ref<Date | null>(null)
  // "Giá CNF": chỉ tính các báo giá USD/MT và hiển thị giá gốc (USD) thay vì
  // giá quy đổi VNĐ/KG — mặc định untick (vẫn dùng VNĐ/KG như trước).
  const showCnfOnly = ref(false)
  const selectedWeek = ref<Date | null>(getWeekStartDate(new Date()))
  const selectedWeeklyUserId = ref<string | null>(null)

  // Chart "diễn biến giá theo ngày báo giá cho 1 kỳ giao hàng cố định" —
  // bộ lọc độc lập với bộ lọc chung của Dashboard (kỳ giao hàng ở đây luôn
  // là 1 giá trị cố định người dùng chọn, không phải trục biến thiên).
  const historyDeliveryMonth = ref<Date | null>(null)
  const historyMaterialIds = ref<string[]>([])
  const historyTrendResults = ref<MaterialTrendResult[]>([])
  const historyBandVisibility = ref<Record<string, boolean>>({})
  // "Giá CNF" riêng cho chart này — panel độc lập với bộ lọc chung Dashboard,
  // nên không dùng chung `showCnfOnly` ở trên.
  const historyShowCnfOnly = ref(false)

  const historyBuckets = computed(() => {
    const results = historyShowCnfOnly.value
      ? historyTrendResults.value.map((result) => ({
        ...result,
        points: filterCnfPoints(result.points, true),
      }))
      : historyTrendResults.value

    return buildGroupedComparisonBuckets(
      results,
      (point) => computeThirdPeriodStart(point.receivedDate),
      {
        formatLabel: formatDateLabel,
        getPrice: historyShowCnfOnly.value ? (point) => point.priceOriginal : undefined,
        formatPrice: historyShowCnfOnly.value ? formatUsdPerMt : undefined,
      },
    )
  })

  async function loadPriceHistory() {
    const materialIds = historyMaterialIds.value.slice(0, MAX_COMPARISON_MATERIALS)
    if (materialIds.length < 2 || !historyDeliveryMonth.value) {
      historyTrendResults.value = []
      return
    }

    const fixedDeliveryMonth = toDateInputValue(historyDeliveryMonth.value)
    const responses = await Promise.all(
      materialIds.map((materialId) =>
        getQuotifyPriceTrends(
          { materialId, deliveryMonth: fixedDeliveryMonth },
          authStore.accessToken,
        ),
      ),
    )

    historyTrendResults.value = materialIds.map((materialId, index) => ({
      materialId,
      materialName:
        materials.value.find((material) => material.id === materialId)?.name ?? materialId,
      points: responses[index].points,
    }))

    for (const materialId of materialIds) {
      if (!(materialId in historyBandVisibility.value)) {
        historyBandVisibility.value[materialId] = true
      }
    }
  }

  // Chart "so sánh giá theo mùa vụ qua các năm" — 1 mặt hàng cố định, 1 tháng
  // hàng về cố định (chỉ tháng, không năm), so sánh nhiều NĂM cho cùng tháng
  // đó. Bộ lọc độc lập với bộ lọc chung của Dashboard và 3 panel kia.
  const seasonalMaterialId = ref<string | null>(null)
  const seasonalMonth = ref<number | null>(null)
  const seasonalYears = ref<number[]>([])
  const seasonalTrendResults = ref<MaterialTrendResult[]>([])
  const seasonalBandVisibility = ref<Record<string, boolean>>({})
  // "Giá CNF" riêng cho chart này — panel độc lập với bộ lọc chung Dashboard,
  // nên không dùng chung `showCnfOnly` ở trên.
  const seasonalShowCnfOnly = ref(false)

  const seasonalAvailableYears = computed<number[]>(() => {
    const currentYear = new Date().getFullYear()
    return Array.from({ length: MAX_COMPARISON_YEARS }, (_, index) => currentYear - index)
  })

  const seasonalBuckets = computed<MaterialComparisonBucket[]>(() => {
    const results = seasonalShowCnfOnly.value
      ? seasonalTrendResults.value.map((result) => ({
        ...result,
        points: filterCnfPoints(result.points, true),
      }))
      : seasonalTrendResults.value

    return buildGroupedComparisonBuckets(
      results,
      (point) => String(computeThirdsBeforeDelivery(point.receivedDate, point.deliveryMonth)),
      {
        compareKeys: (left, right) => Number(left) - Number(right),
        formatLabel: formatThirdOffsetLabel,
        getPrice: seasonalShowCnfOnly.value ? (point) => point.priceOriginal : undefined,
        formatPrice: seasonalShowCnfOnly.value ? formatUsdPerMt : undefined,
      },
    )
  })

  async function loadSeasonalComparison() {
    const years = seasonalYears.value.slice(0, MAX_COMPARISON_YEARS)
    if (years.length < 2 || !seasonalMaterialId.value || !seasonalMonth.value) {
      seasonalTrendResults.value = []
      return
    }

    const materialId = seasonalMaterialId.value
    const paddedMonth = String(seasonalMonth.value).padStart(2, '0')
    const responses = await Promise.all(
      years.map((year) =>
        getQuotifyPriceTrends(
          { materialId, deliveryMonth: `${year}-${paddedMonth}-01` },
          authStore.accessToken,
        ),
      ),
    )

    seasonalTrendResults.value = years.map((year, index) => ({
      materialId: String(year),
      materialName: String(year),
      points: responses[index].points,
    }))

    for (const year of years) {
      const key = String(year)
      if (!(key in seasonalBandVisibility.value)) {
        seasonalBandVisibility.value[key] = true
      }
    }
  }

  const queryParams = computed<QuotifyDashboardQuery>(() => ({
    materialId: selectedMaterialId.value,
    deliveryMonth: toDateInputValue(deliveryMonth.value),
    receivedDateStart: toDateInputValue(receivedDateStart.value),
    receivedDateEnd: toDateInputValue(receivedDateEnd.value),
  }))

  const weeklyEntryQueryParams = computed<QuotifyWeeklyEntryActivityQuery>(() => ({
    weekStart: selectedWeek.value
      ? toDateInputValue(getWeekStartDate(selectedWeek.value))
      : null,
    userId: selectedWeeklyUserId.value,
  }))

  const userKpis = computed(() => entryKpis.value?.userKpis ?? [])
  const weeklyUserActivities = computed<QuotifyWeeklyEntryUserActivity[]>(
    () => weeklyEntryActivity.value?.userActivities ?? [],
  )
  const weeklyWarningUsers = computed(() =>
    weeklyUserActivities.value.filter((activity) => activity.hasWarning),
  )
  const hasWeeklyEntryData = computed(() => weeklyUserActivities.value.length > 0)
  const weeklyEntryPeriodLabel = computed(() =>
    weeklyEntryActivity.value
      ? formatWeekRangeLabel(
        weeklyEntryActivity.value.weekStart,
        weeklyEntryActivity.value.weekEnd,
      )
      : 'Tuần hiện tại',
  )
  const weeklyEntryMetricCards = computed<DashboardMetricCard[]>(() => [
    {
      label: 'Báo giá tuần',
      value: formatInteger(weeklyEntryActivity.value?.totalQuoteCount ?? 0),
      detail: weeklyEntryPeriodLabel.value,
      icon: 'pi pi-calendar-clock',
      tone: 'primary',
    },
    {
      label: 'User đã nhập',
      value: `${formatInteger(weeklyEntryActivity.value?.usersWithQuotes ?? 0)} / ${formatInteger(weeklyEntryActivity.value?.activeUserCount ?? 0)}`,
      detail: 'Có ít nhất 1 phiếu trong tuần',
      icon: 'pi pi-user-check',
      tone: 'success',
    },
    {
      label: 'User chưa nhập',
      value: formatInteger(weeklyEntryActivity.value?.usersWithoutQuotes ?? 0),
      detail:
        (weeklyEntryActivity.value?.usersWithoutQuotes ?? 0) > 0
          ? 'Cần nhắc nhập báo giá'
          : 'Không có cảnh báo',
      icon: 'pi pi-exclamation-triangle',
      tone:
        (weeklyEntryActivity.value?.usersWithoutQuotes ?? 0) > 0
          ? 'warn'
          : 'success',
    },
  ])
  const trendPoints = computed(() =>
    filterCnfPoints(priceTrends.value?.points ?? [], showCnfOnly.value),
  )
  const hasTrendData = computed(() => trendPoints.value.length > 0)
  const deliveryMonthBuckets = computed(() =>
    buildDeliveryMonthBuckets(
      trendPoints.value,
      showCnfOnly.value ? (point) => point.priceOriginal : undefined,
    ),
  )

  const chartLabels = computed(() =>
    deliveryMonthBuckets.value.map((bucket) => bucket.label),
  )

  // Màu đại diện MẶT HÀNG (hoặc NĂM, ở chart mùa vụ) — không phải vai trò
  // thống kê như chart đơn 1 mặt hàng, nên không tái dùng accent/success/
  // warning/danger đã có ý nghĩa riêng ở chart đó. Cần đủ MAX_COMPARISON_YEARS
  // (5) màu riêng biệt — dùng chung mảng này cho cả 3 chart so sánh, kể cả
  // khi chỉ 2-3 mặt hàng, để không phải theo dõi 2 palette khác nhau. Thiếu
  // màu sẽ khiến 2 series trùng màu khi chọn đủ 4-5 năm (bug thật đã gặp
  // ngày 13/08/2026 khi mảng này chỉ có 3 màu nhưng chart mùa vụ cho chọn
  // tới 5 năm).
  const MATERIAL_COMPARISON_COLORS = ['#2563eb', '#db2777', '#0d9488', '#d97706', '#7c3aed']

  // Dùng chung cho cả 2 chart so sánh nhiều mặt hàng (theo kỳ hàng về, và
  // theo ngày báo giá cho 1 kỳ hàng về cố định) — chỉ khác nguồn buckets/
  // trend-results/band-visibility truyền vào.
  function buildComparisonChartData(
    buckets: MaterialComparisonBucket[],
    trendResults: MaterialTrendResult[],
    bandVisibility: Record<string, boolean>,
  ) {
    const panel = cssVar('--app-surface-panel', '#ffffff')
    const datasets: Record<string, unknown>[] = []

    const seriesValues = (
      materialId: string,
      key: keyof Pick<MaterialComparisonSeriesPoint, 'avgPrice' | 'minPrice' | 'maxPrice'>,
    ): (number | null)[] =>
      buckets.map((bucket: MaterialComparisonBucket) => {
        const entry = bucket.series.find(
          (candidate: MaterialComparisonSeriesPoint) => candidate.materialId === materialId,
        )
        return entry ? entry[key] : null
      })

    trendResults.forEach((result, index) => {
      const color = MATERIAL_COMPARISON_COLORS[index % MATERIAL_COMPARISON_COLORS.length]

      // Dải giá thấp-cao: vẽ bằng 2 dataset vô hình (max, min) tô màu vùng
      // giữa chúng (`fill` trỏ vào index dataset max) — Chart.js không hỗ
      // trợ "band" trực tiếp, đây là cách chuẩn để mô phỏng. Mặc định hiện,
      // người dùng untick để ẩn riêng từng mặt hàng (không ẩn đường trung
      // bình) — theo phản hồi người dùng ngày 12/08/2026.
      if (bandVisibility[result.materialId]) {
        const maxDatasetIndex = datasets.length
        datasets.push({
          label: `${result.materialName} (cao nhất)`,
          data: seriesValues(result.materialId, 'maxPrice'),
          borderColor: 'transparent',
          backgroundColor: 'transparent',
          pointRadius: 0,
          borderWidth: 0,
          tension: 0.28,
          spanGaps: false,
          fill: false,
        })
        datasets.push({
          label: `${result.materialName} (thấp nhất)`,
          data: seriesValues(result.materialId, 'minPrice'),
          borderColor: 'transparent',
          // Nền tối làm màu dải bị "chìm" nếu dùng chung 1 mức alpha thấp
          // cho cả 2 theme (đặc biệt màu gần tông nền tối) — tăng alpha ở
          // dark mode để dải vẫn rõ, theo phản hồi người dùng ngày 13/08/2026.
          backgroundColor: `${color}${themeStore.mode === 'dark' ? '4d' : '26'}`,
          pointRadius: 0,
          borderWidth: 0,
          tension: 0.28,
          spanGaps: false,
          fill: maxDatasetIndex,
        })
      }

      datasets.push({
        label: result.materialName,
        data: seriesValues(result.materialId, 'avgPrice'),
        borderColor: color,
        backgroundColor: 'transparent',
        pointBackgroundColor: color,
        pointBorderColor: panel,
        pointRadius: 4,
        tension: 0.28,
        spanGaps: false,
      })
    })

    return {
      labels: buckets.map((bucket) => bucket.label),
      datasets,
    }
  }

  const historyChartData = computed(() =>
    buildComparisonChartData(
      historyBuckets.value,
      historyTrendResults.value,
      historyBandVisibility.value,
    ),
  )

  const seasonalChartData = computed(() =>
    buildComparisonChartData(
      seasonalBuckets.value,
      seasonalTrendResults.value,
      seasonalBandVisibility.value,
    ),
  )

  const chartData = computed(() => {
    const panel = cssVar('--app-surface-panel', '#ffffff')
    const accent = cssVar('--app-accent', '#7c3aed')
    const success = cssVar('--app-success', '#16a34a')
    const warning = cssVar('--app-warning', '#f59e0b')
    const danger = cssVar('--app-danger', '#ef4444')

    return {
      labels: chartLabels.value,
      datasets: [
        {
          label: 'Giá trung bình',
          data: deliveryMonthBuckets.value.map((bucket) => bucket.avgPrice),
          borderColor: accent,
          backgroundColor: `${accent}24`,
          pointBackgroundColor: accent,
          pointBorderColor: panel,
          pointRadius: 4,
          tension: 0.28,
          fill: true,
        },
        {
          label: 'Giá thấp nhất',
          data: deliveryMonthBuckets.value.map((bucket) => bucket.minPrice),
          borderColor: success,
          backgroundColor: 'transparent',
          pointBackgroundColor: success,
          pointBorderColor: panel,
          pointRadius: 3,
          borderDash: [6, 4],
          tension: 0.2,
        },
        {
          label: 'Giá cao nhất',
          data: deliveryMonthBuckets.value.map((bucket) => bucket.maxPrice),
          borderColor: warning,
          backgroundColor: 'transparent',
          pointBackgroundColor: warning,
          pointBorderColor: panel,
          pointRadius: 3,
          borderDash: [6, 4],
          tension: 0.2,
        },
        {
          label: 'Đã chốt mua',
          data: deliveryMonthBuckets.value.map((bucket) => bucket.purchasedPrice),
          borderColor: danger,
          backgroundColor: danger,
          pointBackgroundColor: danger,
          pointBorderColor: panel,
          pointRadius: 7,
          pointHoverRadius: 9,
          showLine: false,
        },
      ],
    }
  })

  const chartOptions = computed(() => {
    const grid =
      themeStore.mode === 'dark'
        ? cssVar('--app-border-strong', '#334155')
        : cssVar('--app-border-soft', '#e2e8f0')
    const textColor = cssVar('--app-text-secondary', '#64748b')
    const roleColors: Record<string, string> = {
      'Giá thấp nhất': cssVar('--app-success', '#16a34a'),
      'Giá cao nhất': cssVar('--app-warning', '#f59e0b'),
      'Gần giá trung bình': cssVar('--app-accent', '#7c3aed'),
    }
    const neutralColor = cssVar('--app-text-muted', '#94a3b8')
    // "Giá CNF": bucket đã tính sẵn theo giá gốc USD (xem `deliveryMonthBuckets`),
    // ở đây chỉ cần đổi formatter hiển thị + cách chọn giá đại diện cho từng
    // báo giá mẫu trong tooltip (`getPrice`) sang cùng field USD đó.
    const formatPrice = showCnfOnly.value ? formatUsdPerMt : formatMoney
    const getPrice = showCnfOnly.value
      ? (point: QuotifyPriceTrendPoint) => point.priceOriginal
      : (point: QuotifyPriceTrendPoint) => point.convertedPriceVndPerKg

    return {
      maintainAspectRatio: false,
      responsive: true,
      interaction: {
        intersect: false,
        mode: 'index',
      },
      onClick(_event: unknown, elements: { index: number }[]) {
        const bucket = deliveryMonthBuckets.value[elements[0]?.index ?? -1]
        const fixedDeliveryMonth = toDateInputValue(deliveryMonth.value)
        if (!bucket || !fixedDeliveryMonth) {
          return
        }
        const query: Record<string, string> = {
          deliveryMonth: fixedDeliveryMonth,
          receivedDateStart: bucket.receivedMonth,
          receivedDateEnd: getMonthEnd(bucket.receivedMonth),
        }
        if (selectedMaterialId.value) {
          query.materialId = selectedMaterialId.value
        }
        router.push({ path: '/quotes', query })
      },
      plugins: {
        legend: {
          labels: {
            color: textColor,
            boxWidth: 12,
            boxHeight: 12,
          },
        },
        tooltip: {
          enabled: false,
          callbacks: {
            label(context: { dataIndex: number; dataset: { label?: string } }) {
              const prefix = context.dataset.label ?? 'Giá'
              const bucket = deliveryMonthBuckets.value[context.dataIndex]
              if (!bucket) {
                return prefix
              }

              if (prefix === 'Đã chốt mua') {
                return bucket.purchasedPrice === null
                  ? ''
                  : `${prefix}: ${formatPrice(bucket.purchasedPrice)}`
              }

              const value =
                prefix === 'Giá thấp nhất'
                  ? bucket.minPrice
                  : prefix === 'Giá cao nhất'
                    ? bucket.maxPrice
                    : bucket.avgPrice
              return `${prefix}: ${formatPrice(value)}`
            },
          },
          // Tooltip mặc định của Chart.js vẽ trên canvas, mỗi dòng chỉ có 1
          // màu chữ — không thể tô màu ô vuông khớp màu đường trên chart cho
          // từng báo giá tiêu biểu. Dùng "external" tooltip (render bằng
          // HTML/CSS thật) để mỗi dòng có ô màu khớp đúng màu series tương
          // ứng (xanh = thấp nhất, cam = cao nhất, tím = gần trung bình) —
          // theo phản hồi người dùng ngày 12/08/2026.
          external(context: {
            chart: { canvas: HTMLCanvasElement }
            tooltip: {
              opacity: number
              title?: string[]
              body: { lines: string[] }[]
              labelColors: { backgroundColor: string; borderColor: string }[]
              dataPoints: { dataIndex: number }[]
              caretX: number
              caretY: number
            }
          }) {
            const { chart, tooltip } = context
            const tooltipEl = getOrCreateChartTooltipElement(chart.canvas)

            if (tooltip.opacity === 0) {
              tooltipEl.style.opacity = '0'
              return
            }

            tooltipEl.replaceChildren()

            const titleEl = document.createElement('div')
            titleEl.className = 'quotify-chart-tooltip__title'
            titleEl.textContent = tooltip.title?.[0] ?? ''
            tooltipEl.appendChild(titleEl)

            tooltip.body.forEach((bodyItem, index) => {
              const line = bodyItem.lines[0]
              if (!line) {
                return
              }
              const colors = tooltip.labelColors[index]
              tooltipEl.appendChild(
                buildTooltipRowElement(line, colors?.backgroundColor ?? neutralColor),
              )
            })

            const bucket = deliveryMonthBuckets.value[tooltip.dataPoints[0]?.dataIndex ?? -1]
            if (bucket) {
              const countEl = document.createElement('div')
              countEl.className = 'quotify-chart-tooltip__count'
              countEl.textContent = `${bucket.pointCount} báo giá nhận trong tháng ${bucket.label}`
              tooltipEl.appendChild(countEl)

              const sample = pickRepresentativeTooltipPoints(bucket.points, bucket.avgPrice, getPrice)
              for (const entry of sample) {
                const swatchColor = entry.role ? roleColors[entry.role] ?? neutralColor : neutralColor
                tooltipEl.appendChild(
                  buildTooltipRowElement(
                    buildTooltipLabel(entry.point, getPrice, formatPrice),
                    swatchColor,
                  ),
                )
              }

              const remaining = bucket.pointCount - sample.length
              if (remaining > 0) {
                const moreEl = document.createElement('div')
                moreEl.className = 'quotify-chart-tooltip__more'
                moreEl.textContent = `... và ${remaining} báo giá khác`
                tooltipEl.appendChild(moreEl)
              }

              const hintEl = document.createElement('div')
              hintEl.className = 'quotify-chart-tooltip__hint'
              hintEl.textContent = 'Nhấp để xem tất cả trong Bảng báo giá'
              tooltipEl.appendChild(hintEl)
            }

            // Đo kích thước tooltip SAU khi đã đổ nội dung, rồi kẹp vị trí
            // trong phạm vi canvas — nếu chỉ căn giữa theo caretX (translateX
            // -50%) như trước, tooltip ở gần 2 đầu chart sẽ bị lồi ra ngoài
            // và bị viewport cắt mất nội dung (ảnh báo lỗi ngày 12/08/2026).
            const { offsetLeft, offsetTop, offsetWidth: canvasWidth } = chart.canvas
            tooltipEl.style.opacity = '1'
            tooltipEl.style.left = '0px'
            tooltipEl.style.top = '0px'
            const tooltipWidth = tooltipEl.offsetWidth
            const tooltipHeight = tooltipEl.offsetHeight
            const idealLeft = offsetLeft + tooltip.caretX - tooltipWidth / 2
            const minLeft = offsetLeft
            const maxLeft = offsetLeft + canvasWidth - tooltipWidth
            const clampedLeft = Math.max(minLeft, Math.min(idealLeft, maxLeft))
            tooltipEl.style.left = `${clampedLeft}px`
            tooltipEl.style.top = `${offsetTop + tooltip.caretY - tooltipHeight - 12}px`
          },
        },
      },
      scales: {
        x: {
          ticks: {
            color: textColor,
            maxRotation: 0,
          },
          grid: {
            color: grid,
          },
        },
        y: {
          ticks: {
            color: textColor,
          },
          grid: {
            color: grid,
          },
        },
      },
    }
  })

  // Dùng chung cho cả 2 chart — chỉ khác nhau ở query điều hướng khi click
  // vào 1 điểm (chart theo kỳ hàng về vs chart theo ngày báo giá của 1 kỳ
  // hàng về cố định), phần tooltip/legend/scale giữ nguyên.
  function buildComparisonChartOptions(
    buckets: MaterialComparisonBucket[],
    trendResults: MaterialTrendResult[],
    buildNavigationQuery: (
      bucket: MaterialComparisonBucket,
      result: MaterialTrendResult,
    ) => Record<string, string>,
    // Chart mùa vụ (series = năm) cần hiện thêm tháng lịch thực tế bên cạnh
    // tên series trong tooltip (ví dụ "2026 (07/2026)") vì trục X là offset
    // trừu tượng — 2 chart so sánh cũ giữ nguyên hành vi cũ (mặc định chỉ
    // hiện materialName) nên không cần đổi gì ở lời gọi của chúng.
    formatSeriesRowLabel: (
      entry: MaterialComparisonSeriesPoint,
      bucket: MaterialComparisonBucket,
    ) => string = (entry) => entry.materialName,
    // "Giá CNF": dòng tóm tắt TB/Thấp/Cao trong tooltip đổi sang giá gốc
    // USD/MT — 2 chart chưa có CNF (chart so sánh theo kỳ hàng về) giữ
    // nguyên mặc định VNĐ/KG nên không cần đổi gì ở lời gọi của chúng.
    formatPriceTriplet: (entry: MaterialComparisonSeriesPoint) => string = (entry) =>
      formatComparisonPriceTriplet(entry, false),
  ) {
    const grid =
      themeStore.mode === 'dark'
        ? cssVar('--app-border-strong', '#334155')
        : cssVar('--app-border-soft', '#e2e8f0')
    const textColor = cssVar('--app-text-secondary', '#64748b')

    return {
      maintainAspectRatio: false,
      responsive: true,
      interaction: {
        intersect: false,
        mode: 'index',
      },
      onClick(_event: unknown, elements: { index: number; datasetIndex: number }[]) {
        const element = elements[0]
        const bucket = buckets[element?.index ?? -1]
        const result = trendResults[element?.datasetIndex ?? -1]
        if (!bucket || !result) {
          return
        }
        router.push({
          path: '/quotes',
          query: buildNavigationQuery(bucket, result),
        })
      },
      plugins: {
        legend: {
          labels: {
            color: textColor,
            boxWidth: 12,
            boxHeight: 12,
            // Dataset dải giá thấp-cao (`(cao nhất)`/`(thấp nhất)`) chỉ là
            // helper để tô vùng giữa 2 đường ẩn, không phải series riêng có
            // ý nghĩa để bật/tắt qua legend — ẩn khỏi legend cho đỡ rối.
            filter: (legendItem: { text?: string }) =>
              !legendItem.text?.endsWith('nhất)'),
          },
        },
        tooltip: {
          enabled: false,
          external(context: {
            chart: { canvas: HTMLCanvasElement }
            tooltip: {
              opacity: number
              title?: string[]
              dataPoints: { dataIndex: number }[]
              caretX: number
              caretY: number
            }
          }) {
            const { chart, tooltip } = context
            const tooltipEl = getOrCreateChartTooltipElement(chart.canvas)

            if (tooltip.opacity === 0) {
              tooltipEl.style.opacity = '0'
              return
            }

            tooltipEl.replaceChildren()

            const bucket = buckets[tooltip.dataPoints[0]?.dataIndex ?? -1]
            if (!bucket) {
              tooltipEl.style.opacity = '0'
              return
            }

            const titleEl = document.createElement('div')
            titleEl.className = 'quotify-chart-tooltip__title'
            titleEl.textContent = tooltip.title?.[0] ?? bucket.label
            tooltipEl.appendChild(titleEl)

            bucket.series.forEach((entry, index) => {
              const color =
                MATERIAL_COMPARISON_COLORS[index % MATERIAL_COMPARISON_COLORS.length]
              const priceLabel = formatPriceTriplet(entry)
              tooltipEl.appendChild(
                buildTooltipRowElement(`${formatSeriesRowLabel(entry, bucket)}: ${priceLabel}`, color),
              )
            })

            if (bucket.differenceLines.length > 0) {
              const spacerEl = document.createElement('div')
              spacerEl.className = 'quotify-chart-tooltip__count'
              spacerEl.textContent = bucket.differenceLines[0]
              tooltipEl.appendChild(spacerEl)
              for (const line of bucket.differenceLines.slice(1)) {
                const lineEl = document.createElement('div')
                lineEl.className = 'quotify-chart-tooltip__count'
                lineEl.textContent = line
                tooltipEl.appendChild(lineEl)
              }
            }

            const hintEl = document.createElement('div')
            hintEl.className = 'quotify-chart-tooltip__hint'
            hintEl.textContent = 'Nhấp vào 1 đường để xem báo giá tương ứng trong Bảng báo giá'
            tooltipEl.appendChild(hintEl)

            const { offsetLeft, offsetTop, offsetWidth: canvasWidth } = chart.canvas
            tooltipEl.style.opacity = '1'
            tooltipEl.style.left = '0px'
            tooltipEl.style.top = '0px'
            const tooltipWidth = tooltipEl.offsetWidth
            const tooltipHeight = tooltipEl.offsetHeight
            const idealLeft = offsetLeft + tooltip.caretX - tooltipWidth / 2
            const minLeft = offsetLeft
            const maxLeft = offsetLeft + canvasWidth - tooltipWidth
            const clampedLeft = Math.max(minLeft, Math.min(idealLeft, maxLeft))
            tooltipEl.style.left = `${clampedLeft}px`
            tooltipEl.style.top = `${offsetTop + tooltip.caretY - tooltipHeight - 12}px`
          },
        },
      },
      scales: {
        x: {
          ticks: {
            color: textColor,
            maxRotation: 0,
          },
          grid: {
            color: grid,
          },
        },
        y: {
          ticks: {
            color: textColor,
          },
          grid: {
            color: grid,
          },
        },
      },
    }
  }

  const historyChartOptions = computed(() => {
    const fixedDeliveryMonth = toDateInputValue(historyDeliveryMonth.value) ?? ''
    return buildComparisonChartOptions(
      historyBuckets.value,
      historyTrendResults.value,
      (bucket, result) => ({
        materialId: result.materialId,
        deliveryMonth: fixedDeliveryMonth,
        receivedDateStart: bucket.groupKey,
        receivedDateEnd: getThirdPeriodEnd(bucket.groupKey),
      }),
      undefined,
      (entry) => formatComparisonPriceTriplet(entry, historyShowCnfOnly.value),
    )
  })

  const seasonalChartOptions = computed(() => {
    // `result.materialId` chứa năm (chuỗi, xem loadSeasonalComparison) —
    // materialId THẬT dùng cho điều hướng phải lấy từ ref riêng, không phải
    // từ result (khác quy ước 2 chart trước vì series ở đây là NĂM chứ
    // không phải mặt hàng).
    const fixedMaterialId = seasonalMaterialId.value ?? ''
    const paddedMonth = String(seasonalMonth.value ?? 1).padStart(2, '0')

    const deliveryMonthForYear = (year: string) => `${year}-${paddedMonth}-01`
    // `bucket.groupKey` giờ là khóa gộp (tháng*3 + kỳ, xem
    // computeThirdsBeforeDelivery) — phải tách lại thành tháng thực tế + kỳ
    // trong tháng đó để suy ra đúng khoảng ngày nhận báo giá ~10 ngày (thay
    // vì cả tháng) cho click-through và nhãn tooltip.
    const resolveBucketDateInfo = (year: string, bucket: MaterialComparisonBucket) => {
      const { monthOffset, third } = decomposeThirdOffset(Number(bucket.groupKey))
      const actualMonth = addMonthsToMonthStart(deliveryMonthForYear(year), monthOffset)
      return { actualMonth, third, range: getThirdOfMonthDateRange(actualMonth, third) }
    }

    return buildComparisonChartOptions(
      seasonalBuckets.value,
      seasonalTrendResults.value,
      (bucket, result) => {
        const year = result.materialId
        const { range } = resolveBucketDateInfo(year, bucket)
        return {
          materialId: fixedMaterialId,
          deliveryMonth: deliveryMonthForYear(year),
          receivedDateStart: range.start,
          receivedDateEnd: range.end,
        }
      },
      (entry, bucket) => {
        const { actualMonth, third } = resolveBucketDateInfo(entry.materialId, bucket)
        return `${entry.materialName} (${formatMonthLabel(actualMonth)}, kỳ ${third + 1})`
      },
      (entry) => formatComparisonPriceTriplet(entry, seasonalShowCnfOnly.value),
    )
  })

  const weeklyEntryChartData = computed(() => {
    const accent = cssVar('--app-accent', '#7c3aed')
    const warning = cssVar('--app-warning', '#f59e0b')
    const border = cssVar('--app-border-strong', '#334155')

    return {
      labels: weeklyUserActivities.value.map((activity) => activity.userLabel),
      datasets: [
        {
          label: 'Số phiếu báo giá',
          data: weeklyUserActivities.value.map((activity) => activity.quoteCount),
          backgroundColor: weeklyUserActivities.value.map((activity) =>
            activity.hasWarning ? warning : accent,
          ),
          borderColor: weeklyUserActivities.value.map((activity) =>
            activity.hasWarning ? warning : border,
          ),
          borderWidth: 1,
          borderRadius: 6,
        },
      ],
    }
  })

  const weeklyEntryChartOptions = computed(() => {
    const grid =
      themeStore.mode === 'dark'
        ? cssVar('--app-border-strong', '#334155')
        : cssVar('--app-border-soft', '#e2e8f0')
    const textColor = cssVar('--app-text-secondary', '#64748b')

    return {
      indexAxis: 'y',
      maintainAspectRatio: false,
      responsive: true,
      plugins: {
        legend: {
          display: false,
        },
        tooltip: {
          callbacks: {
            label(context: { dataIndex: number }) {
              const row = weeklyUserActivities.value[context.dataIndex]
              if (!row) {
                return ''
              }

              return row.hasWarning
                ? 'Chưa nhập báo giá trong tuần'
                : `${formatInteger(row.quoteCount)} phiếu báo giá`
            },
          },
        },
      },
      scales: {
        x: {
          beginAtZero: true,
          ticks: {
            color: textColor,
            precision: 0,
          },
          grid: {
            color: grid,
          },
        },
        y: {
          ticks: {
            color: textColor,
          },
          grid: {
            display: false,
          },
        },
      },
    }
  })

  async function loadLookups() {
    isLoadingLookups.value = true
    try {
      materials.value = await listMaterialsLookup(authStore.accessToken)
      if (!selectedMaterialId.value) {
        selectedMaterialId.value = findDefaultMaterialId(materials.value)
      }
    } catch {
      materials.value = []
    } finally {
      isLoadingLookups.value = false
    }
  }

  async function loadDashboard() {
    isLoading.value = true
    errorMessage.value = null
    try {
      const [entryKpiResponse, priceTrendResponse] = await Promise.all([
        getQuotifyEntryKpis(queryParams.value, authStore.accessToken),
        getQuotifyPriceTrends(queryParams.value, authStore.accessToken),
      ])
      entryKpis.value = entryKpiResponse
      priceTrends.value = priceTrendResponse
    } catch {
      errorMessage.value = 'Không thể tải dữ liệu dashboard phân tích giá.'
    } finally {
      isLoading.value = false
    }
  }

  async function loadWeeklyEntryActivity() {
    isLoadingWeeklyEntry.value = true
    errorMessage.value = null
    try {
      const response = await getQuotifyWeeklyEntryActivity(
        weeklyEntryQueryParams.value,
        authStore.accessToken,
      )
      weeklyEntryActivity.value = response
      if (!selectedWeeklyUserId.value) {
        weeklyUserOptions.value = response.userActivities.map((activity) => ({
          label: activity.userLabel,
          value: activity.userId,
        }))
      }
    } catch {
      errorMessage.value = 'Không thể tải dữ liệu nhập báo giá theo tuần.'
    } finally {
      isLoadingWeeklyEntry.value = false
    }
  }

  async function bootstrap() {
    await loadLookups()
    await Promise.all([loadDashboard(), loadWeeklyEntryActivity()])
  }

  async function applyFilters() {
    await loadDashboard()
  }

  async function resetFilters() {
    selectedMaterialId.value = findDefaultMaterialId(materials.value)
    deliveryMonth.value = getDefaultDeliveryMonth()
    receivedDateStart.value = null
    receivedDateEnd.value = null
    showCnfOnly.value = false
    await loadDashboard()
  }

  async function applyWeeklyEntryFilters() {
    await loadWeeklyEntryActivity()
  }

  async function resetWeeklyEntryFilters() {
    selectedWeek.value = getWeekStartDate(new Date())
    selectedWeeklyUserId.value = null
    await loadWeeklyEntryActivity()
  }

  function getWeeklyEntryRowClass(activity: QuotifyWeeklyEntryUserActivity) {
    return activity.hasWarning ? 'dashboard-page__weekly-row--warning' : ''
  }

  return {
    entryKpis,
    priceTrends,
    weeklyEntryActivity,
    materials,
    weeklyUserOptions,
    isLoading,
    isLoadingWeeklyEntry,
    isLoadingLookups,
    errorMessage,
    selectedMaterialId,
    deliveryMonth,
    receivedDateStart,
    receivedDateEnd,
    showCnfOnly,
    selectedWeek,
    selectedWeeklyUserId,
    historyDeliveryMonth,
    historyMaterialIds,
    historyBuckets,
    historyTrendResults,
    historyBandVisibility,
    historyShowCnfOnly,
    historyChartData,
    historyChartOptions,
    loadPriceHistory,
    seasonalMaterialId,
    seasonalMonth,
    seasonalYears,
    seasonalAvailableYears,
    seasonalBuckets,
    seasonalTrendResults,
    seasonalBandVisibility,
    seasonalShowCnfOnly,
    seasonalChartData,
    seasonalChartOptions,
    loadSeasonalComparison,
    userKpis,
    weeklyUserActivities,
    weeklyWarningUsers,
    weeklyEntryMetricCards,
    weeklyEntryPeriodLabel,
    trendPoints,
    deliveryMonthBuckets,
    hasTrendData,
    hasWeeklyEntryData,
    chartData,
    chartOptions,
    weeklyEntryChartData,
    weeklyEntryChartOptions,
    bootstrap,
    loadDashboard,
    loadWeeklyEntryActivity,
    applyFilters,
    resetFilters,
    applyWeeklyEntryFilters,
    resetWeeklyEntryFilters,
    getWeeklyEntryRowClass,
    formatDateTimeLabel,
  }
}
