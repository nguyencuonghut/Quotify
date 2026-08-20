import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ExchangeRateField from '@/components/quotes/ExchangeRateField.vue'
import { useAuthStore } from '@/stores/auth.store'

const ratesApiMock = vi.hoisted(() => ({
  getUsdSellRateToday: vi.fn(),
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

  it('sets manual_past mode when receivedDate is in the past', async () => {
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
          InputText: true,
          Button: true,
        },
      },
    })

    await nextTick()

    expect(ratesApiMock.getUsdSellRateToday).not.toHaveBeenCalled()
    expect(wrapper.emitted('update:sourceMode')?.[0]).toEqual(['manual_past'])
    expect(wrapper.emitted('update:source')?.[0]).toEqual(['Ngày nhận trong quá khứ'])
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
})
