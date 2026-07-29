import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useSuppliersPage } from '@/composables/useSuppliersPage'
import { useAuthStore } from '@/stores/auth.store'
import type { SupplierDomain } from '@/types/suppliers'

const suppliersApiMock = vi.hoisted(() => ({
  createSupplier: vi.fn(),
  deleteSupplier: vi.fn(),
  listSuppliers: vi.fn(),
  updateSupplier: vi.fn(),
}))

const materialsApiMock = vi.hoisted(() => ({
  listMaterialsLookup: vi.fn(),
}))

vi.mock('@/api/suppliers.api', () => suppliersApiMock)
vi.mock('@/api/materials.api', () => materialsApiMock)

function buildSupplier(overrides: Partial<SupplierDomain> = {}): SupplierDomain {
  return {
    id: 'supplier-1',
    code: 'WILMAR',
    name: 'Wilmar Agro Việt Nam (Wilmar Agro)',
    supplierType: 'domestic',
    status: 'active',
    taxCode: null,
    address: null,
    note: null,
    contacts: [],
    materials: [],
    createdAt: '2026-07-29T00:00:00+00:00',
    updatedAt: '2026-07-29T00:00:00+00:00',
    ...overrides,
  }
}

describe('useSuppliersPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.useRealTimers()

    const authStore = useAuthStore()
    authStore.accessToken = 'mock-access-token'
  })

  it('debounces supplier search so row actions are not blocked by immediate table reload', async () => {
    vi.useFakeTimers()
    suppliersApiMock.listSuppliers.mockResolvedValue({ items: [], total: 0 })

    const page = useSuppliersPage()
    page.lazyParams.search = 'W'
    page.onSearchInput()

    expect(suppliersApiMock.listSuppliers).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(249)
    expect(suppliersApiMock.listSuppliers).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(1)
    expect(suppliersApiMock.listSuppliers).toHaveBeenCalledTimes(1)
    expect(suppliersApiMock.listSuppliers).toHaveBeenCalledWith(
      expect.objectContaining({ offset: 0, search: 'W' }),
      'mock-access-token',
    )
  })

  it('keeps the newest supplier list when older requests finish later', async () => {
    let resolveSlow:
      | ((value: { items: SupplierDomain[]; total: number }) => void)
      | undefined
    const slowRequest = new Promise<{ items: SupplierDomain[]; total: number }>(
      (resolve) => {
        resolveSlow = resolve
      },
    )
    suppliersApiMock.listSuppliers
      .mockReturnValueOnce(slowRequest)
      .mockResolvedValueOnce({
        items: [buildSupplier({ id: 'new-supplier', code: 'NEW' })],
        total: 1,
      })

    const page = useSuppliersPage()
    const firstFetch = page.fetchSuppliers()
    const secondFetch = page.fetchSuppliers()
    await secondFetch

    expect(page.suppliers.value).toEqual([
      expect.objectContaining({ id: 'new-supplier' }),
    ])

    resolveSlow?.({
      items: [buildSupplier({ id: 'old-supplier', code: 'OLD' })],
      total: 1,
    })
    await firstFetch

    expect(page.suppliers.value).toEqual([
      expect.objectContaining({ id: 'new-supplier' }),
    ])
    expect(page.loading.value).toBe(false)
  })

  it('opens edit state from the selected supplier immediately', () => {
    const page = useSuppliersPage()
    const supplier = buildSupplier({
      contacts: [
        {
          id: 'contact-1',
          name: 'Người liên hệ',
          title: null,
          email: null,
          phone: null,
          status: 'active',
          createdAt: '2026-07-29T00:00:00+00:00',
          updatedAt: '2026-07-29T00:00:00+00:00',
        },
      ],
      materials: [
        {
          materialId: 'material-1',
          materialCode: 'SOYBEAN_MEAL',
          materialName: 'Khô đậu nành',
        },
      ],
    })

    page.openEditDialog(supplier)

    expect(page.editDialogVisible.value).toBe(true)
    expect(page.selectedSupplier.value).toMatchObject({
      id: 'supplier-1',
      code: 'WILMAR',
    })
    expect(page.editName.value).toBe('Wilmar Agro Việt Nam (Wilmar Agro)')
    expect(page.editContacts.value).toEqual([
      expect.objectContaining({ localId: 'contact-1', name: 'Người liên hệ' }),
    ])
    expect(page.editMaterialIds.value).toEqual(['material-1'])
  })
})
