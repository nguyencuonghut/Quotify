<template>
  <AdminLayout section-label="Báo giá" title="Chi tiết phiếu báo giá">
    <div class="quote-detail-page">
    <!-- Header Section -->
    <div class="quote-detail-page__header">
      <div class="quote-detail-page__title-section">
        <div class="quote-detail-page__supplier-tag">
          <i class="pi pi-truck" />
          <span>{{ quote?.supplierCode }} - {{ quote?.supplierName }}</span>
        </div>
        <h2 class="quote-detail-page__title">Phiếu báo giá nguyên liệu</h2>
      </div>

      <div class="quote-detail-page__actions">
        <Button
          label="Quay lại"
          icon="pi pi-arrow-left"
          severity="secondary"
          outlined
          @click="goBack"
        />
        <Button
          v-if="canUpdateQuote && activeVersion?.status !== 'draft'"
          label="Tạo bản điều chỉnh"
          icon="pi pi-copy"
          @click="createNewVersion"
        />
        <Button
          v-if="canUpdateQuote && activeVersion && activeVersion.status === 'draft'"
          label="Sửa bản nháp"
          icon="pi pi-pencil"
          outlined
          @click="editDraft"
        />
        <Button
          v-if="canUpdateQuote && activeVersion && activeVersion.status === 'draft'"
          label="Xác nhận phiên bản"
          icon="pi pi-check"
          severity="primary"
          @click="showConfirmDialog = true"
        />
        <Button
          v-if="canUpdateQuote && activeVersion && activeVersion.status === 'draft'"
          label="Xóa bản nháp"
          icon="pi pi-trash"
          severity="danger"
          outlined
          @click="showDeleteDraftDialog = true"
        />
      </div>
    </div>

    <!-- Error message -->
    <div v-if="errorMsg" style="margin-bottom: 1rem">
      <Message severity="error" @close="errorMsg = null">{{ errorMsg }}</Message>
    </div>

    <!-- Loading state -->
    <div v-if="isLoading && !quote" class="quote-detail-page__loading">
      <i class="pi pi-spin pi-spinner" aria-hidden="true" />
      <span>Đang tải phiếu báo giá...</span>
    </div>

    <!-- Main Grid Split -->
    <div v-if="quote" class="quote-detail-page__grid">
      <!-- Cột chính: Chi tiết version active -->
      <div class="quote-detail-page__main-content">
        <div class="quote-detail-page__card">
          <div class="quote-detail-page__section-header">
            <h3 class="quote-detail-page__section-title">
              Thông tin phiên bản #{{ activeVersion?.versionNumber }}
            </h3>
            <span
              v-if="activeVersion"
              class="quote-detail-page__status-badge"
              :class="activeVersion.status"
            >
              {{ getVersionStatusLabel(activeVersion.status) }}
            </span>
          </div>

          <!-- Metadata Grid -->
          <div v-if="activeVersion" class="quote-detail-page__meta-grid">
            <div class="quote-detail-page__meta-item">
              <span>Ngày nhận báo giá</span>
              <strong>{{ activeVersion.receivedDate }}</strong>
            </div>
            <div v-if="activeVersion.createdByName" class="quote-detail-page__meta-item">
              <span>Người nhập báo giá</span>
              <strong>{{ activeVersion.createdByName }}</strong>
            </div>
            <div class="quote-detail-page__meta-item">
              <span>Trạng thái nhập lùi</span>
              <strong>{{ activeVersion.isBackfilled ? 'Có (Nhập bù)' : 'Không' }}</strong>
            </div>
            <div v-if="activeVersion.confirmedAt" class="quote-detail-page__meta-item">
              <span>Thời điểm xác nhận</span>
              <strong>{{ formatDateTime(activeVersion.confirmedAt) }}</strong>
            </div>
            <div v-if="activeVersion.correctionReason" class="quote-detail-page__meta-item" style="grid-column: span 2">
              <span>Lý do điều chỉnh</span>
              <strong>{{ activeVersion.correctionReason }}</strong>
            </div>
            <div v-if="activeVersion.supersededAt" class="quote-detail-page__meta-item">
              <span>Thời điểm bị thay thế</span>
              <strong>{{ formatDateTime(activeVersion.supersededAt) }}</strong>
            </div>
          </div>

          <!-- Source File Section -->
          <div v-if="activeVersion">
            <h4 class="quote-detail-page__subsection-title" style="margin-bottom: 0.5rem">Tệp tin báo giá gốc</h4>
            
            <!-- Confirmed Version / Draft with associated file -->
            <div v-if="activeVersion.fileId" class="quote-detail-page__file-card">
              <div class="file-info">
                <i class="pi pi-file-excel" />
                <div>
                  <span class="name">Tệp gốc báo giá #{{ activeVersion.versionNumber }}</span>
                </div>
              </div>
              <Button
                label="Tải xuống"
                icon="pi pi-download"
                severity="secondary"
                text
                @click="downloadSourceFile(activeVersion)"
              />
            </div>
            
            <!-- Draft Version without associated file -> show uploader -->
            <div v-else-if="activeVersion.status === 'draft' && canUpdateQuote" class="quote-detail-page__file-upload-section">
              <i class="pi pi-cloud-upload quote-detail-page__upload-icon" />
              <p>Đính kèm tệp tin gốc (.xlsx, .pdf, .docx, .png)</p>
              <FileUpload
                mode="basic"
                name="file"
                accept="*/*"
                :max-file-size="10000000"
                auto
                custom-upload
                @uploader="onFileSelect"
                :disabled="isFileUploading"
                choose-label="Chọn tệp tin"
              />
            </div>
            <div v-else class="quote-detail-page__empty-hint" style="margin-bottom: 1rem">
              Không có tệp tin đính kèm.
            </div>
          </div>

          <!-- Lines DataTable -->
          <div class="quote-detail-page__lines-header">
            <h4 class="quote-detail-page__subsection-title">Danh sách dòng vật tư</h4>
            <span class="quote-detail-page__lines-count">
              {{ filteredQuoteLines.length }}/{{ activeVersion?.lines.length || 0 }} dòng
            </span>
          </div>
          <div class="quote-detail-page__line-filters">
            <label class="quote-detail-page__filter-field quote-detail-page__filter-field--search">
              <span class="quote-detail-page__filter-label">Tìm kiếm</span>
              <InputText
                v-model="lineGlobalSearch"
                placeholder="Tìm mã, tên vật tư, giá, tháng..."
              />
            </label>
            <label class="quote-detail-page__filter-field">
              <span class="quote-detail-page__filter-label">Tên vật tư</span>
              <Select
                v-model="lineMaterialNameFilter"
                :options="lineMaterialNameOptions"
                aria-label="Tên vật tư"
                option-label="label"
                option-value="value"
                placeholder="Tất cả vật tư"
                show-clear
              />
            </label>
            <label class="quote-detail-page__filter-field">
              <span class="quote-detail-page__filter-label">Tháng giao</span>
              <Select
                v-model="lineDeliveryMonthFilter"
                :options="lineDeliveryMonthOptions"
                aria-label="Tháng giao"
                option-label="label"
                option-value="value"
                placeholder="Tất cả tháng"
                show-clear
              />
            </label>
            <Button
              icon="pi pi-sync"
              label="Xóa lọc"
              severity="secondary"
              outlined
              @click="resetLineFilters"
            />
          </div>
          <DataTable
            :value="filteredQuoteLines"
            class="p-datatable-sm"
            responsive-layout="scroll"
          >
            <Column header="STT" style="width: 50px; text-align: center">
              <template #body="slotProps">
                {{ slotProps.index + 1 }}
              </template>
            </Column>
            <Column field="materialCode" header="Mã vật tư" style="width: 120px" />
            <Column field="materialName" header="Tên vật tư" />
            <Column header="Giá gốc" style="width: 140px">
              <template #body="slotProps">
                <span class="quote-detail-page__price-cell">
                  <span class="quote-detail-page__price-value">
                    {{ formatMoney(slotProps.data.priceOriginal) }}
                  </span>
                  <span class="quote-detail-page__price-unit">{{ slotProps.data.currency }}</span>
                </span>
              </template>
            </Column>
            <Column field="unit" header="Đơn vị" style="width: 80px" />
            <Column header="Tháng giao" style="width: 110px">
              <template #body="slotProps">
                {{ formatDeliveryMonth(slotProps.data.deliveryMonth) }}
              </template>
            </Column>
            <Column style="width: 140px;">
              <template #header>
                <div style="display: flex; flex-direction: column; line-height: 1.3;">
                  <span>Tỷ giá quy đổi</span>
                  <span class="quote-detail-page__price-unit">(VNĐ/USD)</span>
                </div>
              </template>
              <template #body="slotProps">
                <div v-if="slotProps.data.currency.toUpperCase() === 'USD'">
                  <span class="quote-detail-page__price-value quote-detail-page__price-value--highlight">{{ formatMoney(slotProps.data.exchangeRate) }}</span>
                  <div v-if="slotProps.data.exchangeRateManualReason" class="quote-detail-page__price-unit quote-detail-page__manual-reason">
                    Lý do: {{ slotProps.data.exchangeRateManualReason }}
                  </div>
                </div>
                <span v-else class="quote-detail-page__price-unit">-</span>
              </template>
            </Column>
            <Column header="Giá quy đổi (VNĐ/KG)" style="width: 180px">
              <template #body="slotProps">
                <span class="quote-detail-page__price-value quote-detail-page__price-value--highlight">
                  {{ formatMoney(slotProps.data.priceConvertedVndPer_kg || slotProps.data.priceConvertedVndPerKg) }}
                </span>
              </template>
            </Column>
            <Column header="Thuế nhập khẩu" style="width: 130px">
              <template #body="slotProps">
                <span v-if="slotProps.data.currency.toUpperCase() === 'USD'">
                  {{ formatMoney(slotProps.data.importTaxRatePercent) }}%
                </span>
                <span v-else class="quote-detail-page__price-unit">-</span>
              </template>
            </Column>
            <Column header="Chi phí làm hàng" style="width: 150px">
              <template #body="slotProps">
                <span
                  v-if="slotProps.data.currency.toUpperCase() === 'USD'"
                  class="quote-detail-page__price-cell"
                >
                  <span class="quote-detail-page__price-value">
                    {{ formatMoney(slotProps.data.processingCostVndPerKg) }}
                  </span>
                  <span class="quote-detail-page__price-unit">VNĐ/KG</span>
                </span>
                <span v-else class="quote-detail-page__price-unit">-</span>
              </template>
            </Column>
            <Column header="Ghi chú" style="width: 200px">
              <template #body="slotProps">
                <span v-if="slotProps.data.note" class="quote-detail-page__small-text">{{ slotProps.data.note }}</span>
                <span v-else class="quote-detail-page__price-unit">-</span>
              </template>
            </Column>
            <Column header="Chốt mua" style="width: 160px; text-align: left">
              <template #body="slotProps">
                <div style="display: flex; align-items: center; padding-left: 0.75rem; gap: 0.25rem; white-space: nowrap; width: 100%; min-height: 24px;">
                  <Checkbox
                    :model-value="Boolean(slotProps.data.purchaseMarkedAt)"
                    binary
                    :disabled="!canMarkPurchase || activeVersion?.status !== 'confirmed'"
                    @click="togglePurchase(slotProps.data)"
                  />
                  <div
                    v-if="slotProps.data.purchaseMarkedAt"
                    class="quote-detail-page__line-purchase-marked m-0"
                    style="display: inline-block; margin-left: 0.5rem;"
                  >
                    <span>Chốt: {{ formatOnlyDate(slotProps.data.purchaseMarkedAt) }}</span>
                  </div>
                </div>
              </template>
            </Column>
          </DataTable>
        </div>

        <!-- Market Notes Card -->
        <div class="quote-detail-page__card">
          <div class="quote-detail-page__section-header">
            <h3 class="quote-detail-page__section-title">
              <i class="pi pi-file-edit quote-detail-page__section-icon" style="margin-right: 0.5rem" />
              Ghi chú thị trường
            </h3>
            <Button
              v-if="canCreateNote && !isEditingNote && !isEditingRevisionId"
              label="Thêm"
              icon="pi pi-plus"
              size="small"
              @click="startAddNote"
            />
          </div>

          <div class="quote-detail-page__note-body" style="margin-top: 0.75rem">
            <!-- Edit mode (adding new note) -->
            <div v-if="isEditingNote" style="display: flex; flex-direction: column; gap: 0.75rem">
              <Editor
                v-model="editingContent"
                editor-style="height: 200px"
                placeholder="Nhập ghi chú thị trường định dạng rich text..."
              />
              <div class="quote-detail-page__note-actions">
                <Button
                  label="Hủy bỏ"
                  icon="pi pi-times"
                  severity="secondary"
                  outlined
                  @click="cancelEditNote"
                  :disabled="isSavingNote"
                />
                <Button
                  label="Lưu ghi chú"
                  icon="pi pi-save"
                  severity="primary"
                  @click="saveMarketNote"
                  :loading="isSavingNote"
                />
              </div>
              <div v-if="noteErrorMsg" class="quote-detail-page__field-error">
                {{ noteErrorMsg }}
              </div>
            </div>

            <!-- Read mode -->
            <div v-else>
              <div 
                v-if="note?.revisions && note.revisions.length > 0" 
                class="quote-detail-page__comments-list"
              >
                <div 
                  v-for="(rev, idx) in chronologicalRevisions" 
                  :key="rev.id"
                  class="quote-detail-page__comment-card"
                >
                  <!-- Edit mode for specific revision -->
                  <div v-if="isEditingRevisionId === rev.id" style="display: flex; flex-direction: column; gap: 0.75rem">
                    <Editor
                      v-model="editingRevisionContent"
                      editor-style="height: 150px"
                      placeholder="Chỉnh sửa nội dung ghi chú..."
                    />
                    <div class="quote-detail-page__note-actions">
                      <Button
                        label="Hủy"
                        icon="pi pi-times"
                        severity="secondary"
                        outlined
                        size="small"
                        @click="cancelEditRevision"
                        :disabled="isSavingNote"
                      />
                      <Button
                        label="Cập nhật"
                        icon="pi pi-save"
                        severity="primary"
                        size="small"
                        @click="saveRevision(rev.id)"
                        :loading="isSavingNote"
                      />
                    </div>
                  </div>

                  <!-- Read mode for specific revision -->
                  <div v-else>
                    <div class="quote-detail-page__comment-header">
                      <div class="quote-detail-page__comment-author-info">
                        <img
                          :src="getNoteAuthorAvatarUrl(rev)"
                          :alt="rev.authorName ? `Ảnh đại diện ${rev.authorName}` : 'Ảnh đại diện người viết'"
                          class="quote-detail-page__comment-avatar"
                        />
                        <div class="quote-detail-page__comment-meta-text">
                          <span class="quote-detail-page__comment-author">{{ rev.authorName || 'Hệ thống' }}</span>
                          <span class="quote-detail-page__comment-time">{{ formatDateTime(rev.createdAt) }}</span>
                        </div>
                      </div>
                      <div style="display: flex; align-items: center; gap: 0.5rem">
                        <span 
                          v-if="idx === chronologicalRevisions.length - 1" 
                          class="quote-detail-page__current-badge"
                        >
                          Hiện tại
                        </span>
                        <div v-if="canManageNoteRevision(rev)" class="quote-detail-page__comment-actions">
                          <Button
                            icon="pi pi-pencil"
                            severity="secondary"
                            text
                            rounded
                            size="small"
                            title="Sửa"
                            @click="startEditRevision(rev)"
                          />
                          <Button
                            icon="pi pi-trash"
                            severity="danger"
                            text
                            rounded
                            size="small"
                            title="Xóa"
                            @click="requestDeleteRevision(rev.id)"
                          />
                        </div>
                      </div>
                    </div>
                    <div 
                      class="quote-detail-page__comment-body quote-detail-page__note-html-content" 
                      v-html="rev.content" 
                    />
                  </div>
                </div>
              </div>
              <div v-else class="quote-detail-page__empty-hint" style="padding: 0.5rem 0">
                Chưa có ghi chú thị trường nào cho báo giá này.
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Cột phụ: Timeline lịch sử phiên bản -->
      <div class="quote-detail-page__timeline-sidebar">
        <div class="quote-detail-page__card">
          <h3 class="quote-detail-page__timeline-title">
            <i class="pi pi-history" />
            Lịch sử phiên bản
          </h3>
          
          <div class="quote-detail-page__timeline">
            <div
              v-for="v in sortedVersions"
              :key="v.id"
              class="quote-detail-page__timeline-item"
              :class="{ active: v.id === activeVersionId }"
              @click="activeVersionId = v.id"
            >
              <div class="quote-detail-page__timeline-dot" />
              <div class="quote-detail-page__timeline-header">
                <span>Phiên bản V{{ v.versionNumber }}</span>
                <span class="quote-detail-page__status-badge scale-75" :class="v.status">
                  {{ getVersionStatusLabel(v.status) }}
                </span>
              </div>
              <div class="quote-detail-page__timeline-date">
                Nhận ngày: {{ v.receivedDate }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Confirm Dialog -->
    <Dialog
      v-model:visible="showConfirmDialog"
      header="Xác nhận khóa phiên bản báo giá"
      :modal="true"
      :style="{ width: '450px' }"
    >
      <div style="display: flex; align-items: center; gap: 0.75rem">
        <i class="pi pi-exclamation-triangle quote-detail-page__warning-icon quote-detail-page__warning-icon--warning" />
        <span>
          Sau khi xác nhận, toàn bộ giá gốc và tỷ giá của
          <strong>Phiên bản #{{ activeVersion?.versionNumber }}</strong>
          sẽ bị khóa. Nếu đây là bản điều chỉnh, phiên bản đã xác nhận trước đó sẽ chuyển sang trạng thái
          <strong>Đã bị thay thế</strong>.
        </span>
      </div>
      <template #footer>
        <Button
          label="Hủy"
          icon="pi pi-times"
          severity="secondary"
          outlined
          @click="showConfirmDialog = false"
          :disabled="isConfirming"
        />
        <Button
          label="Xác nhận"
          icon="pi pi-check"
          severity="primary"
          @click="confirmQuoteVersion"
          :loading="isConfirming"
        />
      </template>
    </Dialog>

    <!-- Delete Draft Dialog -->
    <Dialog
      v-model:visible="showDeleteDraftDialog"
      header="Xóa bản nháp"
      :modal="true"
      :style="{ width: '450px' }"
    >
      <div style="display: flex; align-items: center; gap: 0.75rem">
        <i class="pi pi-exclamation-triangle quote-detail-page__warning-icon quote-detail-page__warning-icon--danger" />
        <span>
          Bản nháp sẽ bị xóa vĩnh viễn.
          <template v-if="sortedVersions.length === 1">
            Vì đây là bản nháp duy nhất, phiếu nháp cũng sẽ bị xóa.
          </template>
          <template v-else>
            Phiên bản đã xác nhận trước đó, nếu có, không bị ảnh hưởng.
          </template>
        </span>
      </div>
      <template #footer>
        <Button
          label="Hủy"
          icon="pi pi-times"
          severity="secondary"
          outlined
          :disabled="isConfirming"
          @click="showDeleteDraftDialog = false"
        />
        <Button
          label="Xóa bản nháp"
          icon="pi pi-trash"
          severity="danger"
          :loading="isConfirming"
          @click="deleteDraftVersionFromDetail"
        />
      </template>
    </Dialog>

    <!-- Purchase Dialog -->
    <Dialog
      v-model:visible="showPurchaseDialog"
      header="Xác nhận ngày chốt mua"
      :modal="true"
      :style="{ width: '450px' }"
    >
      <div class="quote-detail-page__purchase-dialog-content" style="display: flex; flex-direction: column; gap: 1rem; padding: 0.5rem 0; width: 100%;">
        <div class="quote-detail-page__purchase-dialog-field" style="display: flex; flex-direction: column; gap: 0.75rem; width: 100%;">
          <label class="quote-detail-page__subsection-title" style="display: block; margin-bottom: 0.25rem;">Ngày chốt mua</label>
          <DatePicker
            v-model="selectedPurchaseDate"
            dateFormat="yy-mm-dd"
            placeholder="YYYY-MM-DD"
            showIcon
            class="quote-detail-page__purchase-date-input"
          />
        </div>
      </div>
      <template #footer>
        <Button
          label="Hủy"
          icon="pi pi-times"
          severity="secondary"
          outlined
          @click="showPurchaseDialog = false"
        />
        <Button
          label="Xác nhận chốt"
          icon="pi pi-check"
          severity="primary"
          @click="confirmPurchase"
        />
      </template>
    </Dialog>

    <!-- View Revision Dialog -->
    <Dialog
      v-model:visible="showRevisionDialog"
      :header="'Xem phiên bản ghi chú #' + selectedRevision?.revisionNumber"
      :modal="true"
      :style="{ width: '600px' }"
    >
      <div v-if="selectedRevision" style="display: flex; flex-direction: column; gap: 0.75rem">
        <div class="quote-detail-page__revision-meta">
          <span>Người viết: <strong>{{ selectedRevision.authorName || 'Hệ thống' }}</strong></span>
          <span>Thời gian: <strong>{{ formatDateTime(selectedRevision.createdAt) }}</strong></span>
        </div>
        <div class="quote-detail-page__note-html-content quote-detail-page__note-html-content--scrollable" v-html="selectedRevision.content" />
      </div>
      <template #footer>
        <Button
          label="Đóng"
          icon="pi pi-times"
          severity="secondary"
          @click="showRevisionDialog = false"
        />
      </template>
    </Dialog>

    <!-- Delete Note Revision Dialog -->
    <Dialog
      :visible="pendingDeleteRevisionId !== null"
      header="Xóa ghi chú"
      :modal="true"
      :style="{ width: '400px' }"
      @update:visible="cancelDeleteRevision"
    >
      <p>Bạn có chắc chắn muốn xóa ghi chú này không?</p>
      <template #footer>
        <Button
          label="Hủy"
          icon="pi pi-times"
          severity="secondary"
          outlined
          data-testid="quote-detail-cancel-delete-revision"
          @click="cancelDeleteRevision"
        />
        <Button
          label="Xóa"
          icon="pi pi-trash"
          severity="danger"
          data-testid="quote-detail-confirm-delete-revision"
          @click="confirmDeleteRevision"
        />
      </template>
    </Dialog>
  </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import FileUpload from 'primevue/fileupload'
import Checkbox from 'primevue/checkbox'
import Dialog from 'primevue/dialog'
import Message from 'primevue/message'
import Editor from 'primevue/editor'
import DatePicker from 'primevue/datepicker'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'

import { useAuthStore } from '@/stores/auth.store'
import { usePermissionStore } from '@/stores/permission.store'
import { useQuoteDetail } from '@/composables/useQuoteDetail'
import AdminLayout from '@/layouts/AdminLayout.vue'
import type { QuoteLineDomain, QuoteNoteRevisionDomain } from '@/types/quotes'
import { getDefaultAvatarUrl } from '@/utils/default-avatars'

const route = useRoute()
const useRouterObj = useRouter()
const authStore = useAuthStore()
const permissionStore = usePermissionStore()

const quoteId = route.params.quoteId as string

const {
  quote,
  activeVersionId,
  isLoading,
  errorMsg,
  isConfirming,
  isFileUploading,
  sortedVersions,
  activeVersion,
  note,
  isSavingNote,
  noteErrorMsg,
  loadQuote,
  handleConfirm,
  handleDeleteDraftVersion,
  handleTogglePurchase,
  handleUploadSourceFile,
  getSourceFileDownloadUrl,
  handleUpdateNote,
  handleUpdateNoteRevision,
  handleDeleteNoteRevision,
} = useQuoteDetail(authStore.accessToken)

const showConfirmDialog = ref<boolean>(false)
const showDeleteDraftDialog = ref<boolean>(false)

// Permissions
const isAdminUser = computed(() => authStore.roles.includes('admin'))
const canMutateCurrentQuote = computed(() => {
  if (isAdminUser.value) {
    return true
  }

  return Boolean(quote.value?.createdById && quote.value.createdById === authStore.currentUser?.id)
})
const canUpdateQuote = computed(() => permissionStore.can('quotes.update') && canMutateCurrentQuote.value)
const canMarkPurchase = computed(() => permissionStore.can('quotes.mark_purchased') && canMutateCurrentQuote.value)
const canCreateNote = computed(() => permissionStore.can('quote_notes.create'))
const canUpdateNote = computed(() => permissionStore.can('quote_notes.update'))
const canManageNoteRevision = (revision: QuoteNoteRevisionDomain) => (
  canUpdateNote.value
  && (
    isAdminUser.value
    || Boolean(revision.authorId && revision.authorId === authStore.currentUser?.id)
  )
)
const getNoteAuthorAvatarUrl = (revision: QuoteNoteRevisionDomain) => (
  revision.authorAvatarUrl
  || getDefaultAvatarUrl(revision.authorId || revision.authorName || revision.id)
)

const getVersionStatusLabel = (status: string): string => {
  if (status === 'draft') return 'Bản nháp'
  if (status === 'confirmed') return 'Đã xác nhận'
  if (status === 'superseded') return 'Đã bị thay thế'
  return status
}

const lineGlobalSearch = ref<string>('')
const lineMaterialNameFilter = ref<string | null>(null)
const lineDeliveryMonthFilter = ref<string | null>(null)

const normalizeSearchText = (value: string | number | null | undefined) => {
  return String(value ?? '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim()
}

const formatDeliveryMonth = (value: string) => {
  if (!value) return ''
  const [year, month] = value.split('-')
  return month && year ? `${month}/${year}` : value
}

const lineMaterialNameOptions = computed(() => {
  const names = new Map<string, string>()
  for (const line of activeVersion.value?.lines ?? []) {
    names.set(line.materialName, line.materialName)
  }

  return Array.from(names.values())
    .sort((left, right) => left.localeCompare(right, 'vi'))
    .map((name) => ({ label: name, value: name }))
})

const lineDeliveryMonthOptions = computed(() => {
  const months = new Set<string>()
  for (const line of activeVersion.value?.lines ?? []) {
    months.add(line.deliveryMonth)
  }

  return Array.from(months)
    .sort((left, right) => left.localeCompare(right))
    .map((month) => ({ label: formatDeliveryMonth(month), value: month }))
})

const filteredQuoteLines = computed(() => {
  const search = normalizeSearchText(lineGlobalSearch.value)
  const selectedMaterialName = lineMaterialNameFilter.value
  const selectedDeliveryMonth = lineDeliveryMonthFilter.value

  return (activeVersion.value?.lines ?? []).filter((line) => {
    if (selectedMaterialName && line.materialName !== selectedMaterialName) {
      return false
    }

    if (selectedDeliveryMonth && line.deliveryMonth !== selectedDeliveryMonth) {
      return false
    }

    if (!search) {
      return true
    }

    const searchableText = [
      line.materialCode,
      line.materialName,
      line.currency,
      line.unit,
      formatDeliveryMonth(line.deliveryMonth),
      line.deliveryMonth,
      line.priceOriginal,
      line.priceConvertedVndPerKg,
      line.exchangeRate,
      line.exchangeRateSource,
    ]
      .map(normalizeSearchText)
      .join(' ')

    return searchableText.includes(search)
  })
})

const resetLineFilters = () => {
  lineGlobalSearch.value = ''
  lineMaterialNameFilter.value = null
  lineDeliveryMonthFilter.value = null
}

// Note handlers
const isEditingNote = ref<boolean>(false)
const editingContent = ref<string>('')
const isEditingRevisionId = ref<string | null>(null)
const editingRevisionContent = ref<string>('')

const chronologicalRevisions = computed(() => {
  if (!note.value || !Array.isArray(note.value.revisions)) {
    return []
  }
  return [...note.value.revisions].reverse()
})

const startAddNote = () => {
  editingContent.value = ''
  isEditingNote.value = true
  isEditingRevisionId.value = null
}

const cancelEditNote = () => {
  isEditingNote.value = false
  editingContent.value = ''
}

const saveMarketNote = async () => {
  try {
    await handleUpdateNote(quoteId, editingContent.value)
    isEditingNote.value = false
    editingContent.value = ''
  } catch {
    // handled by composable errorMsg
  }
}

const startEditRevision = (rev: any) => {
  isEditingRevisionId.value = rev.id
  editingRevisionContent.value = rev.content
  isEditingNote.value = false
}

const cancelEditRevision = () => {
  isEditingRevisionId.value = null
  editingRevisionContent.value = ''
}

const saveRevision = async (revId: string) => {
  try {
    await handleUpdateNoteRevision(quoteId, revId, editingRevisionContent.value)
    isEditingRevisionId.value = null
    editingRevisionContent.value = ''
  } catch {
    // handled by composable errorMsg
  }
}

// Trước đây dùng `confirm()` gốc của trình duyệt — vỡ giao diện dark mode
// và không nhất quán với các hành động xoá khác trong cùng trang (đều dùng
// Dialog PrimeVue riêng, ví dụ `showDeleteDraftDialog`), theo phản hồi
// người dùng ngày 22/08/2026.
const pendingDeleteRevisionId = ref<string | null>(null)

const requestDeleteRevision = (revId: string) => {
  pendingDeleteRevisionId.value = revId
}

const cancelDeleteRevision = () => {
  pendingDeleteRevisionId.value = null
}

const confirmDeleteRevision = async () => {
  const revId = pendingDeleteRevisionId.value
  if (!revId) {
    return
  }
  pendingDeleteRevisionId.value = null
  try {
    await handleDeleteNoteRevision(quoteId, revId)
  } catch {
    // handled by composable errorMsg
  }
}

// Revision viewer
const showRevisionDialog = ref<boolean>(false)
const selectedRevision = ref<any>(null)

const goBack = () => {
  useRouterObj.push('/quotes')
}

const editDraft = () => {
  if (!quote.value || !activeVersion.value) return
  useRouterObj.push(`/quotes/${quote.value.id}/versions/${activeVersion.value.id}/edit`)
}

const createNewVersion = () => {
  if (!quote.value) return
  useRouterObj.push(`/quotes/${quote.value.id}/versions/new`)
}

onMounted(() => {
  loadQuote(quoteId)
})

const onFileSelect = async (event: any) => {
  const file = event.files[0]
  if (!file) return
  try {
    await handleUploadSourceFile(file)
  } catch {
    // handled by composable errorMsg
  }
}

const confirmQuoteVersion = async () => {
  try {
    await handleConfirm()
    showConfirmDialog.value = false
  } catch {
    // handled by composable errorMsg
  }
}

const deleteDraftVersionFromDetail = async () => {
  try {
    const shouldGoBack = sortedVersions.value.length === 1
    await handleDeleteDraftVersion()
    showDeleteDraftDialog.value = false
    if (shouldGoBack) {
      useRouterObj.push('/quotes')
    }
  } catch {
    // handled by composable errorMsg
  }
}

const showPurchaseDialog = ref<boolean>(false)
const selectedPurchaseDate = ref<Date>(new Date())
const selectedLineForPurchase = ref<QuoteLineDomain | null>(null)

const togglePurchase = async (line: QuoteLineDomain) => {
  if (line.purchaseMarkedAt) {
    try {
      await handleTogglePurchase(line.id, true, null)
    } catch {
      // handled by composable errorMsg
    }
  } else {
    selectedLineForPurchase.value = line
    if (activeVersion.value && activeVersion.value.receivedDate) {
      selectedPurchaseDate.value = new Date(activeVersion.value.receivedDate)
    } else {
      selectedPurchaseDate.value = new Date()
    }
    showPurchaseDialog.value = true
  }
}

const confirmPurchase = async () => {
  if (!selectedLineForPurchase.value) return
  try {
    const tzOffset = selectedPurchaseDate.value.getTimezoneOffset() * 60000
    const localISOTime = new Date(selectedPurchaseDate.value.getTime() - tzOffset).toISOString()
    await handleTogglePurchase(selectedLineForPurchase.value.id, false, localISOTime)
    showPurchaseDialog.value = false
    selectedLineForPurchase.value = null
  } catch {
    // handled by composable errorMsg
  }
}

const downloadSourceFile = (version: any) => {
  const url = getSourceFileDownloadUrl(version)
  if (!url) return
  
  // Trigger browser download by creating temporary link
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', '')
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

// Helpers format
const formatMoney = (val: number | string | null): string => {
  if (val === null || val === undefined) return ''
  const num = Number(val)
  if (isNaN(num)) return ''
  return new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(num)
}

const formatDateTime = (val: string | null): string => {
  if (!val) return ''
  return new Date(val).toLocaleString('vi-VN')
}

const formatOnlyDate = (val: string | null): string => {
  if (!val) return ''
  const date = new Date(val)
  const dd = String(date.getDate()).padStart(2, '0')
  const mm = String(date.getMonth() + 1).padStart(2, '0')
  const yyyy = date.getFullYear()
  return `${dd}/${mm}/${yyyy}`
}
</script>
