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

/** 1 điểm/ngày trên chart "Giá theo kỳ hàng về" — báo giá THẤP NHẤT nhận
 * trong ngày đó (xem `buildDailyMinPoints`). */
export interface DailyMinPricePoint {
  date: string
  price: number
  point: QuotifyPriceTrendPoint
}

export type PeriodRangeKey = '1w' | '1m' | '3m' | '6m' | '1y'

export interface PeriodRangeOption {
  label: string
  value: PeriodRangeKey
}

const PERIOD_RANGE_OPTIONS: PeriodRangeOption[] = [
  { label: '1 tuần', value: '1w' },
  { label: '1 tháng', value: '1m' },
  { label: '3 tháng', value: '3m' },
  { label: '6 tháng', value: '6m' },
  { label: '1 năm', value: '1y' },
]

const DEFAULT_PERIOD_RANGE_KEY: PeriodRangeKey = '6m'

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

/** Khoảng ngày nhận báo giá [start, end] cho 1 nút bấm nhanh trên chart "Giá
 * theo kỳ hàng về" — end luôn là HÔM NAY, start lùi lại theo khoảng đã chọn.
 * Dùng các hàm `setDate`/`setMonth`/`setFullYear` của `Date` (không phải
 * cộng/trừ số mili-giây cố định) để tự xử lý đúng số ngày/tháng thiếu và năm
 * nhuận như lịch thật. */
function computePeriodRangeDates(key: PeriodRangeKey): { start: Date; end: Date } {
  const end = new Date()
  end.setHours(0, 0, 0, 0)
  const start = new Date(end)
  if (key === '1w') {
    start.setDate(start.getDate() - 7)
  } else if (key === '1m') {
    start.setMonth(start.getMonth() - 1)
  } else if (key === '3m') {
    start.setMonth(start.getMonth() - 3)
  } else if (key === '6m') {
    start.setMonth(start.getMonth() - 6)
  } else {
    start.setFullYear(start.getFullYear() - 1)
  }
  return { start, end }
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
 * ghi thêm "(kỳ N)" vào label khiến tick nào cũng hiện thông tin kỳ. Vì 3
 * bucket/tháng dùng CHUNG 1 label như nhau, việc chọn ĐÚNG 1 bucket/tháng để
 * thực sự hiện tick không được giao cho Chart.js tự bỏ bớt (autoSkip) nữa —
 * autoSkip tính theo pixel nên chỉ cần đổi bề rộng khả dụng của chart (thêm
 * `layout.padding`, resize cửa sổ...) là có thể lệch, khiến có tháng hiện 2
 * tick trùng label (lỗi thật gặp ngày 20/08/2026). `seasonalChartOptions`
 * giờ tự tính trước, DETERMINISTIC, bucket nào (luôn là kỳ nhỏ nhất) được
 * hiện label qua tham số `getTickLabel` của `buildComparisonChartOptions`.
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

/** Mỗi ngày nhận báo giá chỉ lấy 1 điểm trên chart "Giá theo kỳ hàng về" —
 * báo giá THẤP NHẤT trong ngày đó, rồi nối các điểm theo ngày thành 1 đường
 * duy nhất (theo yêu cầu người dùng ngày 20/08/2026: "tôi chỉ quan tâm tới
 * MIN"). */
function buildDailyMinPoints(
  points: QuotifyPriceTrendPoint[],
  // Mặc định lấy giá quy đổi VNĐ/KG; chế độ "Giá CNF" truyền vào
  // `(point) => point.priceOriginal` để dùng giá gốc USD thay thế.
  getPrice: (point: QuotifyPriceTrendPoint) => number = (point) => point.convertedPriceVndPerKg,
): DailyMinPricePoint[] {
  const byDate = new Map<string, QuotifyPriceTrendPoint>()
  for (const point of points) {
    const day = point.receivedDate.slice(0, 10)
    const current = byDate.get(day)
    if (!current || getPrice(point) < getPrice(current)) {
      byDate.set(day, point)
    }
  }

  return Array.from(byDate.entries())
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([date, point]) => ({ date, price: getPrice(point), point }))
}

