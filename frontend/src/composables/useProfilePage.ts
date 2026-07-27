import { computed } from 'vue'

import { useAuthStore } from '@/stores/auth.store'

export function useProfilePage() {
  const authStore = useAuthStore()

  const currentUser = computed(() => authStore.currentUser)
  const profileInitials = computed(() => {
    const fullName = currentUser.value?.fullName?.trim()
    if (fullName) {
      const parts = fullName.split(/\s+/).filter(Boolean)
      return parts
        .slice(0, 2)
        .map((part) => part[0]?.toUpperCase() ?? '')
        .join('')
    }

    const email = currentUser.value?.email?.trim()
    return email ? email.slice(0, 2).toUpperCase() : 'FV'
  })

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
    profileInitials,
    formatDateTime,
  }
}
