<template>
  <AdminLayout section-label="Danh mục" title="Loại vật tư">
    <div class="material-types-page">
      <section class="material-types-page__header">
        <div class="material-types-page__filters">
          <label class="material-types-page__filter-field">
            <span class="material-types-page__filter-label">Tìm kiếm</span>
            <InputText
              v-model="lazyParams.search"
              class="material-types-page__input-search"
              placeholder="Mã hoặc tên loại vật tư..."
              @input="onSearchInput"
            />
          </label>

          <label class="material-types-page__filter-field">
            <span class="material-types-page__filter-label">Trạng thái</span>
            <Select
              v-model="lazyParams.status"
              :options="statusFilterOptions"
              class="material-types-page__status-filter"
              option-label="label"
              option-value="value"
              placeholder="Tất cả"
              show-clear
              @change="onFilterChange"
            />
          </label>
        </div>

        <div class="material-types-page__actions">
          <Button
            v-if="permissionStore.can('material_types.import')"
            icon="pi pi-upload"
            label="Import CSV"
            severity="secondary"
            @click="openImportDialog"
          />
          <Button
            v-if="permissionStore.can('material_types.create')"
            icon="pi pi-plus"
            label="Thêm loại vật tư"
            @click="openCreateDialog"
          />
        </div>
      </section>

      <div v-if="generalError" class="material-types-page__general-error">
        <i class="pi pi-exclamation-triangle" aria-hidden="true" />
        <span>{{ generalError }}</span>
      </div>

      <section class="material-types-page__table-wrapper">
        <DataTable
          :loading="loading"
          :rows="lazyParams.limit"
          :rows-per-page-options="[10, 20, 30, 50]"
          :total-records="totalMaterialTypes"
          :value="materialTypes"
          current-page-report-template="Hiển thị từ {first} đến {last} trên tổng số {totalRecords} dòng"
          data-key="id"
          lazy
          paginator
          paginator-template="RowsPerPageDropdown FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink CurrentPageReport"
          responsive-layout="scroll"
          @page="onPageChange"
          @sort="onSortChange"
        >
          <Column field="code" header="Mã" sortable />
          <Column field="name" header="Tên loại vật tư" sortable />
          <Column field="status" header="Trạng thái" sortable>
            <template #body="{ data }">
              <Tag
                :severity="data.status === 'active' ? 'success' : 'secondary'"
                :value="formatStatus(data.status)"
              />
            </template>
          </Column>
          <Column field="note" header="Ghi chú" />
          <Column header="Thao tác" class="material-types-page__actions-column">
            <template #body="{ data }">
              <div class="material-types-page__row-actions">
                <Button
                  v-if="permissionStore.can('material_types.update')"
                  aria-label="Chỉnh sửa"
                  icon="pi pi-pencil"
                  rounded
                  severity="secondary"
                  text
                  @click="openEditDialog(data)"
                />
                <Button
                  v-if="permissionStore.can('material_types.delete')"
                  aria-label="Xóa"
                  icon="pi pi-trash"
                  rounded
                  severity="danger"
                  text
                  @click="openDeleteDialog(data)"
                />
              </div>
            </template>
          </Column>
        </DataTable>
      </section>

      <Dialog
        v-model:visible="importDialogVisible"
        class="material-types-page__dialog"
        header="Import loại vật tư"
        modal
      >
        <div class="material-types-page__form">
          <div v-if="importError" class="material-types-page__submit-error">
            {{ importError }}
          </div>
          <div class="material-types-page__dialog-actions">
            <Button
              icon="pi pi-download"
              label="Tải template CSV"
              severity="secondary"
              text
              @click="downloadTemplate"
            />
          </div>
          <FileUpload
            accept=".csv,text/csv"
            choose-label="Chọn file CSV"
            custom-upload
            mode="basic"
            name="file"
            :auto="true"
            :disabled="uploadingImport"
            @uploader="handleImportUpload"
          />
          <div
            v-if="importJob"
            class="material-types-page__import-status"
            :class="{
              'material-types-page__import-status--failed':
                importJob.status === 'failed',
            }"
          >
            <strong>{{ formatImportStatus(importJob.status) }}</strong>
            <span v-if="importJob.errorSummary">
              {{ importJob.errorSummary }}
            </span>
            <span>
              {{ importJob.processedRows }} thành công,
              {{ importJob.failedRows }} lỗi trên {{ importJob.totalRows }} dòng
            </span>
            <ProgressBar :value="getImportProgress()" />
            <Button
              v-if="importJob.failedRows > 0"
              icon="pi pi-download"
              label="Tải file lỗi"
              severity="secondary"
              text
              @click="downloadErrorFile"
            />
          </div>
        </div>
      </Dialog>

      <Dialog
        v-model:visible="createDialogVisible"
        class="material-types-page__dialog"
        header="Thêm loại vật tư"
        modal
      >
        <form class="material-types-page__form" @submit.prevent="submitCreate">
          <div v-if="submitError" class="material-types-page__submit-error">
            {{ submitError }}
          </div>

          <div class="material-types-page__form-field">
            <label for="create-code" class="material-types-page__form-label required">
              Mã loại vật tư
            </label>
            <InputText
              id="create-code"
              v-model="createCode"
              v-bind="createCodeProps"
              fluid
              placeholder="Ví dụ: CORN"
            />
            <small class="material-types-page__field-error">{{ createErrors.code }}</small>
          </div>

          <div class="material-types-page__form-field">
            <label for="create-name" class="material-types-page__form-label required">
              Tên loại vật tư
            </label>
            <InputText
              id="create-name"
              v-model="createName"
              v-bind="createNameProps"
              fluid
              placeholder="Ví dụ: Ngô"
            />
            <small class="material-types-page__field-error">{{ createErrors.name }}</small>
          </div>

          <div class="material-types-page__form-field">
            <label for="create-status" class="material-types-page__form-label required">
              Trạng thái
            </label>
            <Select
              id="create-status"
              v-model="createStatus"
              v-bind="createStatusProps"
              :options="catalogStatusOptions"
              fluid
              option-label="label"
              option-value="value"
            />
            <small class="material-types-page__field-error">{{ createErrors.status }}</small>
          </div>

          <div class="material-types-page__form-field">
            <label for="create-note" class="material-types-page__form-label">Ghi chú</label>
            <Textarea
              id="create-note"
              v-model="createNote"
              v-bind="createNoteProps"
              auto-resize
              rows="3"
              fluid
              placeholder="Thông tin bổ sung..."
            />
            <small class="material-types-page__field-error">{{ createErrors.note }}</small>
          </div>

          <div class="material-types-page__dialog-actions">
            <Button
              label="Hủy"
              severity="secondary"
              text
              @click="createDialogVisible = false"
            />
            <Button label="Lưu lại" type="submit" :loading="createFormSubmitting" />
          </div>
        </form>
      </Dialog>

      <Dialog
        v-model:visible="editDialogVisible"
        class="material-types-page__dialog"
        header="Chỉnh sửa loại vật tư"
        modal
      >
        <form class="material-types-page__form" @submit.prevent="submitEdit">
          <div v-if="submitError" class="material-types-page__submit-error">
            {{ submitError }}
          </div>

          <div class="material-types-page__form-field">
            <label for="edit-code" class="material-types-page__form-label required">
              Mã loại vật tư
            </label>
            <InputText
              id="edit-code"
              v-model="editCode"
              v-bind="editCodeProps"
              fluid
            />
            <small class="material-types-page__field-error">{{ editErrors.code }}</small>
          </div>

          <div class="material-types-page__form-field">
            <label for="edit-name" class="material-types-page__form-label required">
              Tên loại vật tư
            </label>
            <InputText
              id="edit-name"
              v-model="editName"
              v-bind="editNameProps"
              fluid
            />
            <small class="material-types-page__field-error">{{ editErrors.name }}</small>
          </div>

          <div class="material-types-page__form-field">
            <label for="edit-status" class="material-types-page__form-label required">
              Trạng thái
            </label>
            <Select
              id="edit-status"
              v-model="editStatus"
              v-bind="editStatusProps"
              :options="catalogStatusOptions"
              fluid
              option-label="label"
              option-value="value"
            />
            <small class="material-types-page__field-error">{{ editErrors.status }}</small>
          </div>

          <div class="material-types-page__form-field">
            <label for="edit-note" class="material-types-page__form-label">Ghi chú</label>
            <Textarea
              id="edit-note"
              v-model="editNote"
              v-bind="editNoteProps"
              auto-resize
              rows="3"
              fluid
            />
            <small class="material-types-page__field-error">{{ editErrors.note }}</small>
          </div>

          <div class="material-types-page__dialog-actions">
            <Button
              label="Hủy"
              severity="secondary"
              text
              @click="editDialogVisible = false"
            />
            <Button label="Cập nhật" type="submit" :loading="editFormSubmitting" />
          </div>
        </form>
      </Dialog>

      <Dialog
        v-model:visible="deleteDialogVisible"
        class="material-types-page__dialog"
        header="Xác nhận xóa"
        modal
      >
        <div class="material-types-page__delete-message">
          <p>
            Bạn có chắc chắn muốn xóa loại vật tư
            <strong>{{ selectedMaterialType?.name }}</strong> không?
          </p>
          <div v-if="submitError" class="material-types-page__submit-error">
            {{ submitError }}
          </div>
        </div>

        <div class="material-types-page__dialog-actions">
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
            @click="submitDelete"
          />
        </div>
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
import FileUpload from 'primevue/fileupload'
import InputText from 'primevue/inputtext'
import ProgressBar from 'primevue/progressbar'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import Textarea from 'primevue/textarea'

