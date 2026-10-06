<template>
  <section
    class="profile-page__panel profile-page__panel--wide"
    aria-labelledby="alert-preferences-title"
    data-testid="alert-preferences-panel"
  >
    <div class="profile-page__panel-header">
      <span class="profile-page__panel-icon pi pi-bell" aria-hidden="true" />
      <div>
        <h3 id="alert-preferences-title" class="profile-page__panel-title">
          Tùy chọn thông báo giá
        </h3>
        <p class="profile-page__panel-description">
          Chọn mức biến động tối thiểu bạn muốn nhận qua Telegram.
        </p>
      </div>
    </div>

    <p
      v-if="loadError"
      class="profile-page__error"
      role="alert"
      data-testid="alert-preferences-load-error"
    >
      {{ loadError }}
    </p>
    <div v-if="loadError" class="profile-page__telegram-actions">
      <Button
        type="button"
        icon="pi pi-refresh"
        label="Thử lại"
        :loading="isLoading"
        :disabled="isLoading"
        data-testid="alert-preferences-retry"
        @click="load"
      />
    </div>

    <form
      v-else
      class="profile-page__alert-preferences"
      data-testid="alert-preferences-form"
      @submit.prevent="save"
    >
      <div class="profile-page__alert-toggle">
        <ToggleSwitch
          v-model="isEnabled"
          input-id="alert-preferences-enabled"
          :disabled="!isLoaded || isSaving"
          data-testid="alert-preferences-enabled"
        />
        <label for="alert-preferences-enabled">
          Nhận thông báo biến động giá qua Telegram
        </label>
      </div>

      <div class="profile-page__field">
        <label for="alert-preferences-level" class="profile-page__label">
          Mức tối thiểu
        </label>
        <Select
          v-model="minLevelChoice"
          input-id="alert-preferences-level"
          :options="levelOptions"
          option-label="label"
          option-value="value"
          :disabled="!isLoaded || isSaving || !isEnabled"
          data-testid="alert-preferences-level"
        />
        <small class="profile-page__hint">
          Với thẻ giá bất thường, mức tối thiểu không áp dụng: bạn nhận khi là
          trưởng phòng hoặc là người nhập phiếu và còn bật thông báo. Tin mức
          Nhẹ nằm trong bản tin tổng hợp hằng ngày.
        </small>
      </div>

      <div v-if="isAdmin" class="profile-page__alert-toggle">
        <ToggleSwitch
          v-model="adminReceiveAll"
          input-id="alert-preferences-admin-all"
          :disabled="!isLoaded || isSaving"
          data-testid="alert-preferences-admin-all"
        />
        <label for="alert-preferences-admin-all">
          Quản trị viên: nhận thông báo của mọi vật tư
        </label>
      </div>
      <small v-if="isAdmin" class="profile-page__hint">
        Tài khoản quản trị hệ thống dùng để nhập dữ liệu hàng loạt không bao giờ
        nhận thông báo, dù bật tùy chọn này.
      </small>

      <p
        v-if="errorMessage"
        class="profile-page__error"
        role="alert"
        data-testid="alert-preferences-error"
      >
        {{ errorMessage }}
      </p>
      <p
        v-if="successMessage"
        class="profile-page__success"
        role="status"
        data-testid="alert-preferences-success"
      >
        {{ successMessage }}
      </p>

      <div class="profile-page__telegram-actions">
        <Button
          type="submit"
          icon="pi pi-save"
          label="Lưu tùy chọn"
          :loading="isSaving"
          :disabled="!isLoaded || isSaving"
          data-testid="alert-preferences-save"
        />
      </div>
    </form>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import Button from 'primevue/button'
import Select from 'primevue/select'
import ToggleSwitch from 'primevue/toggleswitch'

import { useAlertPreferences } from '@/composables/useAlertPreferences'

const {
  isEnabled,
  minLevelChoice,
  adminReceiveAll,
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
} = useAlertPreferences()

const levelOptions = computed(() => [
  { value: 'default', label: defaultOptionLabel.value },
  { value: 'light', label: 'Từ mức Nhẹ (gồm bản tin tổng hợp hằng ngày)' },
  { value: 'medium', label: 'Từ mức Trung bình' },
  { value: 'large', label: 'Chỉ mức Lớn' },
])

onMounted(() => {
  void load()
})
</script>
