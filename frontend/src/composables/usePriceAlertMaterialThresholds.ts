import { computed, onScopeDispose, ref } from 'vue'
import { toTypedSchema } from '@vee-validate/zod'
import { useForm } from 'vee-validate'
import { z } from 'zod'

import { ApiError } from '@/api/http'
import {
  deleteMaterialThreshold,
  listMaterialThresholds,
  putMaterialThreshold,
} from '@/api/price-alert-settings.api'
import { useAuthStore } from '@/stores/auth.store'
import { usePermissionStore } from '@/stores/permission.store'
import type { MaterialThresholdDomain } from '@/types/price-alert-settings'

const DEFAULT_ROWS = 10
const SEARCH_DELAY_MS = 300

function percent(label: string) {
  return z
    .number({
      required_error: `${label} là bắt buộc.`,
      invalid_type_error: `${label} là bắt buộc và phải là số hợp lệ.`,
    })
    .gt(0, `${label} phải lớn hơn 0.`)
    .max(100, `${label} không được vượt quá 100%.`)
}

const schema = toTypedSchema(
  z
    .object({
      lightFromPercent: percent('Ngưỡng Nhẹ'),
      mediumFromPercent: percent('Ngưỡng Trung bình'),
      largeOverPercent: percent('Ngưỡng Lớn'),
      // Để trống nghĩa là dùng ngưỡng giá bất thường mặc định.
      anomalyPercent: z
        .number({
          invalid_type_error: 'Ngưỡng giá bất thường phải là số hợp lệ.',
        })
        .gt(0, 'Ngưỡng giá bất thường phải lớn hơn 0.')
        .max(999.99, 'Ngưỡng giá bất thường không được vượt quá 999,99%.')
        .nullable(),
    })
    .superRefine((v, ctx) => {
      if (
        !(
          v.lightFromPercent < v.mediumFromPercent &&
          v.mediumFromPercent < v.largeOverPercent
        )
      ) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: 'Ngưỡng phải tăng dần: Nhẹ < Trung bình < Lớn.',
          path: ['mediumFromPercent'],
        })
      }
      if (v.anomalyPercent !== null && v.anomalyPercent <= v.largeOverPercent) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: 'Ngưỡng giá bất thường phải lớn hơn ngưỡng Lớn.',
          path: ['anomalyPercent'],
        })
      }
    }),
)

function round2(value: number): number {
  return Math.round(value * 100) / 100
}

function describeSaveError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 404) {
      return 'Không tìm thấy vật tư này.'
    }
    if (error.status === 422) {
      return 'Ngưỡng không hợp lệ. Kiểm tra thứ tự và phạm vi giá trị.'
    }
    if (error.status === 403) {
      return 'Bạn không có quyền sửa ngưỡng thông báo giá.'
    }
  }
  return 'Không thể lưu ngưỡng. Vui lòng thử lại.'
}

