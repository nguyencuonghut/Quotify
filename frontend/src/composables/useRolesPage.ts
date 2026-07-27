import { ref, reactive } from 'vue'
import { toTypedSchema } from '@vee-validate/zod'
import { useForm } from 'vee-validate'
import { z } from 'zod'

import { ApiError } from '@/api/http'
import {
  createRole,
  deleteRole,
  listPermissions,
  listRoles,
  updateRole,
} from '@/api/roles.api'
import { useAuthStore } from '@/stores/auth.store'
import type {
  PermissionDomain,
  RoleDomain,
  RoleListQueryParams,
} from '@/types/roles'

export function useRolesPage() {
  const authStore = useAuthStore()

  // Data State
  const roles = ref<RoleDomain[]>([])
  const totalRoles = ref(0)
  const loading = ref(false)
  const permissions = ref<PermissionDomain[]>([])
  const generalError = ref<string | null>(null)

  // Lazy Params
  const lazyParams = reactive<RoleListQueryParams>({
    limit: 10,
    offset: 0,
    search: '',
    sort_by: 'name',
    sort_order: 'asc',
  })

  // Dialog State
  const createDialogVisible = ref(false)
  const editDialogVisible = ref(false)
  const deleteDialogVisible = ref(false)
  const selectedRole = ref<RoleDomain | null>(null)
  const isDeleting = ref(false)
  const submitError = ref<string | null>(null)

  // Fetch Functions
  async function fetchRoles() {
    loading.value = true
    generalError.value = null
    try {
      const result = await listRoles(lazyParams, authStore.accessToken)
      roles.value = result.items
      totalRoles.value = result.total
    } catch {
      generalError.value = 'Không thể tải danh sách vai trò.'
    } finally {
      loading.value = false
    }
  }

  async function fetchPermissions() {
    try {
      const result = await listPermissions(authStore.accessToken)
      permissions.value = result
    } catch {
      // handled silently
    }
  }

  // Validation Schemas
  const roleSchema = toTypedSchema(
    z.object({
      name: z
        .string()
        .min(1, 'Tên vai trò là bắt buộc.')
        .max(120, 'Tên vai trò không được quá 120 ký tự.')
        .regex(
          /^[a-zA-Z0-9_-]+$/,
          'Tên vai trò chỉ chứa chữ cái, số, gạch dưới, gạch ngang.',
        ),
      description: z
        .string()
        .max(500, 'Mô tả không được quá 500 ký tự.')
        .optional()
        .nullable()
        .or(z.literal('')),
      permissions: z.array(z.string()).min(1, 'Chọn ít nhất 1 quyền.'),
    }),
  )

  // Create Form Setup
  const createForm = useForm({
    initialValues: {
      name: '',
      description: '',
      permissions: [] as string[],
    },
    validationSchema: roleSchema,
  })

  const [createName, createNameProps] = createForm.defineField('name')
  const [createDescription, createDescriptionProps] =
    createForm.defineField('description')
  const [createPermissions, createPermissionsProps] =
    createForm.defineField('permissions')

  const submitCreate = createForm.handleSubmit(async (values) => {
    submitError.value = null
    try {
      await createRole(
        {
          name: values.name,
          description: values.description || null,
          permissions: values.permissions,
        },
        authStore.accessToken,
      )
      createDialogVisible.value = false
      createForm.resetForm()
      await fetchRoles()
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        createForm.setErrors({ name: 'Tên vai trò này đã tồn tại.' })
      } else if (err instanceof ApiError && err.status === 400) {
        submitError.value =
          err.message || 'Lỗi tạo vai trò do phân quyền không hợp lệ.'
      } else {
        submitError.value = 'Lỗi hệ thống khi tạo vai trò.'
      }
    }
  })

  // Edit Form Setup
  const editForm = useForm({
    initialValues: {
      name: '',
      description: '',
      permissions: [] as string[],
    },
    validationSchema: roleSchema,
  })

  const [editName, editNameProps] = editForm.defineField('name')
  const [editDescription, editDescriptionProps] =
    editForm.defineField('description')
  const [editPermissions, editPermissionsProps] =
    editForm.defineField('permissions')

  const submitEdit = editForm.handleSubmit(async (values) => {
    if (!selectedRole.value) return
    submitError.value = null
    try {
      await updateRole(
        selectedRole.value.id,
        {
          name: values.name,
          description: values.description || null,
          permissions: values.permissions,
        },
        authStore.accessToken,
      )
      editDialogVisible.value = false
      editForm.resetForm()
      await fetchRoles()
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        editForm.setErrors({ name: 'Tên vai trò này đã tồn tại.' })
      } else if (err instanceof ApiError && err.status === 400) {
        submitError.value =
          err.message || 'Không thể cập nhật tên vai trò hệ thống.'
      } else {
        submitError.value = 'Lỗi hệ thống khi cập nhật vai trò.'
      }
    }
  })

  // Dialog Controls
  function openCreateDialog() {
    submitError.value = null
    createForm.resetForm({
      values: {
        name: '',
        description: '',
        permissions: [],
      },
    })
    createDialogVisible.value = true
  }

  function openEditDialog(role: RoleDomain) {
    submitError.value = null
    selectedRole.value = role
    editForm.resetForm({
      values: {
        name: role.name,
        description: role.description || '',
        permissions: role.permissions,
      },
    })
    editDialogVisible.value = true
  }

  function openDeleteDialog(role: RoleDomain) {
    submitError.value = null
    selectedRole.value = role
    deleteDialogVisible.value = true
  }

  async function submitDelete() {
    if (!selectedRole.value) return
    isDeleting.value = true
    submitError.value = null
    try {
      await deleteRole(selectedRole.value.id, authStore.accessToken)
      deleteDialogVisible.value = false
      selectedRole.value = null
      await fetchRoles()
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        submitError.value = 'Không thể xóa vai trò hệ thống.'
      } else {
        submitError.value = 'Lỗi hệ thống khi xóa vai trò.'
      }
    } finally {
      isDeleting.value = false
    }
  }

  return {
    roles,
    totalRoles,
    loading,
    permissions,
    lazyParams,
    generalError,
    submitError,

    // Dialog Visibility State
    createDialogVisible,
    editDialogVisible,
    deleteDialogVisible,
    selectedRole,
    isDeleting,

    // Operations
    fetchRoles,
    fetchPermissions,
    openCreateDialog,
    openEditDialog,
    openDeleteDialog,
    submitDelete,

    // Create Fields & Bound Forms
    createName,
    createNameProps,
    createDescription,
    createDescriptionProps,
    createPermissions,
    createPermissionsProps,
    createErrors: createForm.errors,
    submitCreate,
    createFormSubmitting: createForm.isSubmitting,

    // Edit Fields & Bound Forms
    editName,
    editNameProps,
    editDescription,
    editDescriptionProps,
    editPermissions,
    editPermissionsProps,
    editErrors: editForm.errors,
    submitEdit,
    editFormSubmitting: editForm.isSubmitting,
  }
}
