<template>
  <AdminLayout section-label="Báo giá" title="Cấu hình quy đổi">
    <div class="quotify-settings-page">
      <div
        v-if="generalError"
        class="quotify-settings-page__general-error"
        role="alert"
      >
        <i class="pi pi-exclamation-triangle" aria-hidden="true" />
        <span>{{ generalError }}</span>
      </div>

      <div class="quotify-settings-page__grid">
        <form
          class="quotify-settings-page__panel"
          @submit.prevent="submitSettings"
        >
          <div class="quotify-settings-page__panel-header">
            <div>
              <p class="quotify-settings-page__eyebrow">Cấu hình</p>
              <h3 class="quotify-settings-page__panel-title">
                Cấu hình quy đổi
              </h3>
            </div>
            <span class="quotify-settings-page__status">
              {{ formattedImportTaxRatePercent }} · {{ formattedProcessingCost }}
            </span>
          </div>

          <div class="quotify-settings-page__form-field">
            <label
              class="quotify-settings-page__form-label required"
              for="import-tax-rate"
            >
              Thuế nhập khẩu (%)
            </label>
            <InputNumber
              id="import-tax-rate"
              v-model="importTaxRatePercent"
              v-bind="importTaxRatePercentProps"
              class="quotify-settings-page__input"
              :disabled="loadingSettings || !canUpdateSettings"
              :invalid="Boolean(settingsErrors.importTaxRatePercent)"
              locale="vi-VN"
              :max="100"
              :max-fraction-digits="2"
              :min="0"
              :min-fraction-digits="2"
              suffix=" %"
            />
            <small class="quotify-settings-page__field-error">
              {{ settingsErrors.importTaxRatePercent }}
            </small>
          </div>

          <div class="quotify-settings-page__form-field">
            <label
              class="quotify-settings-page__form-label required"
              for="processing-cost"
            >
              Chi phí làm hàng VNĐ/KG
            </label>
            <InputNumber
              id="processing-cost"
              v-model="processingCostVndPerKg"
              v-bind="processingCostVndPerKgProps"
              class="quotify-settings-page__input"
              :disabled="loadingSettings || !canUpdateSettings"
              :invalid="Boolean(settingsErrors.processingCostVndPerKg)"
              locale="vi-VN"
              :max="999999"
              :max-fraction-digits="2"
              :min="0"
              :min-fraction-digits="2"
              suffix=" VNĐ/KG"
            />
            <small class="quotify-settings-page__field-error">
              {{ settingsErrors.processingCostVndPerKg }}
            </small>
          </div>

          <div class="quotify-settings-page__meta-grid">
            <div class="quotify-settings-page__meta-item">
              <span class="quotify-settings-page__meta-label">Cập nhật lúc</span>
              <strong>{{ formattedSettingsUpdatedAt }}</strong>
            </div>
            <div class="quotify-settings-page__meta-item">
              <span class="quotify-settings-page__meta-label">Trạng thái</span>
              <strong>{{ canUpdateSettings ? 'Có quyền sửa' : 'Chỉ xem' }}</strong>
            </div>
          </div>

          <p
            v-if="submitError"
            class="quotify-settings-page__submit-error"
            role="alert"
          >
            {{ submitError }}
          </p>
          <p
            v-if="successMessage"
            class="quotify-settings-page__success-message"
            role="status"
          >
            {{ successMessage }}
          </p>

          <div class="quotify-settings-page__actions">
            <Button
              icon="pi pi-save"
              label="Lưu cấu hình"
              :disabled="loadingSettings || !canUpdateSettings"
              :loading="settingsSubmitting"
              type="submit"
            />
          </div>
        </form>

        <section class="quotify-settings-page__panel">
          <div class="quotify-settings-page__panel-header">
            <div>
              <p class="quotify-settings-page__eyebrow">Tỷ giá</p>
              <h3 class="quotify-settings-page__panel-title">
                USD bán ra hôm nay
              </h3>
            </div>
            <Button
              aria-label="Tải lại tỷ giá"
              icon="pi pi-refresh"
              :loading="loadingRate"
              rounded
              severity="secondary"
              text
              type="button"
              @click="fetchTodayRate"
            />
          </div>

          <div class="quotify-settings-page__rate-value">
            {{ formattedRate }}
          </div>

          <div class="quotify-settings-page__meta-grid">
            <div class="quotify-settings-page__meta-item">
              <span class="quotify-settings-page__meta-label">Nguồn</span>
              <strong>{{ todayRate?.source ?? 'Chưa có dữ liệu' }}</strong>
            </div>
            <div class="quotify-settings-page__meta-item">
              <span class="quotify-settings-page__meta-label">Lấy lúc</span>
              <strong>{{ formattedRateRetrievedAt }}</strong>
            </div>
          </div>

          <p
            v-if="rateError"
            class="quotify-settings-page__submit-error"
            role="alert"
          >
            {{ rateError }}
          </p>
        </section>
      </div>
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import Button from 'primevue/button'
import InputNumber from 'primevue/inputnumber'

import AdminLayout from '@/layouts/AdminLayout.vue'
import { useQuotifySettingsPage } from '@/composables/useQuotifySettingsPage'

const {
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
  settingsErrors,
  settingsSubmitting,
  formattedImportTaxRatePercent,
  formattedProcessingCost,
  formattedRate,
  formattedRateRetrievedAt,
  formattedSettingsUpdatedAt,
  bootstrap,
  fetchTodayRate,
  submitSettings,
} = useQuotifySettingsPage()

onMounted(() => {
  bootstrap()
})
</script>
