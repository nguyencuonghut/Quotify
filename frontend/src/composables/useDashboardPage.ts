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
  QuotifyDashboardSupplierTypeFilter,
  QuotifyEntryKpis,
  QuotifyPriceSummary,
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

interface DashboardSupplierTypeOption {
  label: string
  value: QuotifyDashboardSupplierTypeFilter
}

interface DashboardUserOption {
  label: string
  value: string
}

interface DeliveryMonthBucket {
  deliveryMonth: string
  label: string
  minPrice: number
  maxPrice: number
  avgPrice: number
  pointCount: number
  purchasedPrice: number | null
  points: QuotifyPriceTrendPoint[]
}

const preferredMaterialCodes = ['CORN']
const preferredMaterialNames = ['ngô hạt', 'ngo hat', 'bắp hạt', 'bap hat']
const supplierTypeOptions: DashboardSupplierTypeOption[] = [
  { label: 'Nội địa', value: 'domestic' },
  { label: 'Quốc tế', value: 'international' },
]

const emptySummary: QuotifyPriceSummary = {
  minPrice: null,
  maxPrice: null,
  avgPrice: null,
  totalLines: 0,
  totalQuotes: 0,
  purchasedLines: 0,
}

function formatMoney(value: number | null): string {
  if (value === null || Number.isNaN(value)) {
    return 'Chưa có dữ liệu'
  }

  return `${new Intl.NumberFormat('en-US', {
    maximumFractionDigits: 2,
    minimumFractionDigits: 2,
  }).format(value)} VNĐ/KG`
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

function toDateInputValue(value: Date | null): string | null {
  if (!value) {
    return null
  }

  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
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

function buildTooltipLabel(point: QuotifyPriceTrendPoint): string {
  return [
    point.supplierLabel,
    formatSupplierType(point.supplierType),
    formatDateLabel(point.receivedDate),
    formatMonthLabel(point.deliveryMonth),
    formatMoney(point.convertedPriceVndPerKg),
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

  const byPriceAsc = [...points].sort(
    (left, right) => left.convertedPriceVndPerKg - right.convertedPriceVndPerKg,
  )
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
      Math.abs(left.convertedPriceVndPerKg - avgPrice) -
      Math.abs(right.convertedPriceVndPerKg - avgPrice),
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
): DeliveryMonthBucket[] {
  const bucketMap = new Map<string, QuotifyPriceTrendPoint[]>()
  for (const point of points) {
    bucketMap.set(point.deliveryMonth, [
      ...(bucketMap.get(point.deliveryMonth) ?? []),
      point,
    ])
  }

  return Array.from(bucketMap.entries())
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([deliveryMonthKey, bucketPoints]) => {
      const prices = bucketPoints.map((point) => point.convertedPriceVndPerKg)
      const purchasedPoint = bucketPoints.find((point) => point.purchased)

      return {
        deliveryMonth: deliveryMonthKey,
        label: formatMonthLabel(deliveryMonthKey),
        minPrice: Math.min(...prices),
        maxPrice: Math.max(...prices),
        avgPrice:
          prices.reduce((total, current) => total + current, 0) / prices.length,
        pointCount: bucketPoints.length,
        purchasedPrice: purchasedPoint?.convertedPriceVndPerKg ?? null,
        points: bucketPoints,
      }
    })
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
  const selectedSupplierType = ref<QuotifyDashboardSupplierTypeFilter | null>(null)
  const deliveryMonth = ref<Date | null>(null)
  const receivedDateStart = ref<Date | null>(null)
  const receivedDateEnd = ref<Date | null>(null)
  const selectedWeek = ref<Date | null>(getWeekStartDate(new Date()))
  const selectedWeeklyUserId = ref<string | null>(null)

  const queryParams = computed<QuotifyDashboardQuery>(() => ({
    materialId: selectedMaterialId.value,
    deliveryMonth: toDateInputValue(deliveryMonth.value),
    receivedDateStart: toDateInputValue(receivedDateStart.value),
    receivedDateEnd: toDateInputValue(receivedDateEnd.value),
    supplierType: selectedSupplierType.value,
  }))

  const weeklyEntryQueryParams = computed<QuotifyWeeklyEntryActivityQuery>(() => ({
    weekStart: selectedWeek.value
      ? toDateInputValue(getWeekStartDate(selectedWeek.value))
      : null,
    userId: selectedWeeklyUserId.value,
  }))

  const summary = computed(() => priceTrends.value?.summary ?? emptySummary)

  const metricCards = computed<DashboardMetricCard[]>(() => [
    {
      label: 'Giá thấp nhất',
      value: formatMoney(summary.value.minPrice),
      detail: 'MIN theo bộ lọc hiện tại',
      icon: 'pi pi-arrow-down-right',
      tone: 'success',
    },
    {
      label: 'Giá cao nhất',
      value: formatMoney(summary.value.maxPrice),
      detail: 'MAX theo bộ lọc hiện tại',
      icon: 'pi pi-arrow-up-right',
      tone: 'warn',
    },
    {
      label: 'Giá trung bình',
      value: formatMoney(summary.value.avgPrice),
      detail: 'TRUNG BÌNH giá quy đổi',
      icon: 'pi pi-chart-line',
      tone: 'info',
    },
    {
      label: 'Tổng báo giá',
      value: formatInteger(summary.value.totalQuotes),
      detail: `${formatInteger(summary.value.totalLines)} dòng, ${formatInteger(summary.value.purchasedLines)} đã chốt mua`,
      icon: 'pi pi-file-check',
      tone: 'primary',
    },
  ])

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
  const trendPoints = computed(() => priceTrends.value?.points ?? [])
  const purchaseContexts = computed(() => priceTrends.value?.purchaseContexts ?? [])
  const hasTrendData = computed(() => trendPoints.value.length > 0)
  const deliveryMonthBuckets = computed(() =>
    buildDeliveryMonthBuckets(trendPoints.value),
  )

  const chartLabels = computed(() =>
    deliveryMonthBuckets.value.map((bucket) => bucket.label),
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

    return {
      maintainAspectRatio: false,
      responsive: true,
      interaction: {
        intersect: false,
        mode: 'index',
      },
      onClick(_event: unknown, elements: { index: number }[]) {
        const bucket = deliveryMonthBuckets.value[elements[0]?.index ?? -1]
        if (!bucket) {
          return
        }
        router.push({ path: '/quotes', query: { deliveryMonth: bucket.deliveryMonth } })
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
                  : `${prefix}: ${formatMoney(bucket.purchasedPrice)}`
              }

              const value =
                prefix === 'Giá thấp nhất'
                  ? bucket.minPrice
                  : prefix === 'Giá cao nhất'
                    ? bucket.maxPrice
                    : bucket.avgPrice
              return `${prefix}: ${formatMoney(value)}`
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
              countEl.textContent = `${bucket.pointCount} báo giá cho kỳ ${bucket.label}`
              tooltipEl.appendChild(countEl)

              const sample = pickRepresentativeTooltipPoints(bucket.points, bucket.avgPrice)
              for (const entry of sample) {
                const swatchColor = entry.role ? roleColors[entry.role] ?? neutralColor : neutralColor
                tooltipEl.appendChild(
                  buildTooltipRowElement(buildTooltipLabel(entry.point), swatchColor),
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
    selectedSupplierType.value = null
    deliveryMonth.value = null
    receivedDateStart.value = null
    receivedDateEnd.value = null
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
    supplierTypeOptions,
    isLoading,
    isLoadingWeeklyEntry,
    isLoadingLookups,
    errorMessage,
    selectedMaterialId,
    selectedSupplierType,
    deliveryMonth,
    receivedDateStart,
    receivedDateEnd,
    selectedWeek,
    selectedWeeklyUserId,
    metricCards,
    userKpis,
    weeklyUserActivities,
    weeklyWarningUsers,
    weeklyEntryMetricCards,
    weeklyEntryPeriodLabel,
    trendPoints,
    deliveryMonthBuckets,
    purchaseContexts,
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
    formatMoney,
    formatDateLabel,
    formatDateTimeLabel,
    formatMonthLabel,
  }
}