import {
  catalogStatusOptions,
  useMaterialTypesPage,
} from '@/composables/useMaterialTypesPage'
import { useCatalogImport } from '@/composables/useCatalogImport'
import AdminLayout from '@/layouts/AdminLayout.vue'
import { usePermissionStore } from '@/stores/permission.store'
import type { CatalogStatus } from '@/types/materials'

const permissionStore = usePermissionStore()
const statusFilterOptions = [
  { label: 'Tất cả', value: '' },
  ...catalogStatusOptions,
]

const {
  materialTypes,
  totalMaterialTypes,
  loading,
  generalError,
  submitError,
  selectedMaterialType,
  createDialogVisible,
  editDialogVisible,
  deleteDialogVisible,
  isDeleting,
  lazyParams,
  fetchMaterialTypes,
  openCreateDialog,
  openEditDialog,
  openDeleteDialog,
  submitDelete,
  createCode,
  createCodeProps,
  createName,
  createNameProps,
  createStatus,
  createStatusProps,
  createNote,
  createNoteProps,
  createErrors,
  createFormSubmitting,
  submitCreate,
  editCode,
  editCodeProps,
  editName,
  editNameProps,
  editStatus,
  editStatusProps,
  editNote,
  editNoteProps,
  editErrors,
  editFormSubmitting,
  submitEdit,
} = useMaterialTypesPage()

