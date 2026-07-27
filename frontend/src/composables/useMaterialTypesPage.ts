import { reactive, ref } from 'vue'
import { toTypedSchema } from '@vee-validate/zod'
import { useForm } from 'vee-validate'
import { z } from 'zod'

import { ApiError } from '@/api/http'
import {
  createMaterialType,
  deleteMaterialType,
  listMaterialTypes,
  updateMaterialType,
} from '@/api/materials.api'
import { useAuthStore } from '@/stores/auth.store'
import type {
  CatalogListQueryParams,
  CatalogStatus,
  MaterialTypeDomain,
} from '@/types/materials'

export const catalogStatusOptions: Array<{
  label: string
  value: CatalogStatus
}> = [
  { label: 'Đang dùng', value: 'active' },
  { label: 'Ngừng dùng', value: 'inactive' },
]

const materialTypeSchema = toTypedSchema(
  z.object({
    code: z
      .string()
      .min(1, 'Mã loại vật tư là bắt buộc.')
      .max(50, 'Mã loại vật tư không được quá 50 ký tự.'),
    name: z
      .string()
      .min(1, 'Tên loại vật tư là bắt buộc.')
      .max(150, 'Tên loại vật tư không được quá 150 ký tự.'),
    status: z.enum(['active', 'inactive']),
    note: z
      .string()
      .max(2000, 'Ghi chú không được quá 2000 ký tự.')
      .optional()
      .nullable()
      .or(z.literal('')),
  }),
)

export function useMaterialTypesPage() {
  const authStore = useAuthStore()

  const materialTypes = ref<MaterialTypeDomain[]>([])
  const totalMaterialTypes = ref(0)
  const loading = ref(false)
  const generalError = ref<string | null>(null)
  const submitError = ref<string | null>(null)
  const selectedMaterialType = ref<MaterialTypeDomain | null>(null)
  const createDialogVisible = ref(false)
  const editDialogVisible = ref(false)
  const deleteDialogVisible = ref(false)
  const isDeleting = ref(false)

  const lazyParams = reactive<CatalogListQueryParams>({
    limit: 10,
    offset: 0,
    search: '',
    status: '',
    sort_by: 'code',
    sort_order: 'asc',
  })

  async function fetchMaterialTypes() {
    loading.value = true
    generalError.value = null
    try {
      const result = await listMaterialTypes(lazyParams, authStore.accessToken)
      materialTypes.value = result.items
      totalMaterialTypes.value = result.total
    } catch {
      generalError.value = 'Không thể tải danh sách loại vật tư.'
    } finally {
      loading.value = false
    }
  }

  const createForm = useForm({
    initialValues: {
      code: '',
      name: '',
      status: 'active' as CatalogStatus,
      note: '',
    },
    validationSchema: materialTypeSchema,
  })
  const [createCode, createCodeProps] = createForm.defineField('code')
  const [createName, createNameProps] = createForm.defineField('name')
  const [createStatus, createStatusProps] = createForm.defineField('status')
  const [createNote, createNoteProps] = createForm.defineField('note')

  const editForm = useForm({
    initialValues: {
      code: '',
      name: '',
      status: 'active' as CatalogStatus,
      note: '',
    },
    validationSchema: materialTypeSchema,
  })
  const [editCode, editCodeProps] = editForm.defineField('code')
  const [editName, editNameProps] = editForm.defineField('name')
  const [editStatus, editStatusProps] = editForm.defineField('status')
  const [editNote, editNoteProps] = editForm.defineField('note')

  const submitCreate = createForm.handleSubmit(async (values) => {
    submitError.value = null
    try {
      await createMaterialType(
        {
          code: values.code,
          name: values.name,
          status: values.status,
          note: values.note || null,
        },
        authStore.accessToken,
      )
      createDialogVisible.value = false
      createForm.resetForm()
      await fetchMaterialTypes()
    } catch (err) {
      handleSubmitError(err, createForm.setErrors)
    }
  })

  const submitEdit = editForm.handleSubmit(async (values) => {
    if (!selectedMaterialType.value) return
    submitError.value = null
    try {
      await updateMaterialType(
        selectedMaterialType.value.id,
        {
          code: values.code,
          name: values.name,
          status: values.status,
          note: values.note || null,
        },
        authStore.accessToken,
      )
      editDialogVisible.value = false
      editForm.resetForm()
      await fetchMaterialTypes()
    } catch (err) {
      handleSubmitError(err, editForm.setErrors)
    }
  })

  function handleSubmitError(
    err: unknown,
    setErrors: (fields: Partial<Record<'code', string>>) => void,
  ) {
    if (err instanceof ApiError && err.status === 409) {
      setErrors({ code: 'Mã loại vật tư này đã tồn tại.' })
      return
    }
    submitError.value = 'Lỗi hệ thống khi lưu loại vật tư.'
  }

  function openCreateDialog() {
    submitError.value = null
    createForm.resetForm({
      values: {
        code: '',
        name: '',
        status: 'active',
        note: '',
      },
    })
    createDialogVisible.value = true
  }

  function openEditDialog(materialType: MaterialTypeDomain) {
    submitError.value = null
    selectedMaterialType.value = materialType
    editForm.resetForm({
      values: {
        code: materialType.code,
        name: materialType.name,
        status: materialType.status,
        note: materialType.note || '',
      },
    })
    editDialogVisible.value = true
  }

  function openDeleteDialog(materialType: MaterialTypeDomain) {
    submitError.value = null
    selectedMaterialType.value = materialType
    deleteDialogVisible.value = true
  }

  async function submitDelete() {
    if (!selectedMaterialType.value) return
    isDeleting.value = true
    submitError.value = null
    try {
      await deleteMaterialType(selectedMaterialType.value.id, authStore.accessToken)
      deleteDialogVisible.value = false
      selectedMaterialType.value = null
      await fetchMaterialTypes()
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        submitError.value =
          'Không thể xóa loại vật tư đang có vật tư. Hãy chuyển trạng thái inactive.'
      } else {
        submitError.value = 'Lỗi hệ thống khi xóa loại vật tư.'
      }
    } finally {
      isDeleting.value = false
    }
  }

  return {
    materialTypes,
    totalMaterialTypes,
    loading,
    generalError,
    submitError,
    selectedMaterialType,
    createDialogVisible,
    editDialogVisible,
    deleteDialogVisible,
    isDeleting,
    lazyParams,
    fetchMaterialTypes,
    openCreateDialog,
    openEditDialog,
    openDeleteDialog,
    submitDelete,
    createCode,
    createCodeProps,
    createName,
    createNameProps,
    createStatus,
    createStatusProps,
    createNote,
    createNoteProps,
    createErrors: createForm.errors,
    createFormSubmitting: createForm.isSubmitting,
    submitCreate,
    editCode,
    editCodeProps,
    editName,
    editNameProps,
    editStatus,
    editStatusProps,
    editNote,
    editNoteProps,
    editErrors: editForm.errors,
    editFormSubmitting: editForm.isSubmitting,
    submitEdit,
  }
}
