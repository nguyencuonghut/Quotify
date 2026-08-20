import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ExchangeRateField from '@/components/quotes/ExchangeRateField.vue'
import { useAuthStore } from '@/stores/auth.store'

const ratesApiMock = vi.hoisted(() => ({
  getUsdSellRateToday: vi.fn(),
  getUsdSellRateForDate: vi.fn(),
}))

vi.mock('@/api/exchange-rates.api', () => ratesApiMock)

// Helper để lấy ngày hôm nay định dạng YYYY-MM-DD
function getTodayString() {
  return new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'Asia/Ho_Chi_Minh',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date())
}

describe('ExchangeRateField', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()

    const authStore = useAuthStore()
    authStore.accessToken = 'mock-token'
  })

  it('renders default fields correctly', () => {
    const wrapper = mount(ExchangeRateField, {
      props: {
        receivedDate: '2026-07-28',
        rate: 26000,
        source: 'Vietcombank USD bán ra',
        sourceMode: 'auto',
        manualReason: '',
      },
      global: {
        stubs: {
          InputNumber: {
            props: ['modelValue', 'disabled'],
            template: '<input type="number" :value="modelValue" :disabled="disabled" />',
          },
          InputText: true,
          Button: true,
        },
      },
    })

    expect(wrapper.text()).toContain('Tỷ giá quy đổi (VNĐ/USD)')
    expect(wrapper.text()).toContain('Nguồn tỷ giá')
    expect(wrapper.text()).toContain('Vietcombank USD bán ra')
    expect(wrapper.text()).toContain('Tự động')

    const input = wrapper.find('input[type="number"]')
    expect(input.exists()).toBe(true)
    expect(input.attributes('disabled')).toBeDefined() // readonly in auto mode
  })

  it('triggers auto-fetch when mounted with today receivedDate', async () => {
    const today = getTodayString()
    ratesApiMock.getUsdSellRateToday.mockResolvedValue({
      currency: 'USD',
      rate: '26150.00',
      source: 'Vietcombank USD bán ra',
      retrievedAt: '2026-07-28T08:00:00+07:00',
    })

    const wrapper = mount(ExchangeRateField, {
      props: {
        receivedDate: today,
        rate: null,
        source: '',
        sourceMode: '',
        manualReason: '',
      },
      global: {
        stubs: {
          InputNumber: true,
          InputText: true,
          Button: true,
        },
      },
    })

    // Chờ async lifecycle onMounted và triggerFetchTodayRate
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(ratesApiMock.getUsdSellRateToday).toHaveBeenCalledWith('mock-token')
    
    // Check emitted events
    const rateEmitted = wrapper.emitted('update:rate')
    const sourceEmitted = wrapper.emitted('update:source')
    const modeEmitted = wrapper.emitted('update:sourceMode')
    
    expect(rateEmitted?.[0]).toEqual([26150])
    expect(sourceEmitted?.[0]).toEqual(['Vietcombank USD bán ra'])
    expect(modeEmitted?.[0]).toEqual(['auto'])
  })

  it('switches to manual_fallback when auto-fetch fails', async () => {
    const today = getTodayString()
    ratesApiMock.getUsdSellRateToday.mockRejectedValue(new Error('Outage'))

    const wrapper = mount(ExchangeRateField, {
      props: {
        receivedDate: today,
        rate: null,
        source: '',
        sourceMode: '',
        manualReason: '',
      },
      global: {
        stubs: {
          InputNumber: true,
          InputText: true,
          Button: true,
        },
      },
    })

    await new Promise((resolve) => setTimeout(resolve, 0))
    await nextTick()

    expect(ratesApiMock.getUsdSellRateToday).toHaveBeenCalled()

    const modeEmitted = wrapper.emitted('update:sourceMode')
    const sourceEmitted = wrapper.emitted('update:source')

    expect(modeEmitted?.[0]).toEqual(['manual_fallback'])
    expect(sourceEmitted?.[0]).toEqual(['Không lấy được tỷ giá tự động'])
  })

  it('auto-fetches the past-date rate on mount and sets manual_past immediately while loading', async () => {
    ratesApiMock.getUsdSellRateForDate.mockResolvedValue({
      currency: 'USD',
      rate: '26350.00',
      source: 'Vietcombank USD bán ra',
      retrievedAt: '2020-01-01T00:00:00+07:00',
    })

    const wrapper = mount(ExchangeRateField, {
      props: {
        receivedDate: '2020-01-01',
        rate: null,
        source: '',
        sourceMode: '',
        manualReason: '',
      },
      global: {
        stubs: {
          InputNumber: true,
          Button: true,
        },
      },
    })

    await nextTick()

    expect(ratesApiMock.getUsdSellRateToday).not.toHaveBeenCalled()
    // Đặt mode/source ngay lập tức (trước khi fetch xong) để UI phản hồi tức thì
    expect(wrapper.emitted('update:sourceMode')?.[0]).toEqual(['manual_past'])
    expect(wrapper.emitted('update:source')?.[0]).toEqual(['Ngày nhận trong quá khứ'])

    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(ratesApiMock.getUsdSellRateForDate).toHaveBeenCalledWith('2020-01-01', 'mock-token')
    const sourceModeEmits = wrapper.emitted('update:sourceMode') ?? []
    expect(sourceModeEmits[sourceModeEmits.length - 1]).toEqual(['auto'])
    expect(wrapper.emitted('update:rate')?.at(-1)).toEqual([26350])
  })

  it('keeps manual_past and shows an error when the mount-time past-date fetch fails', async () => {
    ratesApiMock.getUsdSellRateForDate.mockRejectedValue(new Error('boom'))

    const wrapper = mount(ExchangeRateField, {
      props: {
        receivedDate: '2020-01-01',
        rate: null,
        source: '',
        sourceMode: '',
        manualReason: '',
      },
      global: {
        stubs: {
          InputNumber: true,
          Button: true,
        },
      },
    })

    await new Promise((resolve) => setTimeout(resolve, 0))
    await nextTick()

    // props không được cập nhật lại trong test (không có v-model thật ở đây)
    // nên chỉ kiểm tra các sự kiện emit — banner lỗi phụ thuộc prop sourceMode
    // thật sự được cập nhật, đã kiểm ở test dùng sourceMode ban đầu khác rỗng.
    const sourceModeEmits = wrapper.emitted('update:sourceMode') ?? []
    expect(sourceModeEmits.every((emitted) => emitted[0] === 'manual_past')).toBe(true)
    expect(ratesApiMock.getUsdSellRateForDate).toHaveBeenCalledWith('2020-01-01', 'mock-token')
  })

  it('emits changes when rate is modified', async () => {
    const wrapper = mount(ExchangeRateField, {
      props: {
        receivedDate: '2020-01-01',
        rate: 26000,
        source: 'Ngày nhận trong quá khứ',
        sourceMode: 'manual_past',
        manualReason: '',
      },
      global: {
        stubs: {
          InputNumber: {
            props: ['modelValue'],
            template: '<input type="number" :value="modelValue" @input="$emit(\'update:modelValue\', Number($event.target.value))" />',
          },
          Button: true,
        },
      },
    })

    const rateInput = wrapper.find('input[type="number"]')
    await rateInput.setValue(26200)
    expect(wrapper.emitted('update:rate')?.[0]).toEqual([26200])
  })

  it('respects disabled property by disabling the rate input', () => {
    const wrapper = mount(ExchangeRateField, {
      props: {
        receivedDate: '2026-07-28',
        rate: 26000,
        source: 'Không lấy được tỷ giá tự động',
        sourceMode: 'manual_fallback',
        manualReason: '',
        disabled: true,
      },
      global: {
        stubs: {
          InputNumber: {
            props: ['disabled'],
            template: '<input class="rate-input" :disabled="disabled" />',
          },
          Button: true,
        },
      },
    })

    const rateInput = wrapper.find('.rate-input')

    expect(rateInput.attributes('disabled')).toBeDefined()
  })

  it('fetches the rate for a past received date when the button is clicked', async () => {
    ratesApiMock.getUsdSellRateForDate.mockResolvedValue({
      currency: 'USD',
      rate: '26330.00',
      source: 'Vietcombank USD bán ra',
      retrievedAt: '2026-08-15T00:00:00+07:00',
    })

    const wrapper = mount(ExchangeRateField, {
      props: {
        receivedDate: '2026-08-15',
        rate: null,
        source: 'Ngày nhận trong quá khứ',
        sourceMode: 'manual_past',
        manualReason: '',
      },
      global: {
        stubs: {
          InputNumber: true,
        },
      },
    })

    const fetchButton = wrapper.find(
      '[aria-label="Lấy tỷ giá Vietcombank theo ngày nhận báo giá"]',
    )
    expect(fetchButton.exists()).toBe(true)
    await fetchButton.trigger('click')
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(ratesApiMock.getUsdSellRateForDate).toHaveBeenCalledWith('2026-08-15', 'mock-token')
    expect(wrapper.emitted('update:rate')?.[0]).toEqual([26330])
    // Emit đầu là 'Ngày nhận trong quá khứ'/'manual_past' (đặt ngay khi bắt
    // đầu fetch để UI phản hồi tức thì) — emit CUỐI mới là kết quả fetch thật.
    expect(wrapper.emitted('update:source')?.at(-1)).toEqual(['Vietcombank USD bán ra'])
    expect(wrapper.emitted('update:sourceMode')?.at(-1)).toEqual(['auto'])
  })

  it('shows an inline error and keeps manual entry when the past-date fetch fails', async () => {
    ratesApiMock.getUsdSellRateForDate.mockRejectedValue(new Error('boom'))

    const wrapper = mount(ExchangeRateField, {
      props: {
        receivedDate: '2020-01-01',
        rate: null,
        source: 'Ngày nhận trong quá khứ',
        sourceMode: 'manual_past',
        manualReason: '',
      },
      global: {
        stubs: {
          InputNumber: true,
        },
      },
    })

    const fetchButton = wrapper.find(
      '[aria-label="Lấy tỷ giá Vietcombank theo ngày nhận báo giá"]',
    )
    await fetchButton.trigger('click')
    await new Promise((resolve) => setTimeout(resolve, 0))
    await nextTick()

    // Vẫn ở manual_past (mode chỉ chuyển 'auto' khi fetch thành công)
    const sourceModeEmits = wrapper.emitted('update:sourceMode') ?? []
    expect(sourceModeEmits.every((emitted) => emitted[0] === 'manual_past')).toBe(true)
    expect(wrapper.text()).toContain('Vui lòng nhập tay tỷ giá')
  })
})
