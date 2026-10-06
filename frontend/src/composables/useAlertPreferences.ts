import { computed, ref } from 'vue'

import {
  getAlertPreferences,
  updateAlertPreferences,
} from '@/api/alert-preferences.api'
import {
  ALERT_LEVEL_LABELS,
  mapAlertPreferencesToPayload,
} from '@/api/alert-preferences.mappers'
import { ApiError } from '@/api/http'
import { useAuthStore } from '@/stores/auth.store'
import { usePermissionStore } from '@/stores/permission.store'
import type {
  AlertLevel,
  AlertLevelChoice,
  AlertPreferencesDomain,
} from '@/types/alert-preferences'

function describeSaveError(error: unknown): string {
  if (error instanceof ApiError && error.status === 403) {
    return 'Chỉ quản trị viên được bật nhận mọi thông báo.'
  }
  return 'Không thể lưu tùy chọn. Vui lòng thử lại.'
}

export function useAlertPreferences() {
  const authStore = useAuthStore()
  const permissionStore = usePermissionStore()

  const isEnabled = ref(true)
  const minLevelChoice = ref<AlertLevelChoice>('default')
  const adminReceiveAll = ref(false)
  const effectiveMinLevel = ref<AlertLevel>('medium')

  const isLoaded = ref(false)
  const isLoading = ref(false)
  const isSaving = ref(false)
  const loadError = ref<string | null>(null)
  const errorMessage = ref<string | null>(null)
  const successMessage = ref<string | null>(null)

  const isAdmin = computed(() => permissionStore.hasRole('admin'))
  const defaultOptionLabel = computed(
    () =>
      `Mặc định theo vai trò (hiện là ${ALERT_LEVEL_LABELS[effectiveMinLevel.value]})`,
  )

  function apply(preferences: AlertPreferencesDomain) {
    isEnabled.value = preferences.isEnabled
    minLevelChoice.value = preferences.minLevelChoice
    adminReceiveAll.value = preferences.adminReceiveAll
    effectiveMinLevel.value = preferences.effectiveMinLevel
  }

  async function load() {
    isLoading.value = true
    loadError.value = null
    try {
      apply(await getAlertPreferences(authStore.accessToken))
      isLoaded.value = true
    } catch {
      loadError.value = 'Không thể tải tùy chọn thông báo.'
      isLoaded.value = false
    } finally {
      isLoading.value = false
    }
  }

  async function save() {
    if (isSaving.value) {
      return
    }
    isSaving.value = true
    errorMessage.value = null
    successMessage.value = null
    try {
      const saved = await updateAlertPreferences(
        mapAlertPreferencesToPayload(
          {
            isEnabled: isEnabled.value,
            minLevelChoice: minLevelChoice.value,
            adminReceiveAll: adminReceiveAll.value,
          },
          isAdmin.value,
        ),
        authStore.accessToken,
      )
      apply(saved)
      successMessage.value = 'Đã lưu tùy chọn thông báo.'
    } catch (error) {
      errorMessage.value = describeSaveError(error)
    } finally {
      isSaving.value = false
    }
  }

  return {
    isEnabled,
    minLevelChoice,
    adminReceiveAll,
    effectiveMinLevel,
    isLoaded,
    isLoading,
    isSaving,
    loadError,
    errorMessage,
    successMessage,
    isAdmin,
    defaultOptionLabel,
    load,
    save,
  }
}
