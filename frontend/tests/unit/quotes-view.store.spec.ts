import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useQuotesViewStore, type QuotesViewState } from '@/stores/quotes-view.store'

const STORAGE_KEY = 'quotify-quotes-view'

const sampleSnapshot: QuotesViewState = {
  globalSearch: 'Tân Long',
  supplierId: 'supplier-1',
  materialId: null,
  materialTypeId: null,
  receivedDateStart: '2026-05-11',
  receivedDateEnd: null,
  deliveryMonth: null,
  purchased: true,
  cancelled: null,
  versionStatus: null,
  limit: 20,
  offset: 40,
  sortField: 'price_converted_vnd_per_kg',
  sortOrder: 'asc',
}

describe('quotes-view.store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    window.sessionStorage.clear()
  })

  it('starts with no snapshot when sessionStorage is empty', () => {
    const store = useQuotesViewStore()
    expect(store.snapshot).toBeNull()
  })

  it('persists a saved snapshot to sessionStorage so it survives a page reload', () => {
    const store = useQuotesViewStore()

    store.save(sampleSnapshot)

    expect(store.snapshot).toEqual(sampleSnapshot)
    expect(JSON.parse(window.sessionStorage.getItem(STORAGE_KEY) ?? '')).toEqual(
      sampleSnapshot,
    )
  })

  it('rehydrates the snapshot from sessionStorage on a fresh store instance (simulating navigating back from quote detail)', () => {
    const firstStore = useQuotesViewStore()
    firstStore.save(sampleSnapshot)

    // Mô phỏng việc QuotesPage.vue bị unmount rồi mount lại (bấm back từ
    // trang chi tiết) — Pinia instance mới vẫn đọc lại đúng snapshot đã lưu.
    setActivePinia(createPinia())
    const secondStore = useQuotesViewStore()

    expect(secondStore.snapshot).toEqual(sampleSnapshot)
  })

  it('ignores corrupted sessionStorage content instead of throwing', () => {
    window.sessionStorage.setItem(STORAGE_KEY, '{not valid json')

    const store = useQuotesViewStore()

    expect(store.snapshot).toBeNull()
  })

  it('clears the snapshot from both the store and sessionStorage', () => {
    const store = useQuotesViewStore()
    store.save(sampleSnapshot)

    store.clear()

    expect(store.snapshot).toBeNull()
    expect(window.sessionStorage.getItem(STORAGE_KEY)).toBeNull()
  })
})
