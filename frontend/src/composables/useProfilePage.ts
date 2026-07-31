import { computed } from 'vue'

import { useAuthStore } from '@/stores/auth.store'
import { getUserAvatarUrl } from '@/utils/default-avatars'

export function useProfilePage() {
  const authStore = useAuthStore()

  const currentUser = computed(() => authStore.currentUser)
  const profileAvatarUrl = computed(() => getUserAvatarUrl(currentUser.value))

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

  return {
    currentUser,
    profileAvatarUrl,
    formatDateTime,
  }
}
