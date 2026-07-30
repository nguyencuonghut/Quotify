<template>
  <AdminLayout
    section-label="Báo giá"
    :title="isNewQuote ? 'Nhập báo giá mới' : isNewVersion ? 'Tạo bản điều chỉnh' : 'Chỉnh sửa bản nháp'"
  >
    <div class="quote-editor-page">
      <!-- Error Banner -->
      <div v-if="errorMsg" class="quote-editor-page__error-banner" role="alert">
        <i class="pi pi-exclamation-triangle" />
        <span>{{ errorMsg }}</span>
      </div>

    <form @submit.prevent="submitForm">
      <!-- General Metadata Card -->
      <div class="quote-editor-page__card">
        <h3 class="quote-editor-page__section-title">Thông tin chung</h3>
        <div class="quote-editor-page__meta-grid">
          <!-- Supplier (Editable only on new quote) -->
          <div class="quote-editor-page__form-field">
            <label for="supplier-dropdown">
              Nhà cung cấp
              <span v-if="isNewQuote" class="required-marker">*</span>
            </label>
            <Select
              v-if="isNewQuote"
              id="supplier-dropdown"
              v-model="supplierId"
              :loading="isSupplierListLoading"
              :options="activeSuppliers"
              option-label="name"
              option-value="id"
              placeholder="Chọn nhà cung cấp..."
              class="quote-editor-page__input-w"
              filter
              :filter-fields="['code', 'name']"
            />
            <InputText
              v-else
              id="supplier-static"
              :model-value="quoteDetail?.supplierName"
              disabled
              class="quote-editor-page__input-w"
            />
          </div>

          <!-- Received Date -->
          <div class="quote-editor-page__form-field">
            <label for="received-date-picker">
              Ngày nhận báo giá
              <span class="required-marker">*</span>
            </label>
            <DatePicker
              id="received-date-picker"
              v-model="receivedDateVal"
              date-format="yy-mm-dd"
              placeholder="Chọn ngày nhận..."
              class="quote-editor-page__input-w"
              show-icon
            />
          </div>
        </div>

        <div v-if="isNewVersion" class="quote-editor-page__correction-banner">
          <p class="quote-editor-page__backfill-title">
            <i class="pi pi-exclamation-circle" />
            Bản điều chỉnh sẽ thay thế phiên bản đã xác nhận hiện tại sau khi được xác nhận.
          </p>
          <p class="quote-editor-page__correction-hint">
            Giữ ngày nhận báo giá như phiên bản cũ để dùng snapshot tỷ giá cũ. Đổi sang hôm nay để lấy tỷ giá Vietcombank mới.
          </p>
          <div class="quote-editor-page__form-field">
            <label for="correction-reason-input">
              Lý do điều chỉnh
              <span class="required-marker">*</span>
            </label>
            <Textarea
              id="correction-reason-input"
              v-model="correctionReason"
              rows="2"
              placeholder="Ví dụ: Sửa giá nhập nhầm từ báo giá nhà cung cấp..."
              class="quote-editor-page__input-w"
            />
          </div>
        </div>

        <!-- Backfill Banner & Reason -->
        <div v-if="isBackfilled" class="quote-editor-page__backfill-banner">
          <p class="quote-editor-page__backfill-title">
            <i class="pi pi-info-circle" />
            Báo giá nhập lại (Nhập lùi ngày/tháng trong quá khứ)
          </p>
          <div class="quote-editor-page__form-field">
            <label for="backfill-reason-input">
              Lý do nhập lùi báo giá
              <span class="required-marker">*</span>
            </label>
            <Textarea
              id="backfill-reason-input"
              v-model="backfillReason"
              rows="2"
              placeholder="Nhập lý do bắt buộc..."
              class="quote-editor-page__input-w"
            />
          </div>
        </div>
      </div>

      <!-- Lines Editor Card -->
      <div class="quote-editor-page__card">
        <h3 class="quote-editor-page__section-title">Chi tiết dòng vật tư</h3>

        <!-- Desktop Table View -->
        <div class="quote-editor-page__table-wrapper">
          <table class="quote-editor-page__table">
            <thead>
              <tr>
                <th style="width: 50px; text-align: center">STT</th>
                <th style="width: 250px">Vật tư <span class="required-marker">*</span></th>
                <th style="width: 150px">Giá gốc <span class="required-marker">*</span></th>
                <th style="width: 150px">Tiền tệ / Đơn vị <span class="required-marker">*</span></th>
                <th style="width: 140px">Tháng giao hàng <span class="required-marker">*</span></th>
                <th>Quy đổi & Preview</th>
                <th style="width: 110px; text-align: center">Hành động</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(line, index) in lines" :key="index">
                <td class="quote-editor-page__line-num">{{ index + 1 }}</td>
                <td>
                  <Select
                    v-model="line.materialId"
                    :options="supplierMaterials"
                    option-label="materialName"
                    option-value="materialId"
                    placeholder="Chọn vật tư..."
                    class="quote-editor-page__input-w"
                    :disabled="isSupplierLoading"
                    filter
                    :filter-fields="['materialCode', 'materialName']"
                  />
                </td>
                <td>
                  <InputNumber
                    v-model="line.priceOriginal"
                    :min="0"
                    :min-fraction-digits="2"
                    :max-fraction-digits="2"
                    placeholder="0.00"
                    locale="en-US"
                    class="quote-editor-page__input-w"
                  />
                </td>
                <td>
                  <Select
                    :model-value="`${line.currency.toUpperCase()}_${line.unit.toUpperCase()}`"
                    @update:model-value="(val) => {
                      if (val) {
                        const [curr, uni] = val.split('_')
                        line.currency = curr
                        line.unit = uni
                      }
                    }"
                    :options="currencyUnitOptions"
                    option-label="label"
                    option-value="value"
                    placeholder="Đơn vị..."
                    class="quote-editor-page__input-w"
                  />
                </td>
                <td>
                  <DatePicker
                    :model-value="line.deliveryMonth ? new Date(Number(line.deliveryMonth.split('-')[0]), Number(line.deliveryMonth.split('-')[1]) - 1, 1) : null"
                    @update:model-value="(val) => {
                      if (val) {
                        const yyyy = val.getFullYear()
                        const mm = String(val.getMonth() + 1).padStart(2, '0')
                        line.deliveryMonth = `${yyyy}-${mm}`
                      }
                    }"
                    view="month"
                    date-format="yy-mm"
                    placeholder="Tháng..."
                    class="quote-editor-page__input-w"
                    :panelStyle="{ minWidth: '280px' }"
                  />
                </td>
                <td>
                  <div v-if="line.currency.toUpperCase() === 'USD' && line.unit.toUpperCase() === 'MT'">
                    <ExchangeRateField
                      :received-date="receivedDate"
                      v-model:rate="line.exchangeRate"
                      v-model:source="line.exchangeRateSource"
                      v-model:source-mode="line.rateSourceMode"
                      v-model:manual-reason="line.exchangeRateManualReason"
                      :hide-labels="true"
                    />
                    <div v-if="getLinePreviewPrice(line) !== null" class="quote-editor-page__preview-price mt-2">
                      Preview: {{ formatMoney(getLinePreviewPrice(line)) }} <span>VNĐ/KG</span>
                    </div>
                  </div>
                  <div v-else>
                    <span class="text-sm text-gray-500">Quy đổi 1:1</span>
                    <div v-if="getLinePreviewPrice(line) !== null" class="quote-editor-page__preview-price mt-1">
                      Preview: {{ formatMoney(getLinePreviewPrice(line)) }} <span>VNĐ/KG</span>
                    </div>
                  </div>
                </td>
                <td style="text-align: center">
                  <div class="quote-editor-page__action-cell">
                    <Button
                      icon="pi pi-copy"
                      severity="secondary"
                      text
                      rounded
                      title="Nhân bản dòng"
                      aria-label="Nhân bản dòng"
                      @click="duplicateLine(index)"
                    />
                    <Button
                      icon="pi pi-trash"
                      severity="danger"
                      text
                      rounded
                      title="Xóa dòng"
                      aria-label="Xóa dòng"
                      @click="removeLine(index)"
                    />
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Mobile Stack View -->
        <div class="quote-editor-page__mobile-lines">
          <div
            v-for="(line, index) in lines"
            :key="index"
            class="quote-editor-page__mobile-line-card"
          >
            <div class="quote-editor-page__mobile-card-header">
              <h4>Dòng #{{ index + 1 }}</h4>
              <div class="quote-editor-page__action-cell">
                <Button
                  icon="pi pi-copy"
                  severity="secondary"
                  text
                  rounded
                  title="Nhân bản dòng"
                  aria-label="Nhân bản dòng"
                  @click="duplicateLine(index)"
                />
                <Button
                  icon="pi pi-trash"
                  severity="danger"
                  text
                  rounded
                  title="Xóa dòng"
                  aria-label="Xóa dòng"
                  @click="removeLine(index)"
                />
              </div>
            </div>
            
            <div class="quote-editor-page__form-field">
              <label>Vật tư <span class="required-marker">*</span></label>
              <Select
                v-model="line.materialId"
                :options="supplierMaterials"
                option-label="materialName"
                option-value="materialId"
                placeholder="Chọn vật tư..."
                class="quote-editor-page__input-w"
                :disabled="isSupplierLoading"
                filter
                :filter-fields="['materialCode', 'materialName']"
              />
            </div>

            <div class="grid">
              <div class="col-6 quote-editor-page__form-field">
                <label>Giá gốc <span class="required-marker">*</span></label>
                <InputNumber
                  v-model="line.priceOriginal"
                  :min="0"
                  placeholder="0.00"
                  locale="en-US"
                  class="quote-editor-page__input-w"
                />
              </div>
              <div class="col-6 quote-editor-page__form-field">
                <label>Đơn vị <span class="required-marker">*</span></label>
                <Select
                  :model-value="`${line.currency.toUpperCase()}_${line.unit.toUpperCase()}`"
                  @update:model-value="(val) => {
                    if (val) {
                      const [curr, uni] = val.split('_')
                      line.currency = curr
                      line.unit = uni
                    }
                  }"
                  :options="currencyUnitOptions"
                  option-label="label"
                  option-value="value"
                  class="quote-editor-page__input-w"
                />
              </div>
            </div>

            <div class="quote-editor-page__form-field">
              <label>Tháng giao hàng <span class="required-marker">*</span></label>
              <DatePicker
                :model-value="line.deliveryMonth ? new Date(Number(line.deliveryMonth.split('-')[0]), Number(line.deliveryMonth.split('-')[1]) - 1, 1) : null"
                @update:model-value="(val) => {
                  if (val) {
                    const yyyy = val.getFullYear()
                    const mm = String(val.getMonth() + 1).padStart(2, '0')
                    line.deliveryMonth = `${yyyy}-${mm}`
                  }
                }"
                view="month"
                date-format="yy-mm"
                placeholder="Tháng..."
                class="quote-editor-page__input-w"
                :panelStyle="{ minWidth: '280px' }"
              />
            </div>

            <div class="quote-editor-page__mobile-rate-section">
              <div v-if="line.currency.toUpperCase() === 'USD' && line.unit.toUpperCase() === 'MT'">
                <ExchangeRateField
                  :received-date="receivedDate"
                  v-model:rate="line.exchangeRate"
                  v-model:source="line.exchangeRateSource"
                  v-model:source-mode="line.rateSourceMode"
                  v-model:manual-reason="line.exchangeRateManualReason"
                />
                <div v-if="getLinePreviewPrice(line) !== null" class="quote-editor-page__preview-price mt-2">
                  Preview: {{ formatMoney(getLinePreviewPrice(line)) }} <span>VNĐ/KG</span>
                </div>
              </div>
              <div v-else class="flex justify-between align-center py-2 border-top">
                <span class="text-sm text-gray-500">Quy đổi 1:1</span>
                <div v-if="getLinePreviewPrice(line) !== null" class="quote-editor-page__preview-price">
                  Preview: {{ formatMoney(getLinePreviewPrice(line)) }} <span>VNĐ/KG</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <Button
          label="Thêm dòng vật tư"
          icon="pi pi-plus"
          severity="secondary"
          outlined
          class="quote-editor-page__add-row-btn"
          @click="addLine"
        />
      </div>

      <!-- Action Buttons -->
      <div class="quote-editor-page__footer-actions">
        <Button
          label="Hủy"
          icon="pi pi-times"
          severity="secondary"
          outlined
          @click="goBack"
          :disabled="isSubmitting"
        />
        <Button
          label="Lưu bản nháp"
          icon="pi pi-save"
          type="submit"
          :loading="isSubmitting"
        />
      </div>
    </form>
  </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Select from 'primevue/select'
