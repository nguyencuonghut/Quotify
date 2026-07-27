<template>
  <AdminLayout section-label="Quản lý hệ thống" title="Quản lý tập tin">
    <div class="files-page">
      <!-- Top Filters and Actions -->
      <section class="files-page__header">
        <div class="files-page__filters">
          <label class="files-page__filter-field">
            <span class="files-page__filter-label">Tìm kiếm tập tin</span>
            <InputText
              v-model="lazyParams.search"
              placeholder="Nhập tên tập tin..."
              class="files-page__input-search"
              @input="onSearchInput"
            />
          </label>
        </div>

        <div class="files-page__actions">
          <Button
            v-if="permissionStore.can('files.upload')"
            label="Tải tập tin lên"
            icon="pi pi-upload"
            @click="openUploadDialog"
          />
        </div>
      </section>

      <!-- Main Data Table -->
      <div v-if="generalError" class="files-page__general-error">
        <i class="pi pi-exclamation-triangle" aria-hidden="true" />
        <span>{{ generalError }}</span>
      </div>

      <section class="files-page__table-wrapper">
        <DataTable
          :loading="loading"
          :rows="lazyParams.limit"
          :total-records="totalFiles"
          :value="files"
          data-key="id"
          lazy
          paginator
          current-page-report-template="Hiển thị từ {first} đến {last} trên tổng số {totalRecords} dòng"
          :rows-per-page-options="[10, 20, 30, 50]"
          paginator-template="RowsPerPageDropdown FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink CurrentPageReport"
          responsive-layout="scroll"
          @page="onPageChange"
        >
          <template #empty>
            <div class="files-page__empty-state">
              Không tìm thấy tập tin nào.
            </div>
          </template>

          <Column field="filename" header="Tên tập tin" />
          <Column field="contentType" header="Định dạng" />

          <Column field="sizeBytes" header="Kích thước">
            <template #body="{ data }">
              {{ formatBytes(data.sizeBytes) }}
            </template>
          </Column>

          <Column field="isPublic" header="Quyền riêng tư">
            <template #body="{ data }">
              <Tag
                :severity="data.isPublic ? 'success' : 'secondary'"
                :value="data.isPublic ? 'Công khai' : 'Riêng tư'"
              />
            </template>
          </Column>

          <Column field="createdAt" header="Ngày tạo">
            <template #body="{ data }">
              {{ formatDate(data.createdAt) }}
            </template>
          </Column>

          <Column header="Thao tác" class="files-page__actions-column">
            <template #body="{ data }">
              <div class="files-page__row-actions">
                <Button
                  v-if="permissionStore.can('files.read')"
                  icon="pi pi-download"
                  severity="secondary"
                  text
                  rounded
                  aria-label="Tải xuống"
                  @click="downloadFileContent(data)"
                />
                <Button
                  v-if="permissionStore.can('files.delete')"
                  icon="pi pi-trash"
                  severity="danger"
                  text
                  rounded
                  aria-label="Xóa"
                  @click="confirmDelete(data)"
                />
              </div>
            </template>
          </Column>
        </DataTable>
      </section>

      <!-- Upload File Dialog -->
      <Dialog
        v-model:visible="uploadDialogVisible"
        header="Tải tập tin lên"
        modal
        class="files-page__dialog"
      >
        <div class="files-page__upload-form">
          <div v-if="uploadError" class="files-page__submit-error">
            {{ uploadError }}
          </div>

          <div class="files-page__form-field">
            <label class="files-page__form-label required">Chọn tập tin</label>
            <FileUpload
              mode="basic"
              name="file"
              accept="*"
              :max-file-size="52428800"
              custom-upload
              auto
              fluid
              choose-label="Chọn tập tin"
              @select="onFileSelect"
            />
            <div v-if="uploadFileObject" class="files-page__selected-file">
              <i class="pi pi-file" />
              <span
                >{{ uploadFileObject.name }} ({{
                  formatBytes(uploadFileObject.size)
                }})</span
              >
            </div>
          </div>

          <div class="files-page__form-field files-page__form-field--checkbox">
            <Checkbox id="is-public-upload" v-model="isPublic" binary />
            <label for="is-public-upload" class="files-page__checkbox-label">
              Tập tin công khai (ai cũng có thể xem trực tiếp)
            </label>
          </div>

          <div class="files-page__dialog-actions">
            <Button
              label="Hủy"
              severity="secondary"
              text
              @click="uploadDialogVisible = false"
            />
            <Button
              label="Tải lên"
              :loading="isUploading"
              :disabled="!uploadFileObject"
              @click="handleUpload"
            />
          </div>
        </div>
      </Dialog>

      <!-- Delete Confirmation Dialog -->
      <Dialog
        v-model:visible="deleteDialogVisible"
        header="Xác nhận xóa"
        modal
        class="files-page__dialog"
      >
        <div class="files-page__delete-message">
          <p>
            Bạn có chắc chắn muốn xóa tập tin
            <strong>{{ selectedFile?.filename }}</strong> không? Hành động này
            sẽ xóa vĩnh viễn tập tin khỏi hệ thống lưu trữ MinIO.
          </p>
          <div v-if="deleteError" class="files-page__submit-error">
            {{ deleteError }}
          </div>
        </div>

        <div class="files-page__dialog-actions">
          <Button
            label="Hủy"
            severity="secondary"
            text
            :disabled="isDeleting"
            @click="deleteDialogVisible = false"
          />
          <Button
            label="Xác nhận xóa"
            severity="danger"
            :loading="isDeleting"
            @click="handleDelete"
          />
        </div>
      </Dialog>
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Dialog from 'primevue/dialog'
import FileUpload from 'primevue/fileupload'
import InputText from 'primevue/inputtext'
import Tag from 'primevue/tag'

import { useFilesPage } from '@/composables/useFilesPage'
import AdminLayout from '@/layouts/AdminLayout.vue'
import { usePermissionStore } from '@/stores/permission.store'

const permissionStore = usePermissionStore()

const {
  files,
  totalFiles,
  loading,
  generalError,
  lazyParams,
  uploadDialogVisible,
  deleteDialogVisible,
  selectedFile,
  isUploading,
  isDeleting,
  uploadError,
  deleteError,
  isPublic,
  uploadFileObject,
  fetchFiles,
  onSearchChange,
  onPageChange,
  openUploadDialog,
  onFileSelect,
  handleUpload,
  confirmDelete,
  handleDelete,
  downloadFileContent,
} = useFilesPage()

// Debounced search input
let searchTimeout: ReturnType<typeof window.setTimeout> | null = null
function onSearchInput() {
  if (searchTimeout) {
    window.clearTimeout(searchTimeout)
  }
  searchTimeout = window.setTimeout(() => {
    onSearchChange(lazyParams.search || '')
  }, 400)
}

function formatBytes(bytes: number, decimals = 2) {
  if (!bytes) return '0 Bytes'
  const k = 1024
  const dm = decimals < 0 ? 0 : decimals
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`
}

function formatDate(date: Date) {
  return date.toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' })
}

onMounted(async () => {
  await fetchFiles()
})
</script>
