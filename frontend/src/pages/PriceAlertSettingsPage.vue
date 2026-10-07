<template>
  <AdminLayout section-label="Hệ thống" title="Thông báo giá">
    <div class="price-alert-settings-page">
      <div
        v-if="generalError"
        class="price-alert-settings-page__general-error"
        role="alert"
      >
        <i class="pi pi-exclamation-triangle" aria-hidden="true" />
        <span>{{ generalError }}</span>
        <Button
          label="Thử lại"
          icon="pi pi-refresh"
          size="small"
          severity="secondary"
          outlined
          data-testid="settings-retry"
          @click="fetchSettings"
        />
      </div>

      <form
        v-if="!generalError"
        class="price-alert-settings-page__form"
        data-testid="settings-form"
        @submit.prevent="submitSettings"
      >
        <section class="price-alert-settings-page__panel">
          <h3 class="price-alert-settings-page__panel-title">Bật hoặc tắt</h3>

          <div class="price-alert-settings-page__toggle">
            <ToggleSwitch
              v-model="fields.isEnabled.value"
              input-id="price-alert-enabled"
              :disabled="loading || !canEdit"
              data-testid="toggle-enabled"
            />
            <label for="price-alert-enabled">
              Gửi thông báo biến động giá qua Telegram
            </label>
          </div>
          <p class="price-alert-settings-page__hint">
            Mỗi lần bật lại, hệ thống bắt đầu quét từ thời điểm bật: phiếu đã
            chốt trước đó không sinh thông báo.
            <strong v-if="meta?.enabledSinceLabel">
              Bật gần nhất lúc {{ meta.enabledSinceLabel }}.
            </strong>
          </p>

          <div class="price-alert-settings-page__toggle">
            <ToggleSwitch
              v-model="fields.anomalyEnabled.value"
              input-id="price-alert-anomaly-enabled"
              :disabled="loading || !canEdit"
              data-testid="toggle-anomaly"
            />
            <label for="price-alert-anomaly-enabled">
              Gửi thẻ giá bất thường (có nút Giá đúng, Nhập sai)
            </label>
          </div>
        </section>

        <section class="price-alert-settings-page__panel">
          <h3 class="price-alert-settings-page__panel-title">
            Ngưỡng mặc định
          </h3>
          <p class="price-alert-settings-page__hint">
            Áp dụng cho mọi vật tư chưa có ngưỡng riêng. Phải tăng dần: Nhẹ &lt;
            Trung bình &lt; Lớn &lt; Bất thường.
          </p>
          <div class="price-alert-settings-page__grid">
            <div
              v-for="field in thresholdFields"
              :key="field.name"
              class="price-alert-settings-page__field"
            >
              <label
                class="price-alert-settings-page__label required"
                :for="`setting-${field.name}`"
              >
                {{ field.label }}
              </label>
              <InputNumber
                v-model="fields[field.name].value"
                :input-id="`setting-${field.name}`"
                :disabled="loading || !canEdit"
                :invalid="Boolean(errors[field.name])"
                locale="vi-VN"
                :min="0"
                :max="field.name === 'anomalyPercent' ? 999.99 : 100"
                :min-fraction-digits="2"
                :max-fraction-digits="2"
                suffix=" %"
              />
              <small class="price-alert-settings-page__field-error">
                {{ errors[field.name] }}
              </small>
            </div>
          </div>
        </section>

        <section class="price-alert-settings-page__panel">
          <h3 class="price-alert-settings-page__panel-title">Tham số</h3>
          <div
            class="price-alert-settings-page__grid price-alert-settings-page__grid--params"
          >
            <div
              v-for="field in parameterFields"
              :key="field.name"
              class="price-alert-settings-page__field"
            >
              <label
                class="price-alert-settings-page__label required"
                :for="`setting-${field.name}`"
              >
                {{ field.label }}
              </label>
              <InputNumber
                v-model="fields[field.name].value"
                :input-id="`setting-${field.name}`"
                :disabled="loading || !canEdit"
                :invalid="Boolean(errors[field.name])"
                locale="vi-VN"
                :use-grouping="false"
                :min="field.min"
                :max="field.max"
              />
              <small class="price-alert-settings-page__hint">
                {{ field.hint }}
              </small>
              <small class="price-alert-settings-page__field-error">
                {{ errors[field.name] }}
              </small>
            </div>
          </div>
        </section>

        <div
          v-if="successMessage"
          class="price-alert-settings-page__notice"
          role="status"
          data-testid="settings-success"
        >
          {{ successMessage }}
        </div>
        <div
          v-if="submitError"
          class="price-alert-settings-page__general-error"
          role="alert"
          data-testid="settings-error"
        >
          <i class="pi pi-exclamation-triangle" aria-hidden="true" />
          <span>{{ submitError }}</span>
        </div>

        <div class="price-alert-settings-page__actions">
          <Button
            type="submit"
            label="Lưu cấu hình"
            icon="pi pi-save"
            :disabled="loading || isSaving || !canEdit"
            :title="canEdit ? '' : 'Bạn không có quyền sửa cấu hình này.'"
            data-testid="settings-save"
          />
          <small
            v-if="meta?.updatedAtLabel"
            class="price-alert-settings-page__hint"
          >
            Cập nhật lần cuối {{ meta.updatedAtLabel }}
          </small>
        </div>
      </form>

      <section class="price-alert-settings-page__panel">
        <h3 class="price-alert-settings-page__panel-title">
          Ngưỡng theo vật tư
        </h3>
        <p class="price-alert-settings-page__hint">
          Vật tư biến động mạnh có thể dùng ngưỡng riêng. Ô nhạt là giá trị mặc
          định đang áp dụng.
        </p>
        <InputText
          v-model="search"
          class="price-alert-settings-page__search"
          placeholder="Tìm theo tên hoặc mã vật tư"
          aria-label="Tìm vật tư"
          data-testid="material-search"
          @input="onSearchInput"
        />

        <div
          v-if="materialSuccess"
          class="price-alert-settings-page__notice"
          role="status"
          data-testid="material-success"
        >
          {{ materialSuccess }}
        </div>
        <div
          v-if="materialsError"
          class="price-alert-settings-page__general-error"
          role="alert"
        >
          <i class="pi pi-exclamation-triangle" aria-hidden="true" />
          <span>{{ materialsError }}</span>
        </div>

        <div
          v-if="!materialsError"
          class="price-alert-settings-page__table-wrapper"
        >
          <DataTable
            :first="first"
            :loading="materialsLoading"
            :rows="rows"
            :rows-per-page-options="rowsPerPageOptions"
            :total-records="total"
            :value="materials"
            current-page-report-template="Hiển thị từ {first} đến {last} trên tổng số {totalRecords} dòng"
            data-key="materialId"
            lazy
            paginator
            paginator-template="FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink CurrentPageReport RowsPerPageDropdown"
            responsive-layout="scroll"
            @page="onPageChange"
          >
            <template #empty>
              <div class="price-alert-settings-page__empty-state">
                Không có vật tư phù hợp.
              </div>
            </template>

            <Column header="Vật tư">
              <template #body="{ data }">
                <div class="price-alert-settings-page__cell">
                  <strong>{{ data.name }}</strong>
                  <small>{{ data.code }}</small>
                </div>
              </template>
            </Column>
            <Column header="Nhẹ từ">
              <template #body="{ data }">
                <span :class="valueClass(data.hasOverride)">
                  {{ data.lightLabel }}
                </span>
              </template>
            </Column>
            <Column header="Trung bình từ">
              <template #body="{ data }">
                <span :class="valueClass(data.hasOverride)">
                  {{ data.mediumLabel }}
                </span>
              </template>
            </Column>
            <Column header="Lớn trên">
              <template #body="{ data }">
                <span :class="valueClass(data.hasOverride)">
                  {{ data.largeLabel }}
                </span>
              </template>
            </Column>
            <Column header="Bất thường từ">
              <template #body="{ data }">
                <span :class="valueClass(!data.anomalyIsDefault)">
                  {{ data.anomalyLabel }}
                </span>
              </template>
            </Column>
            <Column header="Nguồn">
              <template #body="{ data }">
                <Tag
                  :severity="data.hasOverride ? 'info' : 'secondary'"
                  :value="data.hasOverride ? 'Ngưỡng riêng' : 'Mặc định'"
                />
              </template>
            </Column>
            <Column header="Theo dõi">
              <template #body="{ data }">
                <Tag
                  v-if="data.freshness"
                  :severity="data.freshness.isWatched ? 'success' : 'secondary'"
                  :value="data.watchLabel"
                />
                <span v-else class="price-alert-settings-page__muted">
                  {{ data.watchLabel }}
                </span>
              </template>
            </Column>
            <Column header="Chu kỳ (ngày)">
              <template #body="{ data }">
                <span :class="valueClass(Boolean(data.freshness?.isWatched))">
                  {{ data.intervalLabel }}
                </span>
              </template>
            </Column>
            <Column
              header="Thao tác"
              class="price-alert-settings-page__actions-column"
            >
              <template #body="{ data }">
                <Button
                  :aria-label="`Sửa ngưỡng ${data.name}`"
                  :title="
                    canEdit
                      ? 'Sửa ngưỡng riêng'
                      : 'Bạn không có quyền sửa cấu hình này.'
                  "
                  icon="pi pi-pencil"
                  rounded
                  severity="secondary"
                  text
                  :disabled="!canEdit"
                  data-testid="material-edit"
                  @click="openEdit(data)"
                />
                <Button
                  :aria-label="`Theo dõi giá ${data.name}`"
                  :title="
                    canEdit
                      ? 'Theo dõi độ mới của giá'
                      : 'Bạn không có quyền sửa cấu hình này.'
                  "
                  icon="pi pi-eye"
                  rounded
                  severity="secondary"
                  text
                  :disabled="!canEdit"
                  data-testid="material-watch"
                  @click="openWatchEdit(data)"
                />
              </template>
            </Column>
          </DataTable>
        </div>
      </section>

      <Dialog
        v-model:visible="dialogVisible"
        :header="target ? `Ngưỡng riêng: ${target.name}` : 'Ngưỡng riêng'"
        modal
        :closable="!isBusy"
        :close-on-escape="!isBusy"
        class="price-alert-settings-page__dialog"
        @hide="closeDialog"
      >
        <div class="price-alert-settings-page__dialog-grid">
          <div
            v-for="field in materialFields"
            :key="field.name"
            class="price-alert-settings-page__field"
          >
            <label
              :class="[
                'price-alert-settings-page__label',
                { required: field.required },
              ]"
              :for="`material-${field.name}`"
            >
              {{ field.label }}
            </label>
            <InputNumber
              v-model="materialFormFields[field.name].value"
              :input-id="`material-${field.name}`"
              :disabled="isBusy"
              :invalid="Boolean(materialErrors[field.name])"
              locale="vi-VN"
              :min="0"
              :max="999.99"
              :min-fraction-digits="2"
              :max-fraction-digits="2"
              :placeholder="field.placeholder"
              suffix=" %"
            />
            <small class="price-alert-settings-page__field-error">
              {{ materialErrors[field.name] }}
            </small>
          </div>
        </div>
        <p class="price-alert-settings-page__hint">
          Để trống ô Bất thường để dùng ngưỡng giá bất thường mặc định.
        </p>
        <div
          v-if="materialDialogError"
          class="price-alert-settings-page__general-error"
          role="alert"
          data-testid="material-error"
        >
          <i class="pi pi-exclamation-triangle" aria-hidden="true" />
          <span>{{ materialDialogError }}</span>
        </div>
        <template #footer>
          <Button
            v-if="target?.hasOverride"
            label="Dùng mặc định"
            severity="secondary"
            outlined
            :disabled="isBusy"
            data-testid="material-reset"
            @click="resetToDefault"
          />
          <Button
            label="Hủy"
            severity="secondary"
            outlined
            :disabled="isBusy"
            @click="closeDialog"
          />
          <Button
            label="Lưu ngưỡng"
            :disabled="isBusy"
            data-testid="material-save"
            @click="saveOverride"
          />
        </template>
      </Dialog>

      <Dialog
        v-model:visible="watchDialogVisible"
        :header="watchTarget ? `Theo dõi giá: ${watchTarget.name}` : 'Theo dõi giá'"
        modal
        :closable="!watchBusy"
        :close-on-escape="!watchBusy"
        class="price-alert-settings-page__dialog"
        @hide="closeWatchDialog"
      >
        <div class="price-alert-settings-page__dialog-grid">
          <div class="price-alert-settings-page__field">
            <label class="price-alert-settings-page__label" for="watch-enabled">
              Theo dõi độ mới của giá
            </label>
            <ToggleSwitch
              v-model="watchEnabled"
              input-id="watch-enabled"
              :disabled="watchBusy"
            />
          </div>
          <div class="price-alert-settings-page__field">
            <label
              class="price-alert-settings-page__label required"
              for="watch-interval"
            >
              Chu kỳ kỳ vọng (ngày)
            </label>
            <InputNumber
              v-model="watchInterval"
              input-id="watch-interval"
              :disabled="watchBusy"
              :min="1"
              :max="365"
              :use-grouping="false"
              suffix=" ngày"
            />
          </div>
        </div>
        <p class="price-alert-settings-page__hint">
          Vật tư quá chu kỳ mà chưa có giá mới sẽ hiện "Quá hạn" ở Dashboard và
          được nhắc khi bật nhắc cập nhật giá. Tắt theo dõi nếu vật tư này
          không cần cập nhật đều.
        </p>
        <div
          v-if="watchError"
          class="price-alert-settings-page__general-error"
          role="alert"
          data-testid="watch-error"
        >
          <i class="pi pi-exclamation-triangle" aria-hidden="true" />
          <span>{{ watchError }}</span>
        </div>
        <template #footer>
          <Button
            v-if="watchTarget?.freshness"
            label="Bỏ cấu hình"
            severity="secondary"
            outlined
            :disabled="watchBusy"
            data-testid="watch-clear"
            @click="clearWatch"
          />
          <Button
            label="Hủy"
            severity="secondary"
            outlined
            :disabled="watchBusy"
            data-testid="watch-cancel"
            @click="closeWatchDialog"
          />
          <Button
            label="Lưu theo dõi"
            :disabled="watchBusy"
            data-testid="watch-save"
            @click="saveWatch"
          />
        </template>
      </Dialog>
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import Button from 'primevue/button'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Dialog from 'primevue/dialog'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Tag from 'primevue/tag'
import ToggleSwitch from 'primevue/toggleswitch'