import DatePicker from 'primevue/datepicker'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import Button from 'primevue/button'

import { useAuthStore } from '@/stores/auth.store'
import { listSuppliers } from '@/api/suppliers.api'
import { getQuote, createQuote, updateDraft, createVersion } from '@/api/quotes.api'
import type { SupplierDomain } from '@/types/suppliers'
import type { QuoteDomain, QuoteVersionDomain } from '@/types/quotes'
import { useQuoteEditor } from '@/composables/useQuoteEditor'
import ExchangeRateField from '@/components/quotes/ExchangeRateField.vue'
import AdminLayout from '@/layouts/AdminLayout.vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

// Route params
const quoteId = route.params.quoteId as string | undefined
const versionId = route.params.versionId as string | undefined

const isNewQuote = computed(() => !quoteId)
const isNewVersion = computed(() => !!quoteId && !versionId)

const activeSuppliers = ref<SupplierDomain[]>([])
const isSupplierListLoading = ref<boolean>(false)
const quoteDetail = ref<QuoteDomain | null>(null)

const {
  supplierId,
  receivedDate,
  isBackfilled,
  backfillReason,
  correctionReason,
  lines,
  supplierMaterials,
  isSupplierLoading,
  isSubmitting,
  errorMsg,
  initSettings,
  fetchUsdRateToday,
  addLine,
  removeLine,
  duplicateLine,
  loadVersionData,
  getLinePreviewPrice,
  validateForm,
  prepareCreatePayload,
  prepareUpdatePayload,
} = useQuoteEditor(authStore.accessToken)

