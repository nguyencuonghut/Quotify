import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { describe, expect, it, vi } from 'vitest'

const dashboardPageMock = vi.hoisted(() => ({
  bootstrap: vi.fn(),
  applyFilters: vi.fn(),
  resetFilters: vi.fn(),
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
      supplierTypeOptions: [
        { label: 'Nội địa', value: 'domestic' },
        { label: 'Quốc tế', value: 'international' },
      ],
      isLoading: ref(false),
      isLoadingLookups: ref(false),
      errorMessage: ref(null),
      selectedMaterialId: ref(null),
      selectedSupplierType: ref(null),
      deliveryMonth: ref(null),
      receivedDateStart: ref(null),
      receivedDateEnd: ref(null),
      metricCards: computed(() => [
        {
          label: 'Giá thấp nhất',
          value: '10.200,00 VNĐ/KG',
          detail: 'MIN theo bộ lọc hiện tại',
          icon: 'pi pi-arrow-down-right',
          tone: 'success',
        },
        {
          label: 'Tổng báo giá',
          value: '7',
          detail: '9 dòng, 2 đã chốt',
          icon: 'pi pi-file-check',
          tone: 'primary',
        },
      ]),
      userKpis: computed(() => [
        {
          userLabel: 'Người mua hàng',
          quoteCount: 7,
        },
      ]),
      deliveryMonthBuckets: computed(() => [
        {
          label: '08/2026',
        },
      ]),
      purchaseContexts: computed(() => []),
      hasTrendData: computed(() => true),
      chartData: computed(() => ({ labels: ['08/2026'], datasets: [] })),
      chartOptions: computed(() => ({})),
      bootstrap: dashboardPageMock.bootstrap,
      applyFilters: dashboardPageMock.applyFilters,
      resetFilters: dashboardPageMock.resetFilters,
      formatMoney: (value: number | null) =>
        value === null ? 'Chưa có dữ liệu' : `${value} VNĐ/KG`,
      formatDateLabel: (value: string) => value,
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
          Column: true,
          DataTable: passthroughStub,
          DatePicker: true,
          Select: true,
          Tag: true,
        },
      },
    })

    expect(dashboardPageMock.bootstrap).toHaveBeenCalled()
    expect(wrapper.text()).toContain('Dashboard Quotify')
    expect(wrapper.text()).toContain('Phân tích giá quy đổi VNĐ/KG')
    expect(wrapper.text()).toContain('Loại NCC')
    expect(wrapper.text()).toContain('Giá thấp nhất')
    expect(wrapper.text()).toContain('Tổng báo giá')
    expect(wrapper.text()).toContain('Giá theo kỳ hàng về')
    expect(wrapper.text()).toContain('Số phiếu báo giá')
    expect(wrapper.text()).toContain('Góc nhìn tại và sau thời điểm đánh dấu')
  })
})
