import { computed, ref } from 'vue'
import { toTypedSchema } from '@vee-validate/zod'
import { useForm } from 'vee-validate'
import { z } from 'zod'

import { ApiError } from '@/api/http'
import {
  getPriceAlertSettings,
  updatePriceAlertSettings,
} from '@/api/price-alert-settings.api'
import { mapSettingsValuesToPayload } from '@/api/price-alert-settings.mappers'
import { useAuthStore } from '@/stores/auth.store'
import { usePermissionStore } from '@/stores/permission.store'
import type {
  PriceAlertSettingsDomain,
  PriceAlertSettingsValues,
} from '@/types/price-alert-settings'

const ORDER_MESSAGE =
  'Ngưỡng phải tăng dần: Nhẹ < Trung bình < Lớn < Bất thường.'

function percent(label: string) {
  return z
    .number({
      required_error: `${label} là bắt buộc.`,
      invalid_type_error: `${label} là bắt buộc và phải là số hợp lệ.`,
    })
    .gt(0, `${label} phải lớn hơn 0.`)
    .max(100, `${label} không được vượt quá 100%.`)
}

function whole(label: string, min: number, max: number) {
  return z
    .number({
      required_error: `${label} là bắt buộc.`,
      invalid_type_error: `${label} là bắt buộc và phải là số hợp lệ.`,
    })
    .int(`${label} phải là số nguyên.`)
    .min(min, `${label} phải từ ${min} đến ${max}.`)
    .max(max, `${label} phải từ ${min} đến ${max}.`)
}

const schema = toTypedSchema(
  z
    .object({
      isEnabled: z.boolean(),
      anomalyEnabled: z.boolean(),
      referenceWorkingDays: whole('Số ngày làm việc tham chiếu', 1, 30),
      lightFromPercent: percent('Ngưỡng Nhẹ'),
      mediumFromPercent: percent('Ngưỡng Trung bình'),
      largeOverPercent: percent('Ngưỡng Lớn'),
      anomalyPercent: z
        .number({
          required_error: 'Ngưỡng giá bất thường là bắt buộc.',
          invalid_type_error: 'Ngưỡng giá bất thường phải là số hợp lệ.',
        })
        .gt(0, 'Ngưỡng giá bất thường phải lớn hơn 0.')
        // Backend lưu tối đa năm chữ số (hai chữ số thập phân): 999,99.
        .max(999.99, 'Ngưỡng giá bất thường không được vượt quá 999,99%.'),
      anomalyLookbackDays: whole('Cửa sổ giá bất thường (ngày)', 1, 365),
      maxTriggerDelayWorkingDays: whole('Độ trễ tối đa (ngày làm việc)', 0, 30),
      staffLookbackDays: whole('Cửa sổ nhân viên (ngày)', 1, 365),
      dedupeWindowDays: whole('Cửa sổ chống lặp (ngày)', 0, 90),
      immediateCapPerScan: whole('Trần tin mỗi lần quét', 1, 500),
      digestHourLocal: whole('Giờ bản tin', 0, 23),
      referenceFallbackDays: whole('Gốc dự phòng (ngày)', 0, 365),
    })
    .refine(
      (v) =>
        v.lightFromPercent < v.mediumFromPercent &&
        v.mediumFromPercent < v.largeOverPercent &&
        v.largeOverPercent < v.anomalyPercent,
      { message: ORDER_MESSAGE, path: ['mediumFromPercent'] },
    ),
)

const FIELD_NAMES = [
  'isEnabled',
  'anomalyEnabled',
  'referenceWorkingDays',
  'lightFromPercent',
  'mediumFromPercent',
  'largeOverPercent',
  'anomalyPercent',
  'anomalyLookbackDays',
  'maxTriggerDelayWorkingDays',
  'staffLookbackDays',
  'dedupeWindowDays',
  'immediateCapPerScan',
  'digestHourLocal',
  'referenceFallbackDays',
] as const

const DEFAULTS: PriceAlertSettingsValues = {
  isEnabled: false,
  anomalyEnabled: false,
  referenceWorkingDays: 7,
  lightFromPercent: 2.5,
  mediumFromPercent: 5,
  largeOverPercent: 10,
  anomalyPercent: 30,
  anomalyLookbackDays: 30,
  maxTriggerDelayWorkingDays: 3,
  staffLookbackDays: 90,
  dedupeWindowDays: 14,
  immediateCapPerScan: 30,
  digestHourLocal: 8,
  referenceFallbackDays: 30,
}

function describeSaveError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 422) {
      return 'Cấu hình không hợp lệ. Kiểm tra thứ tự ngưỡng và phạm vi giá trị.'
    }
    if (error.status === 403) {
      return 'Bạn không có quyền sửa cấu hình thông báo giá.'
    }
  }
  return 'Không thể lưu cấu hình. Vui lòng thử lại.'
}

export function usePriceAlertSettingsPage() {
  const authStore = useAuthStore()
  const permissionStore = usePermissionStore()

  const meta = ref<Pick<
    PriceAlertSettingsDomain,
    'enabledSinceLabel' | 'updatedAtLabel'
  > | null>(null)
  const loading = ref(false)
  const generalError = ref<string | null>(null)
  const submitError = ref<string | null>(null)
  const successMessage = ref<string | null>(null)
  const isSaving = ref(false)

  const canEdit = computed(() => permissionStore.can('price_alerts.manage'))

  const form = useForm({
    initialValues: { ...DEFAULTS },
    validationSchema: schema,
  })
  const fields = Object.fromEntries(
    FIELD_NAMES.map((name) => [name, form.defineField(name)[0]]),
  ) as {
    [K in (typeof FIELD_NAMES)[number]]: ReturnType<
      typeof form.defineField<K>
    >[0]
  }

  function applyDomain(domain: PriceAlertSettingsDomain) {
    form.setValues({ ...domain.values }, false)
    form.setErrors({})
    meta.value = {
      enabledSinceLabel: domain.enabledSinceLabel,
      updatedAtLabel: domain.updatedAtLabel,
    }
  }

  async function fetchSettings() {
    loading.value = true
    generalError.value = null
    try {
      applyDomain(await getPriceAlertSettings(authStore.accessToken))
    } catch {
      generalError.value = 'Không thể tải cấu hình thông báo giá.'
    } finally {
      loading.value = false
    }
  }

  const submitSettings = form.handleSubmit(async (values) => {
    if (isSaving.value) {
      return
    }
    if (!canEdit.value) {
      submitError.value = 'Bạn không có quyền sửa cấu hình thông báo giá.'
      return
    }
    isSaving.value = true
    submitError.value = null
    successMessage.value = null
    try {
      const saved = await updatePriceAlertSettings(
        mapSettingsValuesToPayload(values as PriceAlertSettingsValues),
        authStore.accessToken,
      )
      applyDomain(saved)
      successMessage.value = 'Đã lưu cấu hình thông báo giá.'
    } catch (error) {
      submitError.value = describeSaveError(error)
    } finally {
      isSaving.value = false
    }
  })

  return {
    fields,
    errors: form.errors,
    meta,
    loading,
    generalError,
    submitError,
    successMessage,
    isSaving,
    canEdit,
    fetchSettings,
    submitSettings,
  }
}