const {
  importDialogVisible,
  importJob,
  importError,
  uploadingImport,
  openImportDialog,
  handleImportUpload,
  downloadTemplate,
  downloadErrorFile,
} = useCatalogImport('material_types', fetchMaterialTypes)

let searchTimeout: ReturnType<typeof window.setTimeout> | null = null
function onSearchInput() {
  if (searchTimeout) {
    window.clearTimeout(searchTimeout)
  }
  searchTimeout = window.setTimeout(() => {
    lazyParams.offset = 0
    fetchMaterialTypes()
  }, 400)
}

function onFilterChange() {
  lazyParams.offset = 0
  fetchMaterialTypes()
}

function onPageChange(event: { first: number; rows: number }) {
  lazyParams.offset = event.first
  lazyParams.limit = event.rows
  fetchMaterialTypes()
}

function onSortChange(event: {
  sortField?: string | ((item: unknown) => string)
  sortOrder?: number | null
}) {
  const sortField =
    typeof event.sortField === 'string' ? event.sortField : undefined
  lazyParams.sort_by = sortField || 'code'
  lazyParams.sort_order = event.sortOrder === 1 ? 'asc' : 'desc'
  lazyParams.offset = 0
  fetchMaterialTypes()
}

function formatStatus(status: CatalogStatus) {
  return status === 'active' ? 'Đang dùng' : 'Ngừng dùng'
}

function formatImportStatus(status: string) {
  if (status === 'completed') return 'Hoàn tất'
  if (status === 'failed') return 'Thất bại'
  if (status === 'processing') return 'Đang xử lý'
  return 'Đang chờ'
}

function getImportProgress() {
  if (!importJob.value?.totalRows) return 0
  return Math.min(
    100,
    Math.round(
      ((importJob.value.processedRows + importJob.value.failedRows) /
        importJob.value.totalRows) *
        100,
    ),
  )
}

onMounted(fetchMaterialTypes)
</script>