export function usePriceAlertMaterialThresholds() {
  const authStore = useAuthStore()
  const permissionStore = usePermissionStore()

  const materials = ref<MaterialThresholdDomain[]>([])
  const total = ref(0)
  const loading = ref(false)
  const generalError = ref<string | null>(null)
  const rows = ref(DEFAULT_ROWS)
  const first = ref(0)
  const rowsPerPageOptions = [10, 20, 30, 50]
  const search = ref('')

  const dialogVisible = ref(false)
  const target = ref<MaterialThresholdDomain | null>(null)
  const isBusy = ref(false)
  const errorMessage = ref<string | null>(null)
  const successMessage = ref<string | null>(null)

  const canEdit = computed(() => permissionStore.can('price_alerts.manage'))

  const form = useForm({
    initialValues: {
      lightFromPercent: 2.5,
      mediumFromPercent: 5,
      largeOverPercent: 10,
      anomalyPercent: null as number | null,
    },
    validationSchema: schema,
  })
  const fields = {
    lightFromPercent: form.defineField('lightFromPercent')[0],
    mediumFromPercent: form.defineField('mediumFromPercent')[0],
    largeOverPercent: form.defineField('largeOverPercent')[0],
    anomalyPercent: form.defineField('anomalyPercent')[0],
  }

  let requestSeq = 0
  let searchTimer: ReturnType<typeof setTimeout> | null = null

  async function fetchMaterials() {
    const seq = ++requestSeq
    loading.value = true
    generalError.value = null
    try {
      const keyword = search.value.trim()
      const result = await listMaterialThresholds(
        {
          limit: rows.value,
          offset: first.value,
          ...(keyword ? { search: keyword } : {}),
        },
        authStore.accessToken,
      )
      if (seq !== requestSeq) {
        return
      }
      materials.value = result.items
      total.value = result.total
    } catch {
      if (seq !== requestSeq) {
        return
      }
      materials.value = []
      total.value = 0
      generalError.value = 'Không thể tải danh sách ngưỡng theo vật tư.'
    } finally {
      if (seq === requestSeq) {
        loading.value = false
      }
    }
  }

  async function onPageChange(event: { first: number; rows: number }) {
    first.value = event.first
    rows.value = event.rows
    await fetchMaterials()
  }

  function onSearchInput() {
    if (searchTimer) {
      clearTimeout(searchTimer)
    }
    searchTimer = setTimeout(() => {
      searchTimer = null
      first.value = 0
      void fetchMaterials()
    }, SEARCH_DELAY_MS)
  }

  // Rời trang trong lúc chờ debounce thì bỏ yêu cầu tìm kiếm đang hẹn.
  onScopeDispose(() => {
    if (searchTimer) {
      clearTimeout(searchTimer)
      searchTimer = null
    }
  })

  function openEdit(item: MaterialThresholdDomain) {
    target.value = item
    errorMessage.value = null
    successMessage.value = null
    const base = item.override ?? item.effective
    form.setValues(
      {
        lightFromPercent: base.light,
        mediumFromPercent: base.medium,
        largeOverPercent: base.large,
        anomalyPercent: item.override?.anomaly ?? null,
      },
      false,
    )
    form.setErrors({})
    dialogVisible.value = true
  }

  function closeDialog() {
    if (isBusy.value) {
      return
    }
    dialogVisible.value = false
    target.value = null
  }

  const saveOverride = form.handleSubmit(async (values) => {
    const current = target.value
    if (isBusy.value || !current) {
      return
    }
    if (!canEdit.value) {
      errorMessage.value = 'Bạn không có quyền sửa ngưỡng thông báo giá.'
      return
    }
    isBusy.value = true
    errorMessage.value = null
    successMessage.value = null
    let saved = false
    try {
      await putMaterialThreshold(
        current,
        {
          light_from_percent: round2(values.lightFromPercent),
          medium_from_percent: round2(values.mediumFromPercent),
          large_over_percent: round2(values.largeOverPercent),
          anomaly_percent:
            values.anomalyPercent === null
              ? null
              : round2(values.anomalyPercent),
        },
        authStore.accessToken,
      )
      successMessage.value = `Đã lưu ngưỡng riêng cho ${current.name}.`
      saved = true
    } catch (error) {
      errorMessage.value = describeSaveError(error)
    } finally {
      isBusy.value = false
    }
    if (saved) {
      closeDialog()
      await fetchMaterials()
    }
  })

  async function resetToDefault() {
    const current = target.value
    if (isBusy.value || !current) {
      return
    }
    if (!canEdit.value) {
      errorMessage.value = 'Bạn không có quyền sửa ngưỡng thông báo giá.'
      return
    }
    isBusy.value = true
    errorMessage.value = null
    successMessage.value = null
    let done = false
    try {
      await deleteMaterialThreshold(current.materialId, authStore.accessToken)
      successMessage.value = `Đã đưa ${current.name} về ngưỡng mặc định.`
      done = true
    } catch (error) {
      errorMessage.value = describeSaveError(error)
    } finally {
      isBusy.value = false
    }
    if (done) {
      closeDialog()
      await fetchMaterials()
    }
  }

  return {
    materials,
    total,
    loading,
    generalError,
    rows,
    first,
    rowsPerPageOptions,
    search,
    dialogVisible,
    target,
    isBusy,
    errorMessage,
    successMessage,
    canEdit,
    fields,
    errors: form.errors,
    fetchMaterials,
    onPageChange,
    onSearchInput,
    openEdit,
    closeDialog,
    saveOverride,
    resetToDefault,
  }
}
