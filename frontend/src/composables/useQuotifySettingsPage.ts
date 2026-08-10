import { computed, ref } from 'vue'
import { toTypedSchema } from '@vee-validate/zod'
import { useForm } from 'vee-validate'
import { z } from 'zod'

import { getUsdSellRateToday } from '@/api/exchange-rates.api'
import {
  getQuotifySettings,
  updateQuotifySettings,
} from '@/api/quotify-settings.api'
import { useAuthStore } from '@/stores/auth.store'
import { usePermissionStore } from '@/stores/permission.store'
import type { ExchangeRateDomain } from '@/types/exchange-rates'
import type { QuotifySettingsDomain } from '@/types/quotify-settings'

const appTimezone = import.meta.env.VITE_APP_TIMEZONE ?? 'Asia/Ho_Chi_Minh'

const quotifySettingsSchema = toTypedSchema(
  z.object({
    importTaxRatePercent: z
      .number({
        required_error: 'Thuế nhập khẩu là bắt buộc.',
        invalid_type_error: 'Thuế nhập khẩu phải là số hợp lệ.',
      })
      .min(0, 'Thuế nhập khẩu không được âm.')
      .max(100, 'Thuế nhập khẩu không được vượt quá 100%.'),
    processingCostVndPerKg: z
      .number({
        required_error: 'Chi phí làm hàng là bắt buộc.',
        invalid_type_error: 'Chi phí làm hàng phải là số hợp lệ.',
      })
      .min(0, 'Chi phí làm hàng không được âm.')
      .max(999999, 'Chi phí làm hàng không được quá 999.999 VNĐ/KG.'),
  }),
)

const decimalFormatter = new Intl.NumberFormat('vi-VN', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

const dateTimeFormatter = new Intl.DateTimeFormat('vi-VN', {
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  month: '2-digit',
  timeZone: appTimezone,
  year: 'numeric',
})

function toNumber(value: string | number | null | undefined): number {
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : 0
  }

  const parsed = Number(value ?? 0)
  return Number.isFinite(parsed) ? parsed : 0
}

function formatDecimal(value: string | number | null | undefined): string {
  return decimalFormatter.format(toNumber(value))
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return 'Chưa có dữ liệu'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return 'Chưa có dữ liệu'
  }

  return dateTimeFormatter.format(date)
}

export function useQuotifySettingsPage() {
  const authStore = useAuthStore()
  const permissionStore = usePermissionStore()
  const settings = ref<QuotifySettingsDomain | null>(null)
  const todayRate = ref<ExchangeRateDomain | null>(null)
  const loadingSettings = ref(false)
  const loadingRate = ref(false)
  const generalError = ref<string | null>(null)
  const rateError = ref<string | null>(null)
  const submitError = ref<string | null>(null)
  const successMessage = ref<string | null>(null)

  const canUpdateSettings = computed(() =>
    permissionStore.can('quotify_settings.update'),
  )

  const form = useForm({
    initialValues: {
      importTaxRatePercent: 0,
      processingCostVndPerKg: 200,
    },
    validationSchema: quotifySettingsSchema,
  })
  const [importTaxRatePercent, importTaxRatePercentProps] =
    form.defineField('importTaxRatePercent')
  const [processingCostVndPerKg, processingCostVndPerKgProps] =
    form.defineField('processingCostVndPerKg')

  const formattedImportTaxRatePercent = computed(() => {
    if (!settings.value) {
      return 'Chưa có dữ liệu'
    }

    return `${formatDecimal(settings.value.importTaxRatePercent)} %`
  })

  const formattedProcessingCost = computed(() => {
    if (!settings.value) {
      return 'Chưa có dữ liệu'
    }

    return `${formatDecimal(settings.value.processingCostVndPerKg)} VNĐ/KG`
  })

  const formattedRate = computed(() => {
    if (!todayRate.value) {
      return 'Chưa có dữ liệu'
    }

    return `${formatDecimal(todayRate.value.rate)} VNĐ/USD`
  })

  const formattedRateRetrievedAt = computed(() =>
    formatDateTime(todayRate.value?.retrievedAt),
  )

  const formattedSettingsUpdatedAt = computed(() =>
    formatDateTime(settings.value?.updatedAt),
  )

  async function fetchSettings() {
    loadingSettings.value = true
    generalError.value = null
    try {
      const result = await getQuotifySettings(authStore.accessToken)
      settings.value = result
      form.resetForm({
        values: {
          importTaxRatePercent: toNumber(result.importTaxRatePercent),
          processingCostVndPerKg: toNumber(result.processingCostVndPerKg),
        },
      })
    } catch {
      generalError.value = 'Không thể tải cấu hình quy đổi.'
    } finally {
      loadingSettings.value = false
    }
  }

  async function fetchTodayRate() {
    loadingRate.value = true
    rateError.value = null
    try {
      todayRate.value = await getUsdSellRateToday(authStore.accessToken)
    } catch {
      rateError.value = 'Không thể tải tỷ giá USD bán ra hôm nay.'
      todayRate.value = null
    } finally {
      loadingRate.value = false
    }
  }

  const submitSettings = form.handleSubmit(async (values) => {
    if (!canUpdateSettings.value) {
      submitError.value = 'Bạn không có quyền cập nhật cấu hình quy đổi.'
      return
    }

    submitError.value = null
    successMessage.value = null
    try {
      const result = await updateQuotifySettings(
        {
          import_tax_rate_percent: String(values.importTaxRatePercent),
          processing_cost_vnd_per_kg: String(values.processingCostVndPerKg),
        },
        authStore.accessToken,
      )
      settings.value = result
      form.resetForm({
        values: {
          importTaxRatePercent: toNumber(result.importTaxRatePercent),
          processingCostVndPerKg: toNumber(result.processingCostVndPerKg),
        },
      })
      successMessage.value = 'Đã lưu cấu hình quy đổi.'
    } catch {
      submitError.value = 'Lỗi hệ thống khi lưu cấu hình quy đổi.'
    }
  })

  async function bootstrap() {
    await Promise.all([fetchSettings(), fetchTodayRate()])
  }

  return {
    settings,
    todayRate,
    loadingSettings,
    loadingRate,
    generalError,
    rateError,
    submitError,
    successMessage,
    canUpdateSettings,
    importTaxRatePercent,
    importTaxRatePercentProps,
    processingCostVndPerKg,
    processingCostVndPerKgProps,
    settingsErrors: form.errors,
    settingsSubmitting: form.isSubmitting,
    formattedImportTaxRatePercent,
    formattedProcessingCost,
    formattedRate,
    formattedRateRetrievedAt,
    formattedSettingsUpdatedAt,
    bootstrap,
    fetchTodayRate,
    submitSettings,
  }
}
