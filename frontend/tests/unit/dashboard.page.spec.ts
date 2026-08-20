import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { describe, expect, it, vi } from 'vitest'

const dashboardPageMock = vi.hoisted(() => ({
  bootstrap: vi.fn(),
  applyFilters: vi.fn(),
  resetFilters: vi.fn(),
  applyWeeklyEntryFilters: vi.fn(),
  resetWeeklyEntryFilters: vi.fn(),
  loadPriceHistory: vi.fn(),
  loadSeasonalComparison: vi.fn(),
}))

vi.mock('@/composables/useDashboardPage', async () => {
  const { computed, ref } = await import('vue')

  return {
    useDashboardPage: () => ({
      materials: ref([
        {
          id: 'material-1',
          name: 'Ngô hạt',
        },
      ]),
      isLoading: ref(false),
      isLoadingWeeklyEntry: ref(false),
      isLoadingLookups: ref(false),
      errorMessage: ref(null),
      selectedMaterialId: ref(null),
      deliveryMonth: ref(null),
      receivedDateStart: ref(null),
      receivedDateEnd: ref(null),
      showCnfOnly: ref(false),
      selectedWeek: ref(null),
      selectedWeeklyUserId: ref(null),
      historyDeliveryMonth: ref(null),
      historyMaterialIds: ref([]),
      historyBuckets: computed(() => []),
      historyBandVisibility: ref({}),
      historyTrendResults: computed(() => []),
      historyShowCnfOnly: ref(false),
      historyChartData: computed(() => ({ labels: [], datasets: [] })),
      historyChartOptions: computed(() => ({})),
      seasonalMaterialId: ref(null),
      seasonalMonth: ref(null),
      seasonalYears: ref([]),
      seasonalAvailableYears: computed(() => []),
      seasonalBuckets: computed(() => []),
      seasonalBandVisibility: ref({}),
      seasonalTrendResults: computed(() => []),
      seasonalShowCnfOnly: ref(false),
      seasonalChartData: computed(() => ({ labels: [], datasets: [] })),
      seasonalChartOptions: computed(() => ({})),
      weeklyUserOptions: [
        {
          label: 'Người mua hàng',
          value: 'user-1',
        },
      ],
      userKpis: computed(() => [
        {
          userLabel: 'Người mua hàng',
          quoteCount: 7,
        },
      ]),
      weeklyUserActivities: computed(() => [
        {
          userId: 'user-1',
          userLabel: 'Người mua hàng',
          quoteCount: 7,
          lastQuoteCreatedAt: '2026-07-29T02:00:00+00:00',
          hasWarning: false,
        },
        {
          userId: 'user-2',
          userLabel: 'Người chưa nhập',
          quoteCount: 0,
          lastQuoteCreatedAt: null,
          hasWarning: true,
        },
      ]),
      weeklyWarningUsers: computed(() => [
        {
          userId: 'user-2',
        },
      ]),
      weeklyEntryMetricCards: computed(() => [
        {
          label: 'Báo giá tuần',
          value: '7',
          detail: '27/07/2026 - 02/08/2026',
          icon: 'pi pi-calendar-clock',
          tone: 'primary',
        },
        {
          label: 'User chưa nhập',
          value: '1',
          detail: 'Cần nhắc nhập báo giá',
          icon: 'pi pi-exclamation-triangle',
          tone: 'warn',
        },
      ]),
      deliveryMonthBuckets: computed(() => [
        {
          label: '08/2026',
        },
      ]),
      purchaseContexts: computed(() => []),
      hasTrendData: computed(() => true),
      hasWeeklyEntryData: computed(() => true),
      chartData: computed(() => ({ labels: ['08/2026'], datasets: [] })),
      chartOptions: computed(() => ({})),
      weeklyEntryChartData: computed(() => ({
        labels: ['Người mua hàng', 'Người chưa nhập'],
        datasets: [],
      })),
      weeklyEntryChartOptions: computed(() => ({})),
      bootstrap: dashboardPageMock.bootstrap,
      applyFilters: dashboardPageMock.applyFilters,
      resetFilters: dashboardPageMock.resetFilters,
      applyWeeklyEntryFilters: dashboardPageMock.applyWeeklyEntryFilters,
      resetWeeklyEntryFilters: dashboardPageMock.resetWeeklyEntryFilters,
      loadPriceHistory: dashboardPageMock.loadPriceHistory,
      loadSeasonalComparison: dashboardPageMock.loadSeasonalComparison,
      getWeeklyEntryRowClass: (row: { hasWarning: boolean }) =>
        row.hasWarning ? 'dashboard-page__weekly-row--warning' : '',
      formatMoney: (value: number | null) =>
        value === null ? 'Chưa có dữ liệu' : `${value} VNĐ/KG`,
      formatDateLabel: (value: string) => value,
      formatDateTimeLabel: (value: string | null) => value ?? '-',
      formatMonthLabel: (value: string) => value,
    }),
  }
})

import DashboardPage from '@/pages/DashboardPage.vue'

const passthroughStub = defineComponent({
  template: '<div><slot /></div>',
})

describe('DashboardPage', () => {
  it('renders the Quotify price analysis dashboard shell', () => {
    const wrapper = mount(DashboardPage, {
      global: {
        stubs: {
          AdminLayout: passthroughStub,
          Button: true,
          Chart: true,
          Checkbox: true,
          Column: true,
          DataTable: passthroughStub,
          DatePicker: true,
          MultiSelect: true,
          Select: true,
          SelectButton: true,
          Tab: passthroughStub,
          TabList: passthroughStub,
          TabPanel: passthroughStub,
          TabPanels: passthroughStub,
          Tabs: passthroughStub,
          Tag: true,
        },
      },
    })

    expect(dashboardPageMock.bootstrap).toHaveBeenCalled()
    expect(wrapper.text()).toContain('Dashboard Quotify')
    expect(wrapper.text()).toContain('Phân tích giá quy đổi VNĐ/KG')
    expect(wrapper.text()).toContain('Giá CNF')
    expect(wrapper.text()).toContain('Tình hình nhập báo giá theo tuần')
    expect(wrapper.text()).toContain('Người nhập')
    expect(wrapper.text()).toContain('User chưa nhập')
    expect(wrapper.text()).toContain('Giá theo kỳ hàng về')
    expect(wrapper.text()).toContain('Kỳ giao hàng (bắt buộc chọn)')
    expect(wrapper.text()).toContain('Số phiếu báo giá')
  })
})