// Bind receivedDate from Date object or ISO String
const receivedDateVal = computed<Date | null>({
  get() {
    return receivedDate.value ? new Date(receivedDate.value) : null
  },
  set(val) {
    if (val) {
      const yyyy = val.getFullYear()
      const mm = String(val.getMonth() + 1).padStart(2, '0')
      const dd = String(val.getDate()).padStart(2, '0')
      receivedDate.value = `${yyyy}-${mm}-${dd}`
    } else {
      receivedDate.value = ''
    }
  },
})

// Currency/Unit composite models and options
const currencyUnitOptions = [
  { label: 'VNĐ / KG', value: 'VND_KG' },
  { label: 'USD / MT', value: 'USD_MT' },
]



const formatMoney = (val: number | null): string => {
  if (val === null) return ''
  return new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(val)
}

// Load initialization data
onMounted(async () => {
  await initSettings()
  await fetchUsdRateToday()

  if (isNewQuote.value) {
    // Load suppliers list for selection
    isSupplierListLoading.value = true
    try {
      const result = await listSuppliers(
        { limit: 100, offset: 0, status: 'active', sort_by: 'name', sort_order: 'asc' },
        authStore.accessToken
      )
      activeSuppliers.value = result.items
    } catch {
      // ignore
    } finally {
      isSupplierListLoading.value = false
    }
    
    // Add first line by default
    addLine()
  } else {
    // Load Quote detail for Edit Draft or Clone version
    try {
      const quote = await getQuote(quoteId!, authStore.accessToken)
      quoteDetail.value = quote
      supplierId.value = quote.supplierId

      if (versionId) {
        // Edit draft version
        const version = quote.versions.find((v) => v.id === versionId)
        if (version) {
          if (version.status !== 'draft') {
            router.replace(`/quotes/${quoteId}`)
            return
          }
          await loadVersionData(version, quote)
        }
      } else {
        // Create new version based on latest confirmed version
        const sorted = [...quote.versions].sort((a, b) => b.versionNumber - a.versionNumber)
        const latest = sorted[0]
        if (latest) {
          await loadVersionData(latest, quote)
        } else {
          addLine()
        }
      }
    } catch (err: any) {
      errorMsg.value = err.message || 'Không thể tải dữ liệu báo giá.'
    }
  }
})

const goBack = () => {
  if (quoteId) {
    router.push(`/quotes/${quoteId}`)
  } else {
    router.push('/')
  }
}

const submitForm = async () => {
  if (!validateForm()) {
    return
  }
  if (isNewVersion.value && (!correctionReason.value || !correctionReason.value.trim())) {
    errorMsg.value = 'Vui lòng nhập lý do điều chỉnh báo giá.'
    return
  }

  isSubmitting.value = true
  try {
    if (isNewQuote.value) {
      const payload = prepareCreatePayload()
      const quote = await createQuote(payload, authStore.accessToken)
      router.push(`/quotes/${quote.id}`)
    } else if (isNewVersion.value) {
      const payload = prepareUpdatePayload()
      const version = await createVersion(quoteId!, payload, authStore.accessToken)
      router.push(`/quotes/${quoteId}`)
    } else {
      // Edit draft
      const payload = prepareUpdatePayload()
      await updateDraft(quoteId!, versionId!, payload, authStore.accessToken)
      router.push(`/quotes/${quoteId}`)
    }
  } catch (err: any) {
    errorMsg.value = err.message || 'Đã xảy ra lỗi khi lưu báo giá.'
  } finally {
    isSubmitting.value = false
  }
}
</script>
