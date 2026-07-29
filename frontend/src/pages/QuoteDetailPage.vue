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
          v-if="hasUpdatePermission"
          label="Tạo phiên bản mới"
          icon="pi pi-copy"
          @click="createNewVersion"
        />
        <Button
          v-if="hasUpdatePermission && activeVersion && activeVersion.status === 'draft'"
          label="Sửa bản nháp"
          icon="pi pi-pencil"
          outlined
          @click="editDraft"
        />
        <Button
          v-if="hasUpdatePermission && activeVersion && activeVersion.status === 'draft'"
          label="Xác nhận phiên bản"
          icon="pi pi-check"
          severity="primary"
          @click="showConfirmDialog = true"
        />
      </div>
    </div>

    <!-- Error message -->
    <div v-if="errorMsg" class="mb-4">
      <Message severity="error" @close="errorMsg = null">{{ errorMsg }}</Message>
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
              {{ activeVersion.status === 'draft' ? 'Bản nháp' : 'Đã xác nhận' }}
            </span>
          </div>

          <!-- Metadata Grid -->
          <div v-if="activeVersion" class="quote-detail-page__meta-grid">
            <div class="quote-detail-page__meta-item">
              <span>Ngày nhận báo giá</span>
              <strong>{{ activeVersion.receivedDate }}</strong>
            </div>
            <div class="quote-detail-page__meta-item">
              <span>Trạng thái nhập lùi</span>
              <strong>{{ activeVersion.isBackfilled ? 'Có (Nhập bù)' : 'Không' }}</strong>
            </div>
            <div v-if="activeVersion.isBackfilled" class="quote-detail-page__meta-item" style="grid-column: span 2">
              <span>Lý do nhập bù</span>
              <strong>{{ activeVersion.backfillReason }}</strong>
            </div>
            <div v-if="activeVersion.confirmedAt" class="quote-detail-page__meta-item">
              <span>Thời điểm xác nhận</span>
              <strong>{{ formatDateTime(activeVersion.confirmedAt) }}</strong>
            </div>
          </div>

          <!-- Source File Section -->
          <div v-if="activeVersion">
            <h4 class="font-semibold text-sm mb-2 text-gray-700">Tệp tin báo giá gốc</h4>
            
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
            <div v-else-if="activeVersion.status === 'draft' && hasUpdatePermission" class="quote-detail-page__file-upload-section">
              <i class="pi pi-cloud-upload text-3xl text-gray-400" />
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
            <div v-else class="text-sm text-gray-500 italic mb-4">
              Không có tệp tin đính kèm.
            </div>
          </div>

          <!-- Lines DataTable -->
          <h4 class="font-semibold text-sm mb-3 text-gray-700">Danh sách dòng vật tư</h4>
          <DataTable
            :value="activeVersion?.lines || []"
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
                {{ formatMoney(slotProps.data.priceOriginal) }}
                <span class="text-xs text-gray-500 ml-1">{{ slotProps.data.currency }}</span>
              </template>
            </Column>
            <Column field="unit" header="Đơn vị" style="width: 80px" />
            <Column header="Tháng giao" style="width: 110px">
              <template #body="slotProps">
                {{ slotProps.data.deliveryMonth.substring(0, 7) }}
              </template>
            </Column>
            <Column style="width: 140px;">
              <template #header>
                <div style="display: flex; flex-direction: column; line-height: 1.3;">
                  <span>Tỷ giá quy đổi</span>
                  <span class="text-xs text-gray-400 font-normal">(VNĐ/USD)</span>
                </div>
              </template>
              <template #body="slotProps">
                <div v-if="slotProps.data.currency.toUpperCase() === 'USD'">
                  <strong>{{ formatMoney(slotProps.data.exchangeRate) }}</strong>
                  <div class="text-xs text-gray-500">
                    {{ slotProps.data.exchangeRateSource }}
                    <span class="badge" v-if="slotProps.data.exchangeRateSourceMode === 'auto'">(Tự động)</span>
                    <span class="badge" v-else>(Nhập tay)</span>
                  </div>
                  <div v-if="slotProps.data.exchangeRateManualReason" class="text-xs text-orange-600 italic">
                    Lý do: {{ slotProps.data.exchangeRateManualReason }}
                  </div>
                </div>
                <span v-else class="text-xs text-gray-400">-</span>
              </template>
            </Column>
            <Column header="Giá quy đổi (VNĐ/KG)" style="width: 180px">
              <template #body="slotProps">
                <span class="font-bold text-primary">
                  {{ formatMoney(slotProps.data.priceConvertedVndPer_kg || slotProps.data.priceConvertedVndPerKg) }}
                </span>
                <div v-if="slotProps.data.currency.toUpperCase() === 'USD'" class="text-xs text-gray-500">
                  (Chi phí: {{ formatMoney(slotProps.data.conversionCostVndPerKg) }} VNĐ/KG)
                </div>
              </template>
            </Column>
            <Column header="Chốt mua" style="width: 160px; text-align: left">
              <template #body="slotProps">
                <div style="display: flex; align-items: center; padding-left: 0.75rem; gap: 0.25rem; white-space: nowrap; width: 100%; min-height: 24px;">
                  <Checkbox
                    :model-value="Boolean(slotProps.data.purchaseMarkedAt)"
                    binary
                    :disabled="!hasPurchasePermission || activeVersion?.status === 'draft'"
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
              <i class="pi pi-file-edit mr-2 text-primary" />
              Ghi chú thị trường
            </h3>
            <Button
              v-if="hasUpdatePermission && !isEditingNote && !isEditingRevisionId"
              label="Thêm"
              icon="pi pi-plus"
              size="small"
              @click="startAddNote"
            />
          </div>

          <div class="quote-detail-page__note-body mt-3">
            <!-- Edit mode (adding new note) -->
            <div v-if="isEditingNote" class="flex flex-column gap-3">
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
              <div v-if="noteErrorMsg" class="text-xs text-red-600">
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
                  <div v-if="isEditingRevisionId === rev.id" class="flex flex-column gap-3">
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
                        <div class="quote-detail-page__comment-avatar">
                          {{ rev.authorName ? rev.authorName.charAt(0).toUpperCase() : 'H' }}
                        </div>
                        <div class="quote-detail-page__comment-meta-text">
                          <span class="quote-detail-page__comment-author">{{ rev.authorName || 'Hệ thống' }}</span>
                          <span class="quote-detail-page__comment-time">{{ formatDateTime(rev.createdAt) }}</span>
                        </div>
                      </div>
                      <div class="flex align-items-center gap-2">
                        <span 
                          v-if="idx === chronologicalRevisions.length - 1" 
                          class="quote-detail-page__current-badge"
                        >
                          Hiện tại
                        </span>
                        <div v-if="hasUpdatePermission" class="quote-detail-page__comment-actions">
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
                            @click="confirmDeleteRevision(rev.id)"
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
              <div v-else class="text-gray-500 italic text-sm py-2">
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
                  {{ v.status === 'draft' ? 'Nháp' : 'Chốt' }}
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
      <div class="flex align-items-center gap-3">
        <i class="pi pi-exclamation-triangle text-orange-500 text-3xl" />
        <span>After confirmation, all raw prices and exchange rates of <strong>Version #{{ activeVersion?.versionNumber }}</strong> will be locked and CANNOT be edited. Are you sure you want to proceed?</span>
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

    <!-- Purchase Dialog -->
    <Dialog
      v-model:visible="showPurchaseDialog"
      header="Xác nhận ngày chốt mua"
      :modal="true"
      :style="{ width: '450px' }"
    >
      <div class="quote-detail-page__purchase-dialog-content" style="display: flex; flex-direction: column; gap: 1rem; padding: 0.5rem 0; width: 100%;">
        <div class="quote-detail-page__purchase-dialog-field" style="display: flex; flex-direction: column; gap: 0.75rem; width: 100%;">
          <label class="text-sm font-semibold text-gray-700" style="display: block; margin-bottom: 0.25rem;">Ngày chốt mua</label>
          <DatePicker
            v-model="selectedPurchaseDate"
            dateFormat="yy-mm-dd"
            placeholder="YYYY-MM-DD"
            showIcon
            class="w-full"
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
      <div v-if="selectedRevision" class="flex flex-column gap-3">
        <div class="text-xs text-gray-500 bg-gray-50 p-2 border-round">
          <span>Người viết: <strong>{{ selectedRevision.authorName || 'Hệ thống' }}</strong></span>
          <span class="ml-4">Thời gian: <strong>{{ formatDateTime(selectedRevision.createdAt) }}</strong></span>
        </div>
        <div class="quote-detail-page__note-html-content max-h-20rem overflow-y-auto p-2 border-1 border-gray-200 border-round" v-html="selectedRevision.content" />
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

