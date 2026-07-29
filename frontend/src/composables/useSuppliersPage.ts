import { reactive, ref } from 'vue'
import { toTypedSchema } from '@vee-validate/zod'
import { useForm } from 'vee-validate'
import { z } from 'zod'

import { ApiError } from '@/api/http'
import { listMaterialsLookup } from '@/api/materials.api'
import {
  createSupplier,
  deleteSupplier,
  listSuppliers,
  updateSupplier,
} from '@/api/suppliers.api'
import { useAuthStore } from '@/stores/auth.store'
import type { CatalogStatus, MaterialDomain } from '@/types/materials'
import type {
  SupplierDomain,
  SupplierListQueryParams,
  SupplierPayload,
  SupplierType,
} from '@/types/suppliers'

type SupplierFormFields = {
  code: string
  name: string
  supplierType: SupplierType
  status: CatalogStatus
  taxCode: string
  address: string
  note: string
}

export type SupplierContactDraft = {
  localId: string
  name: string
  title: string
  email: string
  phone: string
  status: CatalogStatus
}

const supplierSchema = toTypedSchema(
  z.object({
    code: z
      .string()
      .min(1, 'Mã NCC là bắt buộc.')
      .max(50, 'Mã NCC không được quá 50 ký tự.'),
    name: z
      .string()
      .min(1, 'Tên NCC là bắt buộc.')
      .max(200, 'Tên NCC không được quá 200 ký tự.'),
    supplierType: z.enum(['domestic', 'international']),
    status: z.enum(['active', 'inactive']),
    taxCode: z.string().max(50, 'Mã số thuế không được quá 50 ký tự.').optional(),
    address: z.string().max(2000, 'Địa chỉ không được quá 2000 ký tự.').optional(),
    note: z.string().max(2000, 'Ghi chú không được quá 2000 ký tự.').optional(),
  }),
)

const emptyFormValues: SupplierFormFields = {
  code: '',
  name: '',
  supplierType: 'domestic',
  status: 'active',
  taxCode: '',
  address: '',
  note: '',
}

export const supplierTypeOptions: { label: string; value: SupplierType }[] = [
  { label: 'Nội địa', value: 'domestic' },
  { label: 'Quốc tế', value: 'international' },
]

export const supplierTypeFilterOptions: { label: string; value: SupplierType | '' }[] = [
  { label: 'Tất cả', value: '' },
  ...supplierTypeOptions,
]

export const catalogStatusOptions: { label: string; value: CatalogStatus }[] = [
  { label: 'Đang dùng', value: 'active' },
  { label: 'Ngừng dùng', value: 'inactive' },
]

export const statusFilterOptions: { label: string; value: CatalogStatus | '' }[] = [
  { label: 'Tất cả', value: '' },
  ...catalogStatusOptions,
]

