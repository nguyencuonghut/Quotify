<template>
  <AdminLayout section-label="Báo giá" title="Giá bất thường">
    <div class="price-alert-anomalies-page">
      <section class="price-alert-anomalies-page__header">
        <div
          class="price-alert-anomalies-page__tabs"
          role="tablist"
          aria-label="Danh sách giá bất thường"
        >
          <Button
            label="Chờ duyệt"
            :outlined="tab !== 'pending'"
            role="tab"
            :aria-selected="tab === 'pending'"
            data-testid="anomalies-tab-pending"
            @click="setTab('pending')"
          />
          <Button
            label="Lịch sử 30 ngày"
            :outlined="tab !== 'resolved'"
            role="tab"
            :aria-selected="tab === 'resolved'"
            data-testid="anomalies-tab-resolved"
            @click="setTab('resolved')"
          />
        </div>
        <Button
          aria-label="Tải lại danh sách giá bất thường"
          icon="pi pi-refresh"
          severity="secondary"
          outlined
          @click="fetchAnomalies"
        />
      </section>

      <p class="price-alert-anomalies-page__hint">
        Điểm giá lệch lớn so với giá gần đây bị tạm loại khỏi tính biến động.
        <strong>Giá đúng</strong> đưa điểm trở lại tính toán;
        <strong>Nhập sai</strong> giữ điểm bị loại (phiếu không bị sửa hay hủy).
      </p>

      <div
        v-if="successMessage"
        class="price-alert-anomalies-page__notice price-alert-anomalies-page__notice--success"
        role="status"
        data-testid="anomalies-success"
      >
        {{ successMessage }}
      </div>
      <div
        v-if="errorMessage"
        class="price-alert-anomalies-page__general-error"
        role="alert"
        data-testid="anomalies-error"
      >
        <i class="pi pi-exclamation-triangle" aria-hidden="true" />
        <span>{{ errorMessage }}</span>
      </div>
      <div
        v-if="generalError"
        class="price-alert-anomalies-page__general-error"
        role="alert"
      >
        <i class="pi pi-exclamation-triangle" aria-hidden="true" />
        <span>{{ generalError }}</span>
      </div>

      <section
        v-if="!generalError"
        class="price-alert-anomalies-page__table-wrapper"
      >
        <DataTable
          :first="first"
          :loading="loading"
          :rows="rows"
          :rows-per-page-options="rowsPerPageOptions"
          :total-records="total"
          :value="anomalies"
          current-page-report-template="Hiển thị từ {first} đến {last} trên tổng số {totalRecords} dòng"
          data-key="id"
          lazy
          paginator
          paginator-template="FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink CurrentPageReport RowsPerPageDropdown"
          responsive-layout="scroll"
          @page="onPageChange"
        >
          <template #empty>
            <div class="price-alert-anomalies-page__empty-state">
              {{
                tab === 'pending'
                  ? 'Không có điểm giá nào đang chờ duyệt.'
                  : 'Chưa có điểm giá nào được xử lý trong 30 ngày qua.'
              }}
            </div>
          </template>

          <Column header="Vật tư">
            <template #body="{ data }">
              <div class="price-alert-anomalies-page__cell">
                <strong>{{ data.materialName }}</strong>
                <small>Kỳ giao hàng {{ data.deliveryMonthLabel }}</small>
                <small>Nhận ngày {{ data.receivedDateLabel }}</small>
              </div>
            </template>
          </Column>
          <Column header="Giá nhận">
            <template #body="{ data }">
              <div class="price-alert-anomalies-page__cell">
                <strong>{{ data.priceLabel }}</strong>
                <small
                  :class="`price-alert-anomalies-page__percent price-alert-anomalies-page__percent--${data.direction}`"
                >
                  {{ data.percentLabel }} so với trung vị {{ data.medianLabel }}
                </small>
              </div>
            </template>
          </Column>
          <Column header="Giá hợp lệ gần đây">
            <template #body="{ data }">
              <div class="price-alert-anomalies-page__cell">
                <span>{{ data.referenceLabel }}</span>
                <small v-if="data.lowConfidence">
                  Độ tin cậy thấp: chỉ có 1 giá tham chiếu
                </small>
                <small v-if="data.attachedCount > 0">
                  Có {{ data.attachedCount }} điểm xác nhận cùng mức
                </small>
              </div>
            </template>
          </Column>
          <Column header="Người nhập">
            <template #body="{ data }">
              <div class="price-alert-anomalies-page__cell">
                <span>{{ data.enteredByName }}</span>
                <small>{{ data.ageLabel }}</small>
                <RouterLink :to="`/quotes/${data.quoteId}`"
                  >Xem phiếu</RouterLink
                >
              </div>
            </template>
          </Column>
          <Column header="Trạng thái / Thao tác">
            <template #body="{ data }">
              <div class="price-alert-anomalies-page__cell">
                <Tag
                  :severity="data.statusSeverity"
                  :value="data.statusLabel"
                />
                <small v-if="data.reviewerLabel">{{
                  data.reviewerLabel
                }}</small>
                <div
                  v-if="data.isPending"
                  class="price-alert-anomalies-page__actions"
                >
                  <Button
                    label="Giá đúng"
                    icon="pi pi-check"
                    severity="success"
                    size="small"
                    :disabled="isBusy || !canReview"
                    :title="reviewTitle"
                    data-testid="anomaly-accept"
                    @click="openConfirm(data, 'accepted')"
                  />
                  <Button
                    label="Nhập sai"
                    icon="pi pi-times"
                    severity="danger"
                    size="small"
                    outlined
                    :disabled="isBusy || !canReview"
                    :title="reviewTitle"
                    data-testid="anomaly-reject"
                    @click="openConfirm(data, 'rejected')"
                  />
                </div>
              </div>
            </template>
          </Column>
        </DataTable>

        <ul
          class="price-alert-anomalies-page__cards"
          data-testid="anomaly-cards"
        >
          <li
            v-if="!anomalies.length && !loading"
            class="price-alert-anomalies-page__empty-state"
          >
            {{
              tab === 'pending'
                ? 'Không có điểm giá nào đang chờ duyệt.'
                : 'Chưa có điểm giá nào được xử lý trong 30 ngày qua.'
            }}
          </li>
          <li
            v-for="item in anomalies"
            :key="item.id"
            class="price-alert-anomalies-page__card"
          >
            <div class="price-alert-anomalies-page__card-head">
              <strong>{{ item.materialName }}</strong>
              <Tag :severity="item.statusSeverity" :value="item.statusLabel" />
            </div>
            <small
              >Kỳ giao hàng {{ item.deliveryMonthLabel }} · nhận
              {{ item.receivedDateLabel }}</small
            >
            <span>
              Giá <strong>{{ item.priceLabel }}</strong>
              <span
                :class="`price-alert-anomalies-page__percent price-alert-anomalies-page__percent--${item.direction}`"
              >
                {{ item.percentLabel }}
              </span>
              so với trung vị {{ item.medianLabel }}
            </span>
            <small>Giá gần đây: {{ item.referenceLabel }}</small>
            <small v-if="item.lowConfidence"
              >Độ tin cậy thấp: chỉ có 1 giá tham chiếu</small
            >
            <small>{{ item.enteredByName }} · {{ item.ageLabel }}</small>
            <small v-if="item.reviewerLabel">{{ item.reviewerLabel }}</small>
            <RouterLink :to="`/quotes/${item.quoteId}`">Xem phiếu</RouterLink>
            <div
              v-if="item.isPending"
              class="price-alert-anomalies-page__actions"
            >
              <Button
                label="Giá đúng"
                icon="pi pi-check"
                severity="success"
                size="small"
                :disabled="isBusy || !canReview"
                :title="reviewTitle"
                @click="openConfirm(item, 'accepted')"
              />
              <Button
                label="Nhập sai"
                icon="pi pi-times"
                severity="danger"
                size="small"
                outlined
                :disabled="isBusy || !canReview"
                :title="reviewTitle"
                @click="openConfirm(item, 'rejected')"
              />
            </div>
          </li>
        </ul>
      </section>

      <Dialog
        v-model:visible="confirmVisible"
        :header="confirmHeader"
        modal
        :closable="!isBusy"
        :close-on-escape="!isBusy"
        class="price-alert-anomalies-page__dialog"
        @hide="closeConfirm"
      >
        <p v-if="confirmTarget" data-testid="anomaly-confirm-text">
          {{ confirmText }}
        </p>
        <template #footer>
          <Button
            label="Hủy"
            severity="secondary"
            outlined
            :disabled="isBusy"
            @click="closeConfirm"
          />
          <Button
            :label="
              confirmDecisionValue === 'accepted'
                ? 'Xác nhận giá đúng'
                : 'Đánh dấu nhập sai'
            "
            :severity="
              confirmDecisionValue === 'accepted' ? 'success' : 'danger'
            "
            :disabled="isBusy"
            data-testid="anomaly-confirm"
            @click="confirmDecision"
          />
        </template>
      </Dialog>
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import Button from 'primevue/button'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Dialog from 'primevue/dialog'
import Tag from 'primevue/tag'