import { useAuthStore } from '@/stores/auth.store'
import { usePermissionStore } from '@/stores/permission.store'
import { useQuoteDetail } from '@/composables/useQuoteDetail'
import AdminLayout from '@/layouts/AdminLayout.vue'
import type { QuoteLineDomain } from '@/types/quotes'

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
  isNoteLoading,
  isSavingNote,
  noteErrorMsg,
  loadQuote,
  handleConfirm,
  handleTogglePurchase,
  handleUploadSourceFile,
  getSourceFileDownloadUrl,
  handleUpdateNote,
  handleUpdateNoteRevision,
  handleDeleteNoteRevision,
} = useQuoteDetail(authStore.accessToken)

const showConfirmDialog = ref<boolean>(false)

// Permissions
const hasUpdatePermission = computed(() => permissionStore.can('quotes.update'))
const hasPurchasePermission = computed(() => permissionStore.can('quotes.mark_purchased'))

// Note handlers
const isEditingNote = ref<boolean>(false)
const editingContent = ref<string>('')
const isEditingRevisionId = ref<string | null>(null)
const editingRevisionContent = ref<string>('')

const latestRevision = computed(() => {
  if (!note.value || !Array.isArray(note.value.revisions) || note.value.revisions.length === 0) {
    return null
  }
  return note.value.revisions[0]
})

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

const confirmDeleteRevision = async (revId: string) => {
  if (confirm('Bạn có chắc chắn muốn xóa ghi chú này không?')) {
    try {
      await handleDeleteNoteRevision(quoteId, revId)
    } catch {
      // handled by composable errorMsg
    }
  }
}

// Revision viewer
const showRevisionDialog = ref<boolean>(false)
const selectedRevision = ref<any>(null)

const viewRevision = (revision: any) => {
  selectedRevision.value = revision
  showRevisionDialog.value = true
}

const goBack = () => {
  useRouterObj.push('/')
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
    if (quote.value && quote.value.receivedDate) {
      selectedPurchaseDate.value = new Date(quote.value.receivedDate)
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

const formatDateTimeShort = (val: string | null): string => {
  if (!val) return ''
  const date = new Date(val)
  const dd = String(date.getDate()).padStart(2, '0')
  const mm = String(date.getMonth() + 1).padStart(2, '0')
  const hh = String(date.getHours()).padStart(2, '0')
  const min = String(date.getMinutes()).padStart(2, '0')
  return `${dd}/${mm} ${hh}:${min}`
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
