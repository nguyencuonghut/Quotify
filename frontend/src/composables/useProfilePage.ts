import { computed, onUnmounted, ref } from 'vue'
import { toTypedSchema } from '@vee-validate/zod'
import { useForm } from 'vee-validate'
import { z } from 'zod'

import { ApiError } from '@/api/http'
import {
  changeCurrentUserPassword,
  uploadCurrentUserAvatar,
} from '@/api/users.api'
import { useAuthStore } from '@/stores/auth.store'
import { getUserAvatarUrl } from '@/utils/default-avatars'

export function useProfilePage() {
  const authStore = useAuthStore()

  const currentUser = computed(() => authStore.currentUser)
  const avatarPreviewUrl = ref<string | null>(null)
  const isAvatarUploading = ref(false)
  const avatarError = ref<string | null>(null)
  const avatarSuccess = ref<string | null>(null)
  const passwordError = ref<string | null>(null)
  const passwordSuccess = ref<string | null>(null)
  const profileAvatarUrl = computed(
    () => avatarPreviewUrl.value || getUserAvatarUrl(currentUser.value),
  )
  const rolesDisplay = computed(
    () => currentUser.value?.roles?.join(', ') || 'Chưa gán vai trò',
  )
  const permissionsDisplay = computed(
    () => `${currentUser.value?.permissions?.length || 0} quyền đã được cấp`,
  )

  const passwordSchema = toTypedSchema(
    z
      .object({
        currentPassword: z.string().min(1, 'Mật khẩu hiện tại là bắt buộc.'),
        newPassword: z
          .string()
          .min(8, 'Mật khẩu mới phải có ít nhất 8 ký tự.'),
        confirmPassword: z.string().min(1, 'Xác nhận mật khẩu là bắt buộc.'),
      })
      .refine((values) => values.newPassword === values.confirmPassword, {
        message: 'Mật khẩu xác nhận chưa khớp.',
        path: ['confirmPassword'],
      }),
  )

  const passwordForm = useForm({
    initialValues: {
      currentPassword: '',
      newPassword: '',
      confirmPassword: '',
    },
    validationSchema: passwordSchema,
  })

  const [currentPassword, currentPasswordProps] =
    passwordForm.defineField('currentPassword')
  const [newPassword, newPasswordProps] =
    passwordForm.defineField('newPassword')
  const [confirmPassword, confirmPasswordProps] =
    passwordForm.defineField('confirmPassword')

  function formatDateTime(value: string | null) {
    if (!value) {
      return 'Chưa có dữ liệu'
    }

    return new Intl.DateTimeFormat('vi-VN', {
      dateStyle: 'medium',
      timeStyle: 'short',
      timeZone: import.meta.env.VITE_APP_TIMEZONE ?? 'Asia/Ho_Chi_Minh',
    }).format(new Date(value))
  }

  function clearAvatarPreview() {
    if (avatarPreviewUrl.value) {
      URL.revokeObjectURL(avatarPreviewUrl.value)
      avatarPreviewUrl.value = null
    }
  }

  async function handleAvatarUpload(event: { files: File | File[] }) {
    const file = Array.isArray(event.files) ? event.files[0] : event.files
    if (!file) return

    clearAvatarPreview()
    avatarPreviewUrl.value = URL.createObjectURL(file)
    avatarError.value = null
    avatarSuccess.value = null
    isAvatarUploading.value = true

    try {
      authStore.currentUser = await uploadCurrentUserAvatar(
        file,
        authStore.accessToken,
      )
      avatarSuccess.value = 'Đã cập nhật ảnh đại diện.'
    } catch (err) {
      clearAvatarPreview()
      avatarError.value =
        err instanceof ApiError
          ? err.message
          : 'Không thể cập nhật ảnh đại diện.'
    } finally {
      isAvatarUploading.value = false
    }
  }

  const submitPasswordChange = passwordForm.handleSubmit(async (values) => {
    passwordError.value = null
    passwordSuccess.value = null

    try {
      await changeCurrentUserPassword(
        {
          current_password: values.currentPassword,
          new_password: values.newPassword,
        },
        authStore.accessToken,
      )
      passwordForm.resetForm()
      passwordSuccess.value = 'Đã cập nhật mật khẩu.'
    } catch (err) {
      passwordError.value =
        err instanceof ApiError ? err.message : 'Không thể cập nhật mật khẩu.'
    }
  })

  onUnmounted(clearAvatarPreview)

  return {
    avatarError,
    avatarSuccess,
    confirmPassword,
    confirmPasswordProps,
    currentUser,
    currentPassword,
    currentPasswordProps,
    errors: passwordForm.errors,
    profileAvatarUrl,
    formatDateTime,
    handleAvatarUpload,
    isAvatarUploading,
    isPasswordSubmitting: passwordForm.isSubmitting,
    newPassword,
    newPasswordProps,
    passwordError,
    passwordSuccess,
    permissionsDisplay,
    rolesDisplay,
    submitPasswordChange,
  }
}
