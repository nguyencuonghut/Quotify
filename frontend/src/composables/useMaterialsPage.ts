import { reactive, ref } from 'vue'
import { toTypedSchema } from '@vee-validate/zod'
import { useForm } from 'vee-validate'
import { z } from 'zod'

import { ApiError } from '@/api/http'
import {
  createMaterial,
  deleteMaterial,
  listMaterials,
  listMaterialTypesLookup,
  updateMaterial,
} from '@/api/materials.api'
import { useAuthStore } from '@/stores/auth.store'
import type {
  CatalogListQueryParams,
  CatalogStatus,
  MaterialDomain,
  MaterialTypeDomain,
} from '@/types/materials'

const materialSchema = toTypedSchema(
  z.object({
    code: z
      .string()
      .min(1, 'Mã vật tư là bắt buộc.')
      .max(50, 'Mã vật tư không được quá 50 ký tự.'),
    name: z
      .string()
      .min(1, 'Tên vật tư là bắt buộc.')
      .max(150, 'Tên vật tư không được quá 150 ký tự.'),
    materialTypeId: z.string().min(1, 'Loại vật tư là bắt buộc.'),
    status: z.enum(['active', 'inactive']),
    note: z
      .string()
      .max(2000, 'Ghi chú không được quá 2000 ký tự.')
      .optional()
      .nullable()
      .or(z.literal('')),
  }),
)

export function useMaterialsPage() {
  const authStore = useAuthStore()

  const materials = ref<MaterialDomain[]>([])
  const materialTypes = ref<MaterialTypeDomain[]>([])
  const totalMaterials = ref(0)
  const loading = ref(false)
  const generalError = ref<string | null>(null)
  const submitError = ref<string | null>(null)
  const selectedMaterial = ref<MaterialDomain | null>(null)
  const createDialogVisible = ref(false)
  const editDialogVisible = ref(false)
  const deleteDialogVisible = ref(false)
  const isDeleting = ref(false)

  const lazyParams = reactive<CatalogListQueryParams>({
    limit: 10,
    offset: 0,
    search: '',
    status: '',
    material_type_id: '',
    sort_by: 'code',
    sort_order: 'asc',
  })

  async function fetchMaterials() {
    loading.value = true
    generalError.value = null
    try {
      const result = await listMaterials(lazyParams, authStore.accessToken)
      materials.value = result.items
      totalMaterials.value = result.total
    } catch {
      generalError.value = 'Không thể tải danh sách vật tư.'
    } finally {
      loading.value = false
    }
  }

  async function fetchMaterialTypesLookup() {
    try {
      materialTypes.value = await listMaterialTypesLookup(authStore.accessToken)
    } catch {
      materialTypes.value = []
    }
  }

  const createForm = useForm({
    initialValues: {
      code: '',
      name: '',
      materialTypeId: '',
      status: 'active' as CatalogStatus,
      note: '',
    },
    validationSchema: materialSchema,
  })
  const [createCode, createCodeProps] = createForm.defineField('code')
  const [createName, createNameProps] = createForm.defineField('name')
  const [createMaterialTypeId, createMaterialTypeIdProps] =
    createForm.defineField('materialTypeId')
  const [createStatus, createStatusProps] = createForm.defineField('status')
  const [createNote, createNoteProps] = createForm.defineField('note')

  const editForm = useForm({
    initialValues: {
      code: '',
      name: '',
      materialTypeId: '',
      status: 'active' as CatalogStatus,
      note: '',
    },
    validationSchema: materialSchema,
  })
  const [editCode, editCodeProps] = editForm.defineField('code')
  const [editName, editNameProps] = editForm.defineField('name')
  const [editMaterialTypeId, editMaterialTypeIdProps] =
    editForm.defineField('materialTypeId')
  const [editStatus, editStatusProps] = editForm.defineField('status')
  const [editNote, editNoteProps] = editForm.defineField('note')

  const submitCreate = createForm.handleSubmit(async (values) => {
    submitError.value = null
    try {
      await createMaterial(
        {
          code: values.code,
          name: values.name,
          material_type_id: values.materialTypeId,
          status: values.status,
          note: values.note || null,
        },
        authStore.accessToken,
      )
      createDialogVisible.value = false
      createForm.resetForm()
      await fetchMaterials()
    } catch (err) {
      handleSubmitError(err, createForm.setErrors)
    }
  })

  const submitEdit = editForm.handleSubmit(async (values) => {
    if (!selectedMaterial.value) return
    submitError.value = null
    try {
      await updateMaterial(
        selectedMaterial.value.id,
        {
          code: values.code,
          name: values.name,
          material_type_id: values.materialTypeId,
          status: values.status,
          note: values.note || null,
        },
        authStore.accessToken,
      )
      editDialogVisible.value = false
      editForm.resetForm()
      await fetchMaterials()
    } catch (err) {
      handleSubmitError(err, editForm.setErrors)
    }
  })

  function handleSubmitError(
    err: unknown,
    setErrors: (fields: Partial<Record<'code' | 'materialTypeId', string>>) => void,
  ) {
    if (err instanceof ApiError && err.status === 409) {
      setErrors({ code: 'Mã vật tư này đã tồn tại.' })
      return
    }
    if (err instanceof ApiError && err.status === 400) {
      setErrors({ materialTypeId: 'Loại vật tư không hợp lệ.' })
      return
    }
    submitError.value = 'Lỗi hệ thống khi lưu vật tư.'
  }

  function openCreateDialog() {
    submitError.value = null
    createForm.resetForm({
      values: {
        code: '',
        name: '',
        materialTypeId: '',
        status: 'active',
        note: '',
      },
    })
    createDialogVisible.value = true
  }

  function openEditDialog(material: MaterialDomain) {
    submitError.value = null
    selectedMaterial.value = material
    editForm.resetForm({
      values: {
        code: material.code,
        name: material.name,
        materialTypeId: material.materialTypeId,
        status: material.status,
        note: material.note || '',
      },
    })
    editDialogVisible.value = true
  }

  function openDeleteDialog(material: MaterialDomain) {
    submitError.value = null
    selectedMaterial.value = material
    deleteDialogVisible.value = true
  }

  async function submitDelete() {
    if (!selectedMaterial.value) return
    isDeleting.value = true
    submitError.value = null
    try {
      await deleteMaterial(selectedMaterial.value.id, authStore.accessToken)
      deleteDialogVisible.value = false
      selectedMaterial.value = null
      await fetchMaterials()
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        submitError.value =
          'Không thể xóa vật tư đã được tham chiếu. Hãy chuyển trạng thái inactive.'
      } else {
        submitError.value = 'Lỗi hệ thống khi xóa vật tư.'
      }
    } finally {
      isDeleting.value = false
    }
  }

  return {
    materials,
    materialTypes,
    totalMaterials,
    loading,
    generalError,
    submitError,
    selectedMaterial,
    createDialogVisible,
    editDialogVisible,
    deleteDialogVisible,
    isDeleting,
    lazyParams,
    fetchMaterials,
    fetchMaterialTypesLookup,
    openCreateDialog,
    openEditDialog,
    openDeleteDialog,
    submitDelete,
    createCode,
    createCodeProps,
    createName,
    createNameProps,
    createMaterialTypeId,
    createMaterialTypeIdProps,
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
    editMaterialTypeId,
    editMaterialTypeIdProps,
    editStatus,
    editStatusProps,
    editNote,
    editNoteProps,
    editErrors: editForm.errors,
    editFormSubmitting: editForm.isSubmitting,
    submitEdit,
  }
}