interface CrosshairChartElement {
  x: number
  y: number
}

interface CrosshairActiveElement {
  element: CrosshairChartElement
  index: number
}

interface CrosshairChartArea {
  top: number
  bottom: number
  left: number
  right: number
}

interface CrosshairYScale {
  getValueForPixel(pixel: number): number | undefined
}

interface CrosshairChart {
  ctx: CanvasRenderingContext2D
  chartArea: CrosshairChartArea
  scales: { y: CrosshairYScale }
  getActiveElements(): CrosshairActiveElement[]
}

interface CrosshairEventArgs {
  event: { type: string; x: number | null; y: number | null }
}

/** Vẽ 1 ô nhãn bo góc (nền đặc + chữ trắng) canh giữa tại `(centerX,
 * centerY)` — dùng cho nhãn giá trị trục Y của crosshair. `roundRect` không
 * có trên mọi trình duyệt cũ nên fallback về `rect` vuông góc nếu thiếu. */
function drawCrosshairLabel(
  ctx: CanvasRenderingContext2D,
  text: string,
  centerX: number,
  centerY: number,
  backgroundColor: string,
  textColor: string,
) {
  ctx.save()
  ctx.font = '600 11px sans-serif'
  const paddingX = 6
  const boxHeight = 18
  const boxWidth = ctx.measureText(text).width + paddingX * 2
  const x = centerX - boxWidth / 2
  const y = centerY - boxHeight / 2

  ctx.fillStyle = backgroundColor
  ctx.beginPath()
  if (typeof ctx.roundRect === 'function') {
    ctx.roundRect(x, y, boxWidth, boxHeight, 3)
  } else {
    ctx.rect(x, y, boxWidth, boxHeight)
  }
  ctx.fill()

  ctx.fillStyle = textColor
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(text, centerX, centerY + 1)
  ctx.restore()
}

/** Plugin Chart.js tự vẽ "đường gióng" (crosshair) khi trỏ chuột vào các
 * chart line của dashboard (dùng chung cho cả 3 chart: "Giá theo kỳ hàng
 * về", "Diễn biến giá theo thời gian chào giá", "So sánh giá theo mùa vụ"),
 * mô phỏng các chart giá chứng khoán — theo yêu cầu người dùng ngày
 * 20/08/2026. Đường gióng trục X chỉ để định vị (không hiện giá trị ngày —
 * thông tin chi tiết đã có trong box tooltip riêng của từng chart, xem
 * `tooltip.external`); đường gióng trục Y bám theo ĐÚNG tọa độ con trỏ chuột
 * (không snap về giá của điểm gần nhất) và hiện giá trị thực tại tọa độ đó —
 * theo phản hồi người dùng ngày 20/08/2026 ("hiển thị giá trị thực tế ở tọa
 * độ chuột"). Vị trí X vẫn snap về điểm dữ liệu gần nhất (qua
 * `getActiveElements()`, đồng bộ với `interaction.mode: 'index'`), còn vị
 * trí Y phải tự theo dõi qua `afterEvent` vì Chart.js không có sẵn API lấy
 * tọa độ chuột thô ở `afterDraw`. */