import AdminLayout from '@/layouts/AdminLayout.vue'
import { usePriceAlertMaterialThresholds } from '@/composables/usePriceAlertMaterialThresholds'
import { usePriceAlertSettingsPage } from '@/composables/usePriceAlertSettingsPage'

const {
  fields,
  errors,
  meta,
  loading,
  generalError,
  submitError,
  successMessage,
  isSaving,
  canEdit,
  fetchSettings,
  submitSettings,
} = usePriceAlertSettingsPage()

const {
  materials,
  total,
  loading: materialsLoading,
  generalError: materialsError,
  rows,
  first,
  rowsPerPageOptions,
  search,
  dialogVisible,
  target,
  isBusy,
  errorMessage: materialDialogError,
  successMessage: materialSuccess,
  fields: materialFormFields,
  errors: materialErrors,
  fetchMaterials,
  onPageChange,
  onSearchInput,
  openEdit,
  closeDialog,
  saveOverride,
  resetToDefault,
  watchDialogVisible,
  watchTarget,
  watchEnabled,
  watchInterval,
  watchBusy,
  watchError,
  openWatchEdit,
  closeWatchDialog,
  saveWatch,
  clearWatch,
} = usePriceAlertMaterialThresholds()

const thresholdFields = [
  { name: 'lightFromPercent', label: 'Nhẹ từ' },
  { name: 'mediumFromPercent', label: 'Trung bình từ' },
  { name: 'largeOverPercent', label: 'Lớn trên' },
  { name: 'anomalyPercent', label: 'Giá bất thường từ' },
] as const

