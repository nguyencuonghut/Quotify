import { ref, reactive, onUnmounted } from 'vue'
import { toTypedSchema } from '@vee-validate/zod'
import { useForm } from 'vee-validate'
import { z } from 'zod'

import { ApiError } from '@/api/http'
import { listRolesLookup } from '@/api/roles.api'
import {
  createUser,
  deleteUser,
  listUsers,
  updateUser,
  uploadUserAvatar,
} from '@/api/users.api'
import {
  importUsers,
  listImportJobs,
  getImportJob,
  exportUsers,
  listExportJobs,
  getExportJob,
} from '@/api/jobs.api'
import { useAuthStore } from '@/stores/auth.store'
import type { RoleDomain } from '@/types/roles'
import type { UserDomain, UserListQueryParams } from '@/types/users'
import type { ImportJobDomain, ExportJobDomain } from '@/types/jobs'

export function useUsersPage() {
  const authStore = useAuthStore()

  // Data State
  const users = ref<UserDomain[]>([])
  const totalUsers = ref(0)
  const loading = ref(false)
  const roles = ref<RoleDomain[]>([])
  const generalError = ref<string | null>(null)

  // Lazy Params
  const lazyParams = reactive<UserListQueryParams>({
    limit: 10,
    offset: 0,
    search: '',
    status_filter: '',
    sort_by: 'created_at',
    sort_order: 'desc',
  })

  // Dialog State
  const createDialogVisible = ref(false)
  const editDialogVisible = ref(false)
  const deleteDialogVisible = ref(false)
  const selectedUser = ref<UserDomain | null>(null)
  const isDeleting = ref(false)
  const submitError = ref<string | null>(null)

  // Fetch Functions
  async function fetchUsers() {
    loading.value = true
    generalError.value = null
    try {
      const result = await listUsers(lazyParams, authStore.accessToken)
      users.value = result.items
      totalUsers.value = result.total
    } catch {
      generalError.value = 'Không thể tải danh sách tài khoản.'
    } finally {
      loading.value = false
    }
  }

  async function fetchRoles() {
    try {
      const result = await listRolesLookup(authStore.accessToken)
      roles.value = result
    } catch {
      // ignore or handle silently
    }
  }

  // Create Form Setup
  const createSchema = toTypedSchema(
    z.object({
      email: z
        .string()
        .email('Nhập email hợp lệ.')
        .min(1, 'Email là bắt buộc.'),
      password: z
        .string()
        .min(8, 'Mật khẩu phải có ít nhất 8 ký tự để đúng baseline bảo mật.'),
      status: z.enum(['active', 'inactive', 'locked']),
      roleNames: z.array(z.string()).min(1, 'Chọn ít nhất 1 vai trò.'),
      fullName: z.string().min(1, 'Họ và tên là bắt buộc.'),
      avatarUrl: z.string().optional().or(z.literal('')),
    }),
  )

  const createForm = useForm({
    initialValues: {
      email: '',
      password: '',
      status: 'active',
      roleNames: [] as string[],
      fullName: '',
      avatarUrl: '',
    },
    validationSchema: createSchema,
  })

  const [createEmail, createEmailProps] = createForm.defineField('email')
  const [createPassword, createPasswordProps] =
    createForm.defineField('password')
  const [createStatus, createStatusProps] = createForm.defineField('status')
  const [createRoleNames, createRoleNamesProps] =
    createForm.defineField('roleNames')
  const [createFullName, createFullNameProps] =
    createForm.defineField('fullName')
  const [createAvatarUrl] = createForm.defineField('avatarUrl')
  const createAvatarError = ref<string | null>(null)
  const isCreateAvatarUploading = ref(false)

  const submitCreate = createForm.handleSubmit(async (values) => {
    submitError.value = null
    try {
      await createUser(
        {
          email: values.email,
          password: values.password,
          status: values.status,
          role_names: values.roleNames,
          full_name: values.fullName,
          avatar_url: values.avatarUrl || undefined,
        },
        authStore.accessToken,
      )
      createDialogVisible.value = false
      createForm.resetForm()
      await fetchUsers()
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        createForm.setErrors({ email: 'Email này đã tồn tại trên hệ thống.' })
      } else {
        submitError.value = 'Lỗi hệ thống khi tạo tài khoản.'
      }
    }
  })

  // Edit Form Setup
  const editSchema = toTypedSchema(
    z.object({
      email: z
        .string()
        .email('Nhập email hợp lệ.')
        .min(1, 'Email là bắt buộc.'),
      password: z
        .string()
        .min(8, 'Mật khẩu phải có ít nhất 8 ký tự để đúng baseline bảo mật.')
        .optional()
        .or(z.literal('')),
      status: z.enum(['active', 'inactive', 'locked']),
      roleNames: z.array(z.string()).min(1, 'Chọn ít nhất 1 vai trò.'),
      fullName: z.string().min(1, 'Họ và tên là bắt buộc.'),
      avatarUrl: z.string().optional().or(z.literal('')),
    }),
  )

  const editForm = useForm({
    initialValues: {
      email: '',
      password: '',
      status: 'active',
      roleNames: [] as string[],
      fullName: '',
      avatarUrl: '',
    },
    validationSchema: editSchema,
  })

  const [editEmail, editEmailProps] = editForm.defineField('email')
  const [editPassword, editPasswordProps] = editForm.defineField('password')
  const [editStatus, editStatusProps] = editForm.defineField('status')
  const [editRoleNames, editRoleNamesProps] = editForm.defineField('roleNames')
  const [editFullName, editFullNameProps] = editForm.defineField('fullName')
  const [editAvatarUrl] = editForm.defineField('avatarUrl')
  const editAvatarError = ref<string | null>(null)
  const isEditAvatarUploading = ref(false)

  const submitEdit = editForm.handleSubmit(async (values) => {
    if (!selectedUser.value) return
    submitError.value = null
    try {
      const updatedUser = await updateUser(
        selectedUser.value.id,
        {
          email: values.email,
          status: values.status,
          password: values.password || undefined,
          role_names: values.roleNames,
          full_name: values.fullName,
          avatar_url: values.avatarUrl || undefined,
        },
        authStore.accessToken,
      )

      if (authStore.currentUser?.id === updatedUser.id) {
        await authStore.fetchCurrentUser()
      }

      editDialogVisible.value = false
      editForm.resetForm()
      await fetchUsers()
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        editForm.setErrors({ email: 'Email này đã tồn tại trên hệ thống.' })
      } else {
        submitError.value = 'Lỗi hệ thống khi cập nhật tài khoản.'
      }
    }
  })

  // Dialog Open/Close Helpers
  function openCreateDialog() {
    submitError.value = null
    createAvatarError.value = null
    createForm.resetForm({
      values: {
        email: '',
        password: '',
        status: 'active',
        roleNames: [],
        fullName: '',
        avatarUrl: '',
      },
    })
    createDialogVisible.value = true
  }

  function openEditDialog(user: UserDomain) {
    submitError.value = null
    editAvatarError.value = null
    selectedUser.value = user
    editForm.resetForm({
      values: {
        email: user.email,
        password: '',
        status: user.status as 'active' | 'inactive' | 'locked',
        roleNames: user.roles,
        fullName: user.fullName || '',
        avatarUrl: user.avatarUrl || '',
      },
    })
    editDialogVisible.value = true
  }

  function openDeleteDialog(user: UserDomain) {
    submitError.value = null
    selectedUser.value = user
    deleteDialogVisible.value = true
  }

  async function uploadAvatarImage(
    file: File,
    mode: 'create' | 'edit',
  ): Promise<void> {
    const errorRef = mode === 'create' ? createAvatarError : editAvatarError
    const uploadingRef =
      mode === 'create' ? isCreateAvatarUploading : isEditAvatarUploading
    const avatarRef = mode === 'create' ? createAvatarUrl : editAvatarUrl

    uploadingRef.value = true
    errorRef.value = null

    try {
      const avatarUrl = await uploadUserAvatar(file, authStore.accessToken)
      avatarRef.value = avatarUrl
    } catch (err) {
      const apiErr = err as { message?: string }
      errorRef.value =
        apiErr?.message || 'Không thể tải ảnh đại diện lên hệ thống.'
    } finally {
      uploadingRef.value = false
    }
  }

  async function handleCreateAvatarUpload(event: { files: File | File[] }) {
    const file = Array.isArray(event.files) ? event.files[0] : event.files
    if (!file) return
    await uploadAvatarImage(file, 'create')
  }

  async function handleEditAvatarUpload(event: { files: File | File[] }) {
    const file = Array.isArray(event.files) ? event.files[0] : event.files
    if (!file) return
    await uploadAvatarImage(file, 'edit')
  }

  function clearCreateAvatar() {
    createAvatarUrl.value = ''
    createAvatarError.value = null
  }

  function clearEditAvatar() {
    editAvatarUrl.value = ''
    editAvatarError.value = null
  }

  async function submitDelete() {
    if (!selectedUser.value) return
    isDeleting.value = true
    submitError.value = null
    try {
      await deleteUser(selectedUser.value.id, authStore.accessToken)
      deleteDialogVisible.value = false
      selectedUser.value = null
      await fetchUsers()
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        submitError.value = 'Bạn không thể tự xóa tài khoản của chính mình.'
      } else {
        submitError.value = 'Lỗi hệ thống khi xóa tài khoản.'
      }
    } finally {
      isDeleting.value = false
    }
  }

  // Import/Export States
  const importDialogVisible = ref(false)
  const exportDialogVisible = ref(false)
  const importJobs = ref<ImportJobDomain[]>([])
  const exportJobs = ref<ExportJobDomain[]>([])
  const loadingImportJobs = ref(false)
  const loadingExportJobs = ref(false)
  const totalImportJobs = ref(0)
  const totalExportJobs = ref(0)

  const importJobsParams = reactive({
    limit: 5,
    offset: 0,
  })

  const exportJobsParams = reactive({
    limit: 5,
    offset: 0,
  })

  const pollIntervalMap = new Map<string, ReturnType<typeof setInterval>>()

  function pollImportJob(jobId: string) {
    if (pollIntervalMap.has(jobId)) return

    const interval = setInterval(async () => {
      try {
        const updatedJob = await getImportJob(jobId, authStore.accessToken)
        const idx = importJobs.value.findIndex((j) => j.id === jobId)
        if (idx !== -1) {
          importJobs.value[idx] = updatedJob
        }
        if (
          updatedJob.status === 'completed' ||
          updatedJob.status === 'failed'
        ) {
          clearInterval(interval)
          pollIntervalMap.delete(jobId)
          await fetchUsers()
        }
      } catch {
        clearInterval(interval)
        pollIntervalMap.delete(jobId)
      }
    }, 2000)

    pollIntervalMap.set(jobId, interval)
  }

  function pollExportJob(jobId: string) {
    if (pollIntervalMap.has(jobId)) return

    const interval = setInterval(async () => {
      try {
        const updatedJob = await getExportJob(jobId, authStore.accessToken)
        const idx = exportJobs.value.findIndex((j) => j.id === jobId)
        if (idx !== -1) {
          exportJobs.value[idx] = updatedJob
        }
        if (
          updatedJob.status === 'completed' ||
          updatedJob.status === 'failed'
        ) {
          clearInterval(interval)
          pollIntervalMap.delete(jobId)
        }
      } catch {
        clearInterval(interval)
        pollIntervalMap.delete(jobId)
      }
    }, 2000)

    pollIntervalMap.set(jobId, interval)
  }

  async function fetchImportJobs() {
    loadingImportJobs.value = true
    try {
      const res = await listImportJobs(importJobsParams, authStore.accessToken)
      importJobs.value = res.items
      totalImportJobs.value = res.total

      res.items.forEach((j) => {
        if (j.status === 'pending' || j.status === 'processing') {
          pollImportJob(j.id)
        }
      })
    } catch {
      // ignore
    } finally {
      loadingImportJobs.value = false
    }
  }

  async function fetchExportJobs() {
    loadingExportJobs.value = true
    try {
      const res = await listExportJobs(exportJobsParams, authStore.accessToken)
      exportJobs.value = res.items
      totalExportJobs.value = res.total

      res.items.forEach((j) => {
        if (j.status === 'pending' || j.status === 'processing') {
          pollExportJob(j.id)
        }
      })
    } catch {
      // ignore
    } finally {
      loadingExportJobs.value = false
    }
  }

  async function handleImportUpload(event: { files: File | File[] }) {
    const file = Array.isArray(event.files) ? event.files[0] : event.files
    if (!file) return
    try {
      const job = await importUsers(file, authStore.accessToken)
      await fetchImportJobs()
      pollImportJob(job.id)
    } catch {
      generalError.value = 'Lỗi hệ thống khi tải lên file nhập tài khoản.'
    }
  }

  async function handleExportTrigger() {
    try {
      const job = await exportUsers(
        {
          search: lazyParams.search || undefined,
          status: lazyParams.status_filter || undefined,
        },
        authStore.accessToken,
      )
      await fetchExportJobs()
      pollExportJob(job.id)
    } catch {
      generalError.value = 'Lỗi hệ thống khi khởi chạy xuất tài khoản.'
    }
  }

  onUnmounted(() => {
    for (const interval of pollIntervalMap.values()) {
      clearInterval(interval)
    }
    pollIntervalMap.clear()
  })

  return {
    users,
    totalUsers,
    loading,
    roles,
    lazyParams,
    generalError,
    submitError,

    // Dialog State
    createDialogVisible,
    editDialogVisible,
    deleteDialogVisible,
    selectedUser,
    isDeleting,

    // Fetch Methods
    fetchUsers,
    fetchRoles,

    // Dialog Actions
    openCreateDialog,
    openEditDialog,
    openDeleteDialog,
    submitDelete,

    // Create Form Fields & Submit
    createEmail,
    createEmailProps,
    createPassword,
    createPasswordProps,
    createStatus,
    createStatusProps,
    createRoleNames,
    createRoleNamesProps,
    createFullName,
    createFullNameProps,
    createAvatarUrl,
    createErrors: createForm.errors,
    createAvatarError,
    isCreateAvatarUploading,
    handleCreateAvatarUpload,
    clearCreateAvatar,
    submitCreate,
    createFormSubmitting: createForm.isSubmitting,

    // Edit Form Fields & Submit
    editEmail,
    editEmailProps,
    editPassword,
    editPasswordProps,
    editStatus,
    editStatusProps,
    editRoleNames,
    editRoleNamesProps,
    editFullName,
    editFullNameProps,
    editAvatarUrl,
    editErrors: editForm.errors,
    editAvatarError,
    isEditAvatarUploading,
    handleEditAvatarUpload,
    clearEditAvatar,
    submitEdit,
    editFormSubmitting: editForm.isSubmitting,

    // Import/Export integration
    importDialogVisible,
    exportDialogVisible,
    importJobs,
    exportJobs,
    loadingImportJobs,
    loadingExportJobs,
    totalImportJobs,
    totalExportJobs,
    importJobsParams,
    exportJobsParams,
    fetchImportJobs,
    fetchExportJobs,
    handleImportUpload,
    handleExportTrigger,
  }
}
