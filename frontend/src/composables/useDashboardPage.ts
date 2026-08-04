import { computed, ref } from 'vue'

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

    return {
      maintainAspectRatio: false,
      responsive: true,
      interaction: {
        intersect: false,
        mode: 'index',
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
            afterBody(context: { dataIndex: number }[]) {
              const bucket = deliveryMonthBuckets.value[context[0]?.dataIndex ?? -1]
              if (!bucket) {
                return []
              }

              return [
                `${bucket.pointCount} báo giá cho kỳ ${bucket.label}`,
                ...bucket.points.slice(0, 5).map(buildTooltipLabel),
              ]
            },
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
