import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useDashboardViewStore, type DashboardViewState } from '@/stores/dashboard-view.store'

const STORAGE_KEY = 'quotify-dashboard-view'

const sampleSnapshot: DashboardViewState = {
  activeMainTab: 'charts',
  activeChartKey: 'period',
  period: {
    selectedMaterialId: 'material-1',
    deliveryMonth: '2026-10-01',
    receivedDateStart: '2026-05-11',
    receivedDateEnd: '2026-05-11',
    showCnfOnly: false,
    periodRangeKey: '6m',
  },
  history: {
    historyDeliveryMonth: null,
    historyMaterialIds: [],
    historyShowCnfOnly: false,
  },
  seasonal: {
    seasonalMaterialId: null,
    seasonalMonth: null,
    seasonalYears: [],
    seasonalShowCnfOnly: false,
  },
}

describe('dashboard-view.store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    window.sessionStorage.clear()
  })

  it('starts with no snapshot when sessionStorage is empty', () => {
    const store = useDashboardViewStore()
    expect(store.snapshot).toBeNull()
  })

  it('persists a saved snapshot to sessionStorage so it survives a page reload', () => {
    const store = useDashboardViewStore()

    store.save(sampleSnapshot)

    expect(store.snapshot).toEqual(sampleSnapshot)
    expect(JSON.parse(window.sessionStorage.getItem(STORAGE_KEY) ?? '')).toEqual(
      sampleSnapshot,
    )
  })

  it('rehydrates the snapshot from sessionStorage on a fresh store instance (simulating a page reload)', () => {
    const firstStore = useDashboardViewStore()
    firstStore.save(sampleSnapshot)

    // Mô phỏng F5: Pinia instance mới, đọc lại đúng snapshot đã lưu trước
    // đó từ sessionStorage — không mất trạng thái đang xem dở dù giữa
    // chừng có refresh (khác với chỉ giữ state in-memory trong Pinia).
    setActivePinia(createPinia())
    const secondStore = useDashboardViewStore()

    expect(secondStore.snapshot).toEqual(sampleSnapshot)
  })

  it('ignores corrupted sessionStorage content instead of throwing', () => {
    window.sessionStorage.setItem(STORAGE_KEY, '{not valid json')

    const store = useDashboardViewStore()

    expect(store.snapshot).toBeNull()
  })

  it('clears the snapshot from both the store and sessionStorage', () => {
    const store = useDashboardViewStore()
    store.save(sampleSnapshot)

    store.clear()

    expect(store.snapshot).toBeNull()
    expect(window.sessionStorage.getItem(STORAGE_KEY)).toBeNull()
  })
})
