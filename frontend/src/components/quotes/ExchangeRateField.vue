<template>
  <div class="exchange-rate-field">
    <!-- Thông báo lỗi khi fetch tỷ giá tự động thất bại -->
    <div
      v-if="fetchError && sourceMode === 'manual_fallback'"
      class="exchange-rate-field__error-banner"
      role="alert"
    >
      <i class="pi pi-exclamation-triangle" aria-hidden="true" />
      <span>{{ fetchError }}</span>
    </div>

    <div class="exchange-rate-field__grid">
      <!-- Trường nhập/hiển thị Tỷ giá -->
      <div class="exchange-rate-field__form-field">
        <label
          v-if="!hideLabels"
          class="exchange-rate-field__form-label"
          :class="{ required: isRateRequired }"
          for="exchange-rate-input"
        >
          Tỷ giá quy đổi (VNĐ/USD)
        </label>
        <div class="exchange-rate-field__input-wrapper">
          <InputNumber
            id="exchange-rate-input"
            :model-value="rate"
            class="exchange-rate-field__input"
            :disabled="disabled || isRateReadOnly || loading"
            :invalid="invalid || Boolean(error)"
            locale="en-US"
            :max="999999"
            :max-fraction-digits="2"
            :min="0"
            :min-fraction-digits="2"
            placeholder="Nhập tỷ giá..."
            @update:model-value="onRateChange"
          />
          <Button
            v-if="isToday && !disabled"
            aria-label="Lấy lại tỷ giá"
            title="Lấy lại tỷ giá"
            class="exchange-rate-field__refresh-btn"
            icon="pi pi-refresh"
            :loading="loading"
            severity="secondary"
            text
            type="button"
            @click="triggerFetchTodayRate"
          />
        </div>
        <small v-if="error" class="exchange-rate-field__field-error">
          {{ error }}
        </small>
      </div>

      <!-- Hiển thị Nguồn tỷ giá -->
      <div class="exchange-rate-field__form-field">
        <span v-if="!hideLabels" class="exchange-rate-field__form-label">Nguồn tỷ giá</span>
        <div class="exchange-rate-field__source-badge">
          {{ source || 'Chưa xác định' }}
          <span
            v-if="sourceMode === 'auto'"
            class="exchange-rate-field__status-tag exchange-rate-field__status-tag--auto"
          >
            Tự động
          </span>
          <span
            v-else
            class="exchange-rate-field__status-tag exchange-rate-field__status-tag--manual"
          >
            Nhập tay
          </span>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, onMounted } from 'vue'
import Button from 'primevue/button'
import InputNumber from 'primevue/inputnumber'

import { getUsdSellRateToday } from '@/api/exchange-rates.api'
import { useAuthStore } from '@/stores/auth.store'

interface Props {
  receivedDate: string // Định dạng YYYY-MM-DD
  rate: number | null
  source?: string | null
  sourceMode?: string | null // 'auto' | 'manual_past' | 'manual_fallback'
  manualReason: string | null
  disabled?: boolean
  invalid?: boolean
  error?: string
  hideLabels?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  disabled: false,
  invalid: false,
  error: '',
  manualReason: '',
  hideLabels: false,
})

const emit = defineEmits<{
  (e: 'update:rate', value: number | null): void
  (e: 'update:source', value: string): void
  (e: 'update:sourceMode', value: string): void
  (e: 'update:manualReason', value: string | null): void
}>()

const authStore = useAuthStore()
const loading = ref(false)
const fetchError = ref<string | null>(null)

// Tính ngày hôm nay theo timezone Asia/Ho_Chi_Minh
const getTodayString = () => {
  const appTimezone = import.meta.env.VITE_APP_TIMEZONE ?? 'Asia/Ho_Chi_Minh'
  return new Intl.DateTimeFormat('sv-SE', {
    timeZone: appTimezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date())
}

const isToday = computed(() => {
  if (!props.receivedDate) return false
  return props.receivedDate === getTodayString()
})

const isRateRequired = computed(() => {
  return props.sourceMode === 'manual_fallback' || props.sourceMode === 'manual_past'
})

const isRateReadOnly = computed(() => {
  return props.sourceMode === 'auto'
})

// Thực hiện tự động fetch tỷ giá
const triggerFetchTodayRate = async () => {
  loading.value = true
  fetchError.value = null
  try {
    const result = await getUsdSellRateToday(authStore.accessToken)
    const numericRate = Number(result.rate)
    emit('update:rate', Number.isFinite(numericRate) ? numericRate : null)
    emit('update:source', result.source)
    emit('update:sourceMode', 'auto')
    emit('update:manualReason', '')
  } catch {
    fetchError.value = 'Không thể lấy tỷ giá tự động từ Vietcombank. Vui lòng nhập tay tỷ giá.'
    emit('update:sourceMode', 'manual_fallback')
    emit('update:source', 'Không lấy được tỷ giá tự động')
  } finally {
    loading.value = false
  }
}

const handleDateChange = () => {
  if (!props.receivedDate) return

  const todayStr = getTodayString()
  
  if (props.receivedDate === todayStr) {
    // Nếu chuyển sang ngày hôm nay, và chưa ở chế độ auto hoặc manual_fallback, ta fetch tự động
    if (props.sourceMode !== 'auto' && props.sourceMode !== 'manual_fallback') {
      triggerFetchTodayRate()
    }
  } else if (props.receivedDate < todayStr) {
    // Ngày trong quá khứ
    emit('update:sourceMode', 'manual_past')
    emit('update:source', 'Ngày nhận trong quá khứ')
    // Reset lý do nhập tay cho quá khứ nếu trước đó ở chế độ fallback
    if (props.sourceMode === 'manual_fallback') {
      emit('update:manualReason', '')
    }
  }
}

watch(() => props.receivedDate, handleDateChange)

onMounted(() => {
  // Nếu ban đầu nhận ngày hiện tại mà chưa có mode gì, tự động fetch
  if (isToday.value && !props.sourceMode) {
    triggerFetchTodayRate()
  } else if (props.receivedDate && props.receivedDate < getTodayString() && !props.sourceMode) {
    emit('update:sourceMode', 'manual_past')
    emit('update:source', 'Ngày nhận trong quá khứ')
  }
})

const onRateChange = (val: number | null) => {
  emit('update:rate', val)
}
</script>