const parameterFields = [
  {
    name: 'referenceWorkingDays',
    label: 'Cửa sổ tham chiếu (ngày làm việc)',
    min: 1,
    max: 30,
    hint: 'So giá mới với các điểm trong số ngày này.',
  },
  {
    name: 'referenceFallbackDays',
    label: 'Gốc dự phòng (ngày)',
    min: 0,
    max: 365,
    hint: 'Dùng khi cửa sổ tham chiếu trống; 0 là tắt.',
  },
  {
    name: 'anomalyLookbackDays',
    label: 'Cửa sổ giá bất thường (ngày)',
    min: 1,
    max: 365,
    hint: 'Trung vị tính trong số ngày này.',
  },
  {
    name: 'maxTriggerDelayWorkingDays',
    label: 'Độ trễ tối đa (ngày làm việc)',
    min: 0,
    max: 30,
    hint: 'Phiếu nhập muộn hơn thì không sinh thông báo.',
  },
  {
    name: 'staffLookbackDays',
    label: 'Cửa sổ nhân viên (ngày)',
    min: 1,
    max: 365,
    hint: 'Nhân viên nhận tin của vật tư họ nhập trong số ngày này.',
  },
  {
    name: 'dedupeWindowDays',
    label: 'Cửa sổ chống lặp (ngày)',
    min: 0,
    max: 90,
    hint: 'Không báo lại cùng chiều và mức trong số ngày này.',
  },
  {
    name: 'immediateCapPerScan',
    label: 'Trần tin mỗi lần quét',
    min: 1,
    max: 500,
    hint: 'Vượt trần thì gộp vào một tin tóm tắt.',
  },
  {
    name: 'digestHourLocal',
    label: 'Giờ bản tin (0 đến 23)',
    min: 0,
    max: 23,
    hint: 'Bản tin tổng hợp mức Nhẹ gửi từ giờ này (giờ Việt Nam).',
  },
] as const

const materialFields = [
  {
    name: 'lightFromPercent',
    label: 'Nhẹ từ',
    required: true,
    placeholder: '',
  },
  {
    name: 'mediumFromPercent',
    label: 'Trung bình từ',
    required: true,
    placeholder: '',
  },
  {
    name: 'largeOverPercent',
    label: 'Lớn trên',
    required: true,
    placeholder: '',
  },
  {
    name: 'anomalyPercent',
    label: 'Giá bất thường từ',
    required: false,
    placeholder: 'Mặc định',
  },
] as const

function valueClass(isOverride: boolean) {
  return isOverride
    ? 'price-alert-settings-page__value'
    : 'price-alert-settings-page__value price-alert-settings-page__value--default'
}

onMounted(() => {
  void fetchSettings()
  void fetchMaterials()
})
</script>