export function useSuppliersPage() {
  const authStore = useAuthStore()

  const suppliers = ref<SupplierDomain[]>([])
  const materials = ref<MaterialDomain[]>([])
  const totalSuppliers = ref(0)
  const loading = ref(false)
  const generalError = ref<string | null>(null)
  const submitError = ref<string | null>(null)
  const selectedSupplier = ref<SupplierDomain | null>(null)
  const createDialogVisible = ref(false)
  const editDialogVisible = ref(false)
  const deleteDialogVisible = ref(false)
  const isDeleting = ref(false)
  const createContacts = ref<SupplierContactDraft[]>([])
  const editContacts = ref<SupplierContactDraft[]>([])
  const createMaterialIds = ref<string[]>([])
  const editMaterialIds = ref<string[]>([])
  let latestFetchId = 0
  let searchDebounceTimer: ReturnType<typeof setTimeout> | null = null

  const lazyParams = reactive<SupplierListQueryParams>({
    limit: 10,
    offset: 0,
    search: '',
    supplier_type: '',
    status: '',
    sort_by: 'code',
    sort_order: 'asc',
  })

  async function fetchSuppliers() {
    const fetchId = ++latestFetchId
    loading.value = true
    generalError.value = null
    try {
      const result = await listSuppliers(lazyParams, authStore.accessToken)
      if (fetchId !== latestFetchId) return
      suppliers.value = result.items
      totalSuppliers.value = result.total
    } catch {
      if (fetchId !== latestFetchId) return
      generalError.value = 'Không thể tải danh sách NCC.'
    } finally {
      if (fetchId === latestFetchId) {
        loading.value = false
      }
    }
  }

  async function fetchMaterialsLookup() {
    try {
      materials.value = await listMaterialsLookup(authStore.accessToken)
    } catch {
      materials.value = []
    }
  }

  const createForm = useForm<SupplierFormFields>({
    initialValues: emptyFormValues,
    validationSchema: supplierSchema,
  })
  const [createCode, createCodeProps] = createForm.defineField('code')
  const [createName, createNameProps] = createForm.defineField('name')
  const [createSupplierType, createSupplierTypeProps] =
    createForm.defineField('supplierType')
  const [createStatus, createStatusProps] = createForm.defineField('status')
  const [createTaxCode, createTaxCodeProps] = createForm.defineField('taxCode')
  const [createAddress, createAddressProps] = createForm.defineField('address')
  const [createNote, createNoteProps] = createForm.defineField('note')

  const editForm = useForm<SupplierFormFields>({
    initialValues: emptyFormValues,
    validationSchema: supplierSchema,
  })
  const [editCode, editCodeProps] = editForm.defineField('code')
  const [editName, editNameProps] = editForm.defineField('name')
  const [editSupplierType, editSupplierTypeProps] =
    editForm.defineField('supplierType')
  const [editStatus, editStatusProps] = editForm.defineField('status')
  const [editTaxCode, editTaxCodeProps] = editForm.defineField('taxCode')
  const [editAddress, editAddressProps] = editForm.defineField('address')
  const [editNote, editNoteProps] = editForm.defineField('note')

  const submitCreate = createForm.handleSubmit(async (values) => {
    submitError.value = null
    if (!validateContacts(createContacts.value)) return
    try {
      await createSupplier(
        buildPayload(values, createContacts.value, createMaterialIds.value),
        authStore.accessToken,
      )
      createDialogVisible.value = false
      createForm.resetForm()
      createContacts.value = []
      createMaterialIds.value = []
      await fetchSuppliers()
    } catch (err) {
      handleSubmitError(err, createForm.setErrors)
    }
  })

  const submitEdit = editForm.handleSubmit(async (values) => {
    if (!selectedSupplier.value) return
    submitError.value = null
    if (!validateContacts(editContacts.value)) return
    try {
      await updateSupplier(
        selectedSupplier.value.id,
        buildPayload(values, editContacts.value, editMaterialIds.value),
        authStore.accessToken,
      )
      editDialogVisible.value = false
      editForm.resetForm()
      await fetchSuppliers()
    } catch (err) {
      handleSubmitError(err, editForm.setErrors)
    }
  })

  function handleSubmitError(
    err: unknown,
    setErrors: (fields: Partial<Record<'code', string>>) => void,
  ) {
    if (err instanceof ApiError && err.status === 409) {
      setErrors({ code: 'Mã NCC này đã tồn tại.' })
      return
    }
    if (err instanceof ApiError && err.status === 400) {
      submitError.value =
        'Danh sách vật tư cung cấp không hợp lệ. Chỉ được chọn vật tư đang dùng.'
      return
    }
    submitError.value = 'Lỗi hệ thống khi lưu NCC.'
  }

  function openCreateDialog() {
    submitError.value = null
    createForm.resetForm({ values: { ...emptyFormValues } })
    createContacts.value = []
    createMaterialIds.value = []
    createDialogVisible.value = true
  }

  function openEditDialog(supplier: SupplierDomain) {
    submitError.value = null
    selectedSupplier.value = supplier
    editForm.resetForm({
      values: {
        code: supplier.code,
        name: supplier.name,
        supplierType: supplier.supplierType,
        status: supplier.status,
        taxCode: supplier.taxCode || '',
        address: supplier.address || '',
        note: supplier.note || '',
      },
    })
    editContacts.value = supplier.contacts.map((contact) => ({
      localId: contact.id,
      name: contact.name,
      title: contact.title || '',
      email: contact.email || '',
      phone: contact.phone || '',
      status: contact.status,
    }))
    editMaterialIds.value = supplier.materials.map((material) => material.materialId)
    editDialogVisible.value = true
  }

  function openDeleteDialog(supplier: SupplierDomain) {
    submitError.value = null
    selectedSupplier.value = supplier
    deleteDialogVisible.value = true
  }

  async function submitDelete() {
    if (!selectedSupplier.value) return
    isDeleting.value = true
    submitError.value = null
    try {
      await deleteSupplier(selectedSupplier.value.id, authStore.accessToken)
      deleteDialogVisible.value = false
      selectedSupplier.value = null
      await fetchSuppliers()
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        submitError.value =
          'Không thể xóa NCC đã được tham chiếu. Hãy chuyển trạng thái inactive.'
      } else {
        submitError.value = 'Lỗi hệ thống khi xóa NCC.'
      }
    } finally {
      isDeleting.value = false
    }
  }

  function addContact(target: 'create' | 'edit') {
    const contacts = target === 'create' ? createContacts : editContacts
    contacts.value.push(createContactDraft())
  }

  function removeContact(target: 'create' | 'edit', localId: string) {
    const contacts = target === 'create' ? createContacts : editContacts
    contacts.value = contacts.value.filter((contact) => contact.localId !== localId)
  }

  function buildPayload(
    values: SupplierFormFields,
    contacts: SupplierContactDraft[],
    materialIds: string[],
  ): SupplierPayload {
    return {
      code: values.code,
      name: values.name,
      supplier_type: values.supplierType,
      status: values.status,
      tax_code: values.taxCode || null,
      address: values.address || null,
      note: values.note || null,
      contacts: contacts.map((contact) => ({
        name: contact.name,
        status: contact.status,
        title: contact.title || null,
        email: contact.email || null,
        phone: contact.phone || null,
      })),
      material_ids: materialIds,
    }
  }

  function validateContacts(contacts: SupplierContactDraft[]): boolean {
    const hasInvalidContact = contacts.some((contact) => !contact.name.trim())
    if (hasInvalidContact) {
      submitError.value = 'Tên liên hệ là bắt buộc nếu thêm dòng liên hệ.'
      return false
    }
    return true
  }

  function createContactDraft(): SupplierContactDraft {
    return {
      localId:
        typeof crypto !== 'undefined' && 'randomUUID' in crypto
          ? crypto.randomUUID()
          : `${Date.now()}-${Math.random()}`,
      name: '',
      title: '',
      email: '',
      phone: '',
      status: 'active',
    }
  }

  function formatStatus(status: CatalogStatus) {
    return status === 'active' ? 'Đang dùng' : 'Ngừng dùng'
  }

  function formatSupplierType(supplierType: SupplierType) {
    return supplierType === 'domestic' ? 'Nội địa' : 'Quốc tế'
  }

  function clearSearchDebounce() {
    if (searchDebounceTimer) {
      clearTimeout(searchDebounceTimer)
      searchDebounceTimer = null
    }
  }

  function onPageChange(event: { first: number; rows: number }) {
    clearSearchDebounce()
    lazyParams.offset = event.first
    lazyParams.limit = event.rows
    void fetchSuppliers()
  }

  function onSortChange(event: {
    sortField?: string | ((item: unknown) => string)
    sortOrder?: number | null
  }) {
    clearSearchDebounce()
    lazyParams.sort_by = typeof event.sortField === 'string' ? event.sortField : 'code'
    lazyParams.sort_order = event.sortOrder === -1 ? 'desc' : 'asc'
    void fetchSuppliers()
  }

  function onSearchInput() {
    lazyParams.offset = 0
    clearSearchDebounce()
    searchDebounceTimer = setTimeout(() => {
      searchDebounceTimer = null
      void fetchSuppliers()
    }, 250)
  }

  function onFilterChange() {
    clearSearchDebounce()
    lazyParams.offset = 0
    void fetchSuppliers()
  }

  return {
    suppliers,
    materials,
    totalSuppliers,
    loading,
    generalError,
    submitError,
    selectedSupplier,
    createDialogVisible,
    editDialogVisible,
    deleteDialogVisible,
    isDeleting,
    createContacts,
    editContacts,
    createMaterialIds,
    editMaterialIds,
    lazyParams,
    fetchSuppliers,
    fetchMaterialsLookup,
    openCreateDialog,
    openEditDialog,
    openDeleteDialog,
    submitDelete,
    addContact,
    removeContact,
    createCode,
    createCodeProps,
    createName,
    createNameProps,
    createSupplierType,
    createSupplierTypeProps,
    createStatus,
    createStatusProps,
    createTaxCode,
    createTaxCodeProps,
    createAddress,
    createAddressProps,
    createNote,
    createNoteProps,
    editCode,
    editCodeProps,
    editName,
    editNameProps,
    editSupplierType,
    editSupplierTypeProps,
    editStatus,
    editStatusProps,
    editTaxCode,
    editTaxCodeProps,
    editAddress,
    editAddressProps,
    editNote,
    editNoteProps,
    submitCreate,
    submitEdit,
    formatStatus,
    formatSupplierType,
    onPageChange,
    onSortChange,
    onSearchInput,
    onFilterChange,
  }
}