import AdminLayout from '@/layouts/AdminLayout.vue'
import { usePriceAlertAnomaliesPage } from '@/composables/usePriceAlertAnomaliesPage'
import { usePermissionStore } from '@/stores/permission.store'

const {
  tab,
  anomalies,
  total,
  loading,
  generalError,
  rows,
  first,
  rowsPerPageOptions,
  confirmVisible,
  confirmTarget,
  confirmDecisionValue,
  isBusy,
  errorMessage,
  successMessage,
  fetchAnomalies,
  onPageChange,
  setTab,
  openConfirm,
  closeConfirm,
  confirmDecision,
} = usePriceAlertAnomaliesPage()

const permissionStore = usePermissionStore()
const canReview = computed(() =>
  permissionStore.can('price_alerts.receive_all'),
)
const reviewTitle = computed(() =>
  canReview.value ? '' : 'Bạn không có quyền duyệt giá bất thường.',
)
const confirmHeader = computed(() =>
  confirmDecisionValue.value === 'accepted'
    ? 'Xác nhận giá đúng'
    : 'Đánh dấu nhập sai',
)
const confirmText = computed(() => {
  const item = confirmTarget.value
  if (!item) {
    return ''
  }
  const subject = `${item.materialName}, kỳ ${item.deliveryMonthLabel}, giá ${item.priceLabel}`
  return confirmDecisionValue.value === 'accepted'
    ? `Xác nhận ${subject} là đúng? Điểm giá sẽ được tính lại trong biến động giá.`
    : `Đánh dấu ${subject} là nhập sai? Điểm giá tiếp tục bị loại khỏi tính biến động. Phiếu báo giá không bị thay đổi.`
})

onMounted(fetchAnomalies)
</script>