function buildCrosshairPlugin(
  formatPrice: (value: number | null) => string,
  lineColor: string,
  labelBackground: string,
  labelTextColor: string,
) {
  let hoverY: number | null = null

  return {
    id: 'quotifyChartCrosshair',
    afterEvent(chart: CrosshairChart, args: CrosshairEventArgs) {
      const { event } = args
      if (event.type === 'mouseout' || event.y === null) {
        hoverY = null
        return
      }
      if (event.y >= chart.chartArea.top && event.y <= chart.chartArea.bottom) {
        hoverY = event.y
      } else {
        hoverY = null
      }
    },
    afterDraw(chart: CrosshairChart) {
      const active = chart.getActiveElements()
      if (active.length === 0 || hoverY === null) {
        return
      }

      const { ctx, chartArea } = chart
      const { x } = active[0].element

      ctx.save()
      ctx.setLineDash([4, 4])
      ctx.strokeStyle = lineColor
      ctx.lineWidth = 1

      ctx.beginPath()
      ctx.moveTo(x, chartArea.top)
      ctx.lineTo(x, chartArea.bottom)
      ctx.stroke()

      ctx.beginPath()
      ctx.moveTo(chartArea.left, hoverY)
      ctx.lineTo(chartArea.right, hoverY)
      ctx.stroke()
      ctx.restore()

      const valueAtCursor = chart.scales.y.getValueForPixel(hoverY)
      if (valueAtCursor !== undefined) {
        drawCrosshairLabel(
          ctx,
          formatPrice(valueAtCursor),
          chartArea.right + 34,
          hoverY,
          labelBackground,
          labelTextColor,
        )
      }
    },
  }
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

/** 1 dòng "X cao hơn Y" trong box hover — dạng CÓ CẤU TRÚC (không phải 1
 * chuỗi đã ghép sẵn) để template tô đậm riêng phần giá trị chênh lệch và
 * phần trăm chênh lệch (`DashboardPage.vue`), theo phản hồi người dùng ngày
 * 20/08/2026. */
export interface ComparisonDifferenceLine {
  label: string
  diffValue: string
  percent: string
}

interface MaterialComparisonBucket {
  // Khóa nhóm dùng chung cho cả 2 chart: chart "theo kỳ hàng về" nhóm theo
  // deliveryMonth, chart "diễn biến theo ngày báo giá" nhóm theo tháng của
  // receivedDate — tên trung tính để 1 hàm build dùng được cho cả hai.
  groupKey: string
  label: string
  series: MaterialComparisonSeriesPoint[]
  differenceLines: ComparisonDifferenceLine[]
}

export interface ComparisonHoverInfoRow {
  label: string
  color: string
  // null khi mặt hàng/năm này chưa có báo giá nào trong bucket đang hover.
  metrics: ComparisonHoverMetrics | null
}

/** Nội dung hiển thị khi hover vào 1 điểm trên chart "Diễn biến giá theo
 * thời gian chào giá"/"So sánh giá theo mùa vụ" — hiện trong 1 khối nằm
 * trong luồng tài liệu (xem `DashboardPage.vue`), không phải tooltip
 * absolute-positioned, để không bao giờ đè lên chart hay bộ lọc phía trên
 * dù nội dung dài ngắn thế nào (số dòng phụ thuộc số mặt hàng/năm đang so
 * sánh). */
export interface ComparisonHoverInfo {
  title: string
  rows: ComparisonHoverInfoRow[]
  differenceLines: ComparisonDifferenceLine[]
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
): ComparisonDifferenceLine[] {
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
      return {
        label: `${entry.materialName} cao hơn ${cheapest.materialName}`,
        diffValue: `+${formatPrice(diff)}`,
        percent: `+${formatPercent(percent)}`,
      }
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

/** TB/Thấp/Cao của box thông tin hover trong 2 chart so sánh nhiều mặt
 * hàng/năm, dạng CÓ CẤU TRÚC (không phải 1 chuỗi đã ghép sẵn) — để template
 * tô đậm riêng giá TB, tô đậm + xanh riêng giá Thấp, tô đậm + đỏ riêng giá
 * Cao (`DashboardPage.vue`), theo yêu cầu người dùng ngày 20/08/2026.
 * Chuyển sang giá gốc USD/MT khi "Giá CNF" bật (giá trị trong `entry` đã
 * được tính đúng theo field USD nhờ `getPrice` truyền vào
 * `buildGroupedComparisonBuckets`, ở đây chỉ cần đổi cách hiển thị). */
export interface ComparisonHoverMetrics {
  avg: string
  min: string
  max: string
  unitLabel: string
  pointCount: number
}

function buildComparisonHoverMetrics(
  entry: MaterialComparisonSeriesPoint,
  onlyCnf: boolean,
): ComparisonHoverMetrics | null {
  if (entry.avgPrice === null || entry.minPrice === null || entry.maxPrice === null) {
    return null
  }
  const formatValue = onlyCnf ? (value: number) => `$${formatNumber(value)}` : formatNumber
  return {
    avg: formatValue(entry.avgPrice),
    min: formatValue(entry.minPrice),
    max: formatValue(entry.maxPrice),
    unitLabel: onlyCnf ? 'USD/MT' : 'VNĐ/KG',
    pointCount: entry.pointCount,
  }
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
  // Khoảng ngày nhận báo giá mặc định = 6 tháng gần nhất (xem
  // `computePeriodRangeDates`/`periodRangeKey`), theo yêu cầu người dùng
  // ngày 20/08/2026 ("Mặc định 6 tháng") — không còn để trống/không giới hạn
  // như trước.
  const defaultPeriodRange = computePeriodRangeDates(DEFAULT_PERIOD_RANGE_KEY)
  const periodRangeKey = ref<PeriodRangeKey>(DEFAULT_PERIOD_RANGE_KEY)
  const periodRangeOptions = PERIOD_RANGE_OPTIONS
  const receivedDateStart = ref<Date | null>(defaultPeriodRange.start)
  const receivedDateEnd = ref<Date | null>(defaultPeriodRange.end)
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
  // Nội dung box hiển thị khi hover — xem `ComparisonHoverInfo`/
  // `buildComparisonChartOptions`.
  const historyHoverInfo = ref<ComparisonHoverInfo | null>(null)

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
  const seasonalHoverInfo = ref<ComparisonHoverInfo | null>(null)

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

  const periodGetPrice = computed(() =>
    showCnfOnly.value
      ? (point: QuotifyPriceTrendPoint) => point.priceOriginal
      : (point: QuotifyPriceTrendPoint) => point.convertedPriceVndPerKg,
  )
  const periodFormatPrice = computed(() => (showCnfOnly.value ? formatUsdPerMt : formatMoney))

  const periodDailyPoints = computed(() =>
    buildDailyMinPoints(trendPoints.value, periodGetPrice.value),
  )

  // MAX/MIN/Trung bình hiển thị ở giữa-trên chart, tính trên chính chuỗi
  // giá MIN-theo-ngày đang vẽ (không phải trên toàn bộ báo giá thô) — khớp
  // với những gì trục Y thực sự đang thể hiện, theo yêu cầu người dùng ngày
  // 20/08/2026 ("MAX, MIN, Trung Bình trong toàn bộ khoảng thời gian đã lọc").
  const periodStats = computed(() => {
    const prices = periodDailyPoints.value.map((entry) => entry.price)
    if (prices.length === 0) {
      return { min: null, max: null, avg: null } as {
        min: number | null
        max: number | null
        avg: number | null
      }
    }
    return {
      min: Math.min(...prices),
      max: Math.max(...prices),
      avg: prices.reduce((total, current) => total + current, 0) / prices.length,
    }
  })

  const periodStatsFormatted = computed(() => ({
    min: periodFormatPrice.value(periodStats.value.min),
    max: periodFormatPrice.value(periodStats.value.max),
    avg: periodFormatPrice.value(periodStats.value.avg),
  }))

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

    return {
      labels: periodDailyPoints.value.map((entry) => entry.date),
      datasets: [
        {
          label: 'Giá thấp nhất trong ngày',
          data: periodDailyPoints.value.map((entry) => entry.price),
          borderColor: accent,
          backgroundColor: `${accent}24`,
          pointBackgroundColor: accent,
          pointBorderColor: panel,
          pointRadius: 2,
          pointHoverRadius: 5,
          tension: 0.2,
          fill: true,
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
    const accent = cssVar('--app-accent', '#7c3aed')
    const formatPrice = periodFormatPrice.value

    return {
      maintainAspectRatio: false,
      responsive: true,
      // Chừa lề phải cho ô nhãn giá trị trục Y của crosshair (xem
      // `buildCrosshairPlugin`), và lề trên đủ chỗ cho box ngày/giá (xem
      // `tooltip.external` bên dưới) — box này giờ LUÔN neo trong dải lề
      // trên, không nằm trong phần thân chart, để không bao giờ che đường
      // biểu đồ dù điểm hover ở vị trí nào, theo yêu cầu người dùng ngày
      // 20/08/2026 ("không được che vào chart dù nó ở bất kỳ vị trí nào").
      layout: {
        padding: { top: 64, right: 64 },
      },
      interaction: {
        intersect: false,
        mode: 'index',
      },
      onClick(_event: unknown, elements: { index: number }[]) {
        const entry = periodDailyPoints.value[elements[0]?.index ?? -1]
        const fixedDeliveryMonth = toDateInputValue(deliveryMonth.value)
        if (!entry || !fixedDeliveryMonth) {
          return
        }
        const query: Record<string, string> = {
          deliveryMonth: fixedDeliveryMonth,
          receivedDateStart: entry.date,
          receivedDateEnd: entry.date,
        }
        if (selectedMaterialId.value) {
          query.materialId = selectedMaterialId.value
        }
        router.push({ path: '/quotes', query })
      },
      plugins: {
        legend: {
          display: false,
        },
        tooltip: {
          enabled: false,
          // Box thông tin ngày chào giá + giá đã chào tại điểm đang hover —
          // đường gióng trục X chỉ cần định vị (không tự hiện giá trị ngày,
          // xem `buildCrosshairPlugin`), thông tin ngày/giá nằm hết ở đây,
          // theo yêu cầu người dùng ngày 20/08/2026.
          external(context: {
            chart: { canvas: HTMLCanvasElement }
            tooltip: {
              opacity: number
              dataPoints: { dataIndex: number }[]
              caretX: number
              caretY: number
            }
          }) {
            const { chart, tooltip } = context
            const tooltipEl = getOrCreateChartTooltipElement(chart.canvas)

            const entry = periodDailyPoints.value[tooltip.dataPoints[0]?.dataIndex ?? -1]
            if (tooltip.opacity === 0 || !entry) {
              tooltipEl.style.opacity = '0'
              return
            }

            tooltipEl.replaceChildren()

            const titleEl = document.createElement('div')
            titleEl.className = 'quotify-chart-tooltip__title'
            titleEl.textContent = formatDateLabel(entry.date)
            tooltipEl.appendChild(titleEl)

            tooltipEl.appendChild(
              buildTooltipRowElement(`Giá ${formatPrice(entry.price)}`, accent),
            )

            // Đo kích thước tooltip SAU khi đã đổ nội dung, rồi kẹp vị trí
            // theo chiều ngang trong phạm vi canvas — cùng cách làm với
            // tooltip của 2 chart so sánh (xem `buildComparisonChartOptions`).
            // Chiều dọc KHÔNG bám theo `caretY` như 2 chart kia — luôn neo cố
            // định trong dải lề trên đã chừa sẵn (`layout.padding.top`), để
            // box không bao giờ đè lên đường biểu đồ dù điểm hover ở đâu,
            // theo yêu cầu người dùng ngày 20/08/2026.
            const { offsetLeft, offsetTop, offsetWidth: canvasWidth } = chart.canvas
            tooltipEl.style.opacity = '1'
            tooltipEl.style.left = '0px'
            tooltipEl.style.top = '0px'
            const tooltipWidth = tooltipEl.offsetWidth
            const idealLeft = offsetLeft + tooltip.caretX - tooltipWidth / 2
            const minLeft = offsetLeft
            const maxLeft = offsetLeft + canvasWidth - tooltipWidth
            const clampedLeft = Math.max(minLeft, Math.min(idealLeft, maxLeft))
            tooltipEl.style.left = `${clampedLeft}px`
            tooltipEl.style.top = `${offsetTop + 6}px`
          },
        },
      },
      scales: {
        x: {
          ticks: {
            color: textColor,
            // Cho phép xiên tối đa 45° (thay vì ép nằm ngang) — nhãn ngày
            // dạng "dd/mm/yyyy" khá dài, nằm ngang dễ chồng lấp nhau khi có
            // nhiều điểm trên trục X (nhất là khoảng 6 tháng/1 năm); xiên
            // chéo giúp đọc rõ hơn, theo yêu cầu người dùng ngày 20/08/2026.
            maxRotation: 45,
            minRotation: 45,
            callback: (_value: unknown, index: number) => {
              const entry = periodDailyPoints.value[index]
              return entry ? formatDateLabel(entry.date) : ''
            },
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

  // Plugin Chart.js riêng cho crosshair (xem `buildCrosshairPlugin`) — tách
  // khỏi `chartOptions` vì phải truyền qua prop `plugins` riêng của
  // `<Chart>` (PrimeVue), không phải qua `options.plugins`.
  const chartPlugins = computed(() => {
    const panel = cssVar('--app-surface-panel', '#ffffff')
    const accent = cssVar('--app-accent', '#7c3aed')
    const crosshairLine = cssVar('--app-text-muted', '#94a3b8')

    return [buildCrosshairPlugin(periodFormatPrice.value, crosshairLine, accent, panel)]
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
    // "Giá CNF": TB/Thấp/Cao trong box hover đổi sang giá gốc USD/MT — 2
    // chart chưa có CNF (chart so sánh theo kỳ hàng về) giữ nguyên mặc định
    // VNĐ/KG nên không cần đổi gì ở lời gọi của chúng.
    buildMetrics: (
      entry: MaterialComparisonSeriesPoint,
    ) => ComparisonHoverMetrics | null = (entry) => buildComparisonHoverMetrics(entry, false),
    // Nội dung hover được ghi vào ref này thay vì vẽ trực tiếp 1 tooltip
    // absolute-positioned đè lên canvas — nội dung chart này (nhiều dòng
    // mặt hàng/năm + chênh lệch giá) dài ngắn thất thường, không có vị trí
    // "an toàn" nào trong/quanh canvas để đặt 1 box đè lên mà chắc chắn
    // không che mất phần khác (dữ liệu chart HOẶC bộ lọc phía trên) — xem
    // template `DashboardPage.vue`, nơi ref này được hiển thị trong 1 khối
    // NẰM TRONG LUỒNG TÀI LIỆU (không absolute), có chiều cao cố định +
    // cuộn riêng, nên không bao giờ đè lên bất cứ thứ gì, theo phản hồi
    // người dùng ngày 20/08/2026 ("box đang chèn vào các phần khác ở trên
    // chart").
    hoverInfo?: { value: ComparisonHoverInfo | null },
    // Nhãn trục X cho TỪNG bucket (theo index, khớp thứ tự `buckets`) — mặc
    // định `undefined` (dùng tick tự sinh từ `labels` như chart theo kỳ
    // hàng về, mỗi bucket 1 nhãn riêng biệt). Chart mùa vụ (series = năm)
    // cần override: 3 bucket liền nhau dùng CHUNG 1 label "T-N" (không hiện
    // kỳ trong tháng, xem `formatThirdOffsetLabel`) — trước đây dựa vào
    // Chart.js tự bỏ bớt tick (autoSkip) "may mắn" rơi đúng vào bước nhảy 3
    // để mỗi tháng chỉ hiện 1 tick, nhưng autoSkip tính theo PIXEL nên chỉ
    // cần đổi bề rộng khả dụng của chart (ví dụ thêm `layout.padding.right`
    // cho nhãn crosshair) là lệch mất sự "may mắn" đó, khiến có tháng hiện
    // 2 tick trùng label — lỗi thật gặp ngày 20/08/2026. Truyền hàm này vào
    // để CHỦ ĐỘNG chỉ định đúng 1 bucket/tháng được hiện label, không phụ
    // thuộc autoSkip nữa.
    getTickLabel?: (bucket: MaterialComparisonBucket, index: number) => string,
  ) {
    const grid =
      themeStore.mode === 'dark'
        ? cssVar('--app-border-strong', '#334155')
        : cssVar('--app-border-soft', '#e2e8f0')
    const textColor = cssVar('--app-text-secondary', '#64748b')

    return {
      maintainAspectRatio: false,
      responsive: true,
      // Chừa lề phải cho ô nhãn giá trị trục Y của crosshair (xem
      // `buildCrosshairPlugin`) — nếu không, ô nhãn bị vẽ lồi ra khỏi phần
      // thân chart khi hover gần rìa phải.
      layout: {
        padding: { right: 64 },
      },
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
            tooltip: {
              opacity: number
              title?: string[]
              dataPoints: { dataIndex: number }[]
            }
          }) {
            if (!hoverInfo) {
              return
            }

            const { tooltip } = context
            if (tooltip.opacity === 0) {
              hoverInfo.value = null
              return
            }

            const bucket = buckets[tooltip.dataPoints[0]?.dataIndex ?? -1]
            if (!bucket) {
              hoverInfo.value = null
              return
            }

            hoverInfo.value = {
              title: tooltip.title?.[0] ?? bucket.label,
              rows: bucket.series.map((entry, index) => ({
                label: formatSeriesRowLabel(entry, bucket),
                color: MATERIAL_COMPARISON_COLORS[index % MATERIAL_COMPARISON_COLORS.length],
                metrics: buildMetrics(entry),
              })),
              differenceLines: bucket.differenceLines,
            }
          },
        },
      },
      scales: {
        x: {
          ticks: {
            color: textColor,
            maxRotation: 0,
            // Khi có `getTickLabel`, tự tính đúng 1 nhãn/bucket cần hiện —
            // tắt autoSkip để Chart.js không tự ý bỏ bớt/chọn lại tick theo
            // pixel nữa (xem chú thích ở tham số `getTickLabel`).
            ...(getTickLabel
              ? {
                  autoSkip: false,
                  callback: (_value: unknown, index: number) => {
                    const bucket = buckets[index]
                    return bucket ? getTickLabel(bucket, index) : ''
                  },
                }
              : {}),
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
      (entry) => buildComparisonHoverMetrics(entry, historyShowCnfOnly.value),
      historyHoverInfo,
    )
  })

  // Plugin crosshair dùng chung (xem `buildCrosshairPlugin`) — tách khỏi
  // `historyChartOptions`/`seasonalChartOptions` vì phải truyền qua prop
  // `plugins` riêng của `<Chart>` (PrimeVue), không phải qua
  // `options.plugins`.
  const historyChartPlugins = computed(() => {
    const panel = cssVar('--app-surface-panel', '#ffffff')
    const accent = cssVar('--app-accent', '#7c3aed')
    const crosshairLine = cssVar('--app-text-muted', '#94a3b8')
    const formatPrice = historyShowCnfOnly.value ? formatUsdPerMt : formatMoney

    return [buildCrosshairPlugin(formatPrice, crosshairLine, accent, panel)]
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

    // Chỉ bucket ĐẦU TIÊN (kỳ nhỏ nhất) của mỗi tháng tương đối được gán
    // label — `seasonalBuckets` đã sắp đúng thứ tự tăng dần theo combinedOffset
    // (compareKeys số học, xem `loadSeasonalComparison`) nên các bucket cùng
    // tháng luôn liền kề nhau, chỉ cần so với tháng của bucket liền trước.
    // Tính SẴN thành mảng (không tính trong lúc Chart.js gọi callback) để
    // không phụ thuộc thứ tự/số lần Chart.js thực sự gọi tick callback.
    let previousMonthOffset: number | null = null
    const tickLabels = seasonalBuckets.value.map((bucket) => {
      const { monthOffset } = decomposeThirdOffset(Number(bucket.groupKey))
      if (monthOffset === previousMonthOffset) {
        return ''
      }
      previousMonthOffset = monthOffset
      return formatThirdOffsetLabel(bucket.groupKey)
    })

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
      (entry) => buildComparisonHoverMetrics(entry, seasonalShowCnfOnly.value),
      seasonalHoverInfo,
      (_bucket, index) => tickLabels[index] ?? '',
    )
  })

  const seasonalChartPlugins = computed(() => {
    const panel = cssVar('--app-surface-panel', '#ffffff')
    const accent = cssVar('--app-accent', '#7c3aed')
    const crosshairLine = cssVar('--app-text-muted', '#94a3b8')
    const formatPrice = seasonalShowCnfOnly.value ? formatUsdPerMt : formatMoney

    return [buildCrosshairPlugin(formatPrice, crosshairLine, accent, panel)]
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

  /** Nút bấm nhanh (1 tuần/1 tháng/3 tháng/6 tháng/1 năm) — ghi thẳng vào
   * `receivedDateStart`/`receivedDateEnd` (CÙNG 2 ref đã gắn sẵn cho 2
   * `DatePicker` "Từ ngày nhận"/"Đến ngày nhận") rồi tải lại, theo yêu cầu
   * người dùng ngày 20/08/2026 ("giữ nguyên các filter như hiện tại"). */
  async function applyPeriodRange(key: PeriodRangeKey) {
    periodRangeKey.value = key
    const { start, end } = computePeriodRangeDates(key)
    receivedDateStart.value = start
    receivedDateEnd.value = end
    await loadDashboard()
  }

  async function resetFilters() {
    selectedMaterialId.value = findDefaultMaterialId(materials.value)
    deliveryMonth.value = getDefaultDeliveryMonth()
    periodRangeKey.value = DEFAULT_PERIOD_RANGE_KEY
    const { start, end } = computePeriodRangeDates(DEFAULT_PERIOD_RANGE_KEY)
    receivedDateStart.value = start
    receivedDateEnd.value = end
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
    periodRangeKey,
    periodRangeOptions,
    applyPeriodRange,
    periodDailyPoints,
    periodStats,
    periodStatsFormatted,
    selectedWeek,
    selectedWeeklyUserId,
    historyDeliveryMonth,
    historyMaterialIds,
    historyBuckets,
    historyTrendResults,
    historyBandVisibility,
    historyShowCnfOnly,
    historyHoverInfo,
    historyChartData,
    historyChartOptions,
    historyChartPlugins,
    loadPriceHistory,
    seasonalMaterialId,
    seasonalMonth,
    seasonalYears,
    seasonalAvailableYears,
    seasonalBuckets,
    seasonalTrendResults,
    seasonalBandVisibility,
    seasonalShowCnfOnly,
    seasonalHoverInfo,
    seasonalChartData,
    seasonalChartOptions,
    seasonalChartPlugins,
    loadSeasonalComparison,
    userKpis,
    weeklyUserActivities,
    weeklyWarningUsers,
    weeklyEntryMetricCards,
    weeklyEntryPeriodLabel,
    trendPoints,
    hasTrendData,
    hasWeeklyEntryData,
    chartData,
    chartOptions,
    chartPlugins,
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
