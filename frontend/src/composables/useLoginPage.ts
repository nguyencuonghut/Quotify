import { computed } from 'vue'

import { toTypedSchema } from '@vee-validate/zod'
import { useForm } from 'vee-validate'
import { z } from 'zod'

import { ApiError } from '@/api/http'
import { useAuthStore } from '@/stores/auth.store'
import type { LoginFormValues } from '@/types/auth'

const loginSchema = toTypedSchema(
  z.object({
    email: z.string().email('Nhập email hợp lệ.'),
    password: z
      .string()
      .min(8, 'Mật khẩu phải có ít nhất 8 ký tự để đúng baseline bảo mật.'),
  }),
)

export function useLoginPage(onSuccess: () => Promise<void> | void) {
  const authStore = useAuthStore()

  const { defineField, errors, handleSubmit, setErrors } =
    useForm<LoginFormValues>({
      initialValues: {
        email: '',
        password: '',
      },
      validationSchema: loginSchema,
    })

  const [email, emailProps] = defineField('email')
  const [password, passwordProps] = defineField('password')

  const submitLogin = handleSubmit(async (values) => {
    try {
      await authStore.login(values)
      await onSuccess()
    } catch (error) {
      if (
        (error instanceof ApiError && error.status === 401) ||
        error instanceof TypeError
      ) {
        setErrors({
          password:
            error instanceof TypeError
              ? 'Không thể kết nối tới dịch vụ xác thực.'
              : 'Thông tin đăng nhập không hợp lệ.',
        })
        return
      }

      throw error
    }
  })

  const isSubmitting = computed(
    () => authStore.loginPending || authStore.initializing,
  )

  return {
    email,
    emailProps,
    errors,
    isSubmitting,
    password,
    passwordProps,
    submitLogin,
  }
}
