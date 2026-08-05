<template>
  <AdminLayout section-label="Danh mục" title="Vật tư">
    <div class="materials-page">
      <section class="materials-page__header">
        <div class="materials-page__filters">
          <label class="materials-page__filter-field">
            <span class="materials-page__filter-label">Tìm kiếm</span>
            <InputText
              v-model="lazyParams.search"
              class="materials-page__input-search"
              placeholder="Mã hoặc tên vật tư..."
              @input="onSearchInput"
            />
          </label>

          <label class="materials-page__filter-field">
            <span class="materials-page__filter-label">Loại vật tư</span>
            <Select
              v-model="lazyParams.material_type_id"
              :options="materialTypes"
              class="materials-page__type-filter"
              option-label="name"
              option-value="id"
              placeholder="Tất cả"
              show-clear
              @change="onFilterChange"
            />
          </label>

          <label class="materials-page__filter-field">
            <span class="materials-page__filter-label">Trạng thái</span>
            <Select
              v-model="lazyParams.status"
              :options="statusFilterOptions"
              class="materials-page__status-filter"
              option-label="label"
              option-value="value"
              placeholder="Tất cả"
              show-clear
              @change="onFilterChange"
            />
          </label>
        </div>

        <div class="materials-page__actions">
          <Button
            v-if="permissionStore.can('materials.import')"
            icon="pi pi-upload"
            label="Import CSV"
            severity="secondary"
            @click="openImportDialog"
          />
          <Button
            v-if="permissionStore.can('materials.create')"
            icon="pi pi-plus"
            label="Thêm vật tư"
            @click="openCreateDialog"
          />
        </div>
      </section>

      <div v-if="generalError" class="materials-page__general-error">
        <i class="pi pi-exclamation-triangle" aria-hidden="true" />
        <span>{{ generalError }}</span>
      </div>

      <section class="materials-page__table-wrapper">
        <DataTable
          :loading="loading"
          :rows="lazyParams.limit"
          :rows-per-page-options="[10, 20, 30, 50]"
          :total-records="totalMaterials"
          :value="materials"
          current-page-report-template="Hiển thị từ {first} đến {last} trên tổng số {totalRecords} dòng"
          data-key="id"
          lazy
          paginator
          paginator-template="RowsPerPageDropdown FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink CurrentPageReport"
          responsive-layout="scroll"
          @page="onPageChange"
          @sort="onSortChange"
        >
          <Column field="code" header="Mã vật tư" sortable />
          <Column field="name" header="Tên vật tư" sortable />
          <Column field="materialTypeName" header="Loại vật tư">
            <template #body="{ data }">
              <span>{{ data.materialTypeName }}</span>
            </template>
          </Column>
          <Column field="status" header="Trạng thái" sortable>
            <template #body="{ data }">
              <Tag
                :severity="data.status === 'active' ? 'success' : 'secondary'"
                :value="formatStatus(data.status)"
              />
            </template>
          </Column>
          <Column field="note" header="Ghi chú" />
          <Column header="Thao tác" class="materials-page__actions-column">
            <template #body="{ data }">
              <div class="materials-page__row-actions">
                <Button
                  v-if="permissionStore.can('materials.update')"
                  aria-label="Chỉnh sửa"
                  icon="pi pi-pencil"
                  rounded
                  severity="secondary"
                  text
                  @click="openEditDialog(data)"
                />
                <Button
                  v-if="permissionStore.can('materials.delete')"
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
        class="materials-page__dialog"
        header="Import vật tư"
        modal
      >
        <div class="materials-page__form">
          <div v-if="importError" class="materials-page__submit-error">
            {{ importError }}
          </div>
          <div class="materials-page__dialog-actions">
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
            class="materials-page__import-status"
            :class="{
              'materials-page__import-status--failed':
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
        class="materials-page__dialog"
        header="Thêm vật tư"
        modal
      >
        <form class="materials-page__form" @submit.prevent="submitCreate">
          <div v-if="submitError" class="materials-page__submit-error">
            {{ submitError }}
          </div>

          <div class="materials-page__form-field">
            <label for="create-material-code" class="materials-page__form-label required">
              Mã vật tư
            </label>
            <InputText
              id="create-material-code"
              v-model="createCode"
              v-bind="createCodeProps"
              fluid
              placeholder="Ví dụ: CORN-01"
            />
            <small class="materials-page__field-error">{{ createErrors.code }}</small>
          </div>

          <div class="materials-page__form-field">
            <label for="create-material-name" class="materials-page__form-label required">
              Tên vật tư
            </label>
            <InputText
              id="create-material-name"
              v-model="createName"
              v-bind="createNameProps"
              fluid
              placeholder="Ví dụ: Ngô hạt"
            />
            <small class="materials-page__field-error">{{ createErrors.name }}</small>
          </div>

          <div class="materials-page__form-field">
            <label for="create-material-type" class="materials-page__form-label required">
              Loại vật tư
            </label>
            <Select
              id="create-material-type"
              v-model="createMaterialTypeId"
              v-bind="createMaterialTypeIdProps"
              :options="materialTypes"
              fluid
              option-label="name"
              option-value="id"
              placeholder="Chọn loại vật tư"
            />
            <small class="materials-page__field-error">
              {{ createErrors.materialTypeId }}
            </small>
          </div>

          <div class="materials-page__form-field">
            <label for="create-material-status" class="materials-page__form-label required">
              Trạng thái
            </label>
            <Select
              id="create-material-status"
              v-model="createStatus"
              v-bind="createStatusProps"
              :options="catalogStatusOptions"
              fluid
              option-label="label"
              option-value="value"
            />
            <small class="materials-page__field-error">{{ createErrors.status }}</small>
          </div>

          <div class="materials-page__form-field">
            <label for="create-material-note" class="materials-page__form-label">
              Ghi chú
            </label>
            <Textarea
              id="create-material-note"
              v-model="createNote"
              v-bind="createNoteProps"
              auto-resize
              rows="3"
              fluid
              placeholder="Thông tin bổ sung..."
            />
            <small class="materials-page__field-error">{{ createErrors.note }}</small>
          </div>

          <div class="materials-page__dialog-actions">
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
        class="materials-page__dialog"
        header="Chỉnh sửa vật tư"
        modal
      >
        <form class="materials-page__form" @submit.prevent="submitEdit">
          <div v-if="submitError" class="materials-page__submit-error">
            {{ submitError }}
          </div>

          <div class="materials-page__form-field">
            <label for="edit-material-code" class="materials-page__form-label required">
              Mã vật tư
            </label>
            <InputText
              id="edit-material-code"
              v-model="editCode"
              v-bind="editCodeProps"
              fluid
            />
            <small class="materials-page__field-error">{{ editErrors.code }}</small>
          </div>

          <div class="materials-page__form-field">
            <label for="edit-material-name" class="materials-page__form-label required">
              Tên vật tư
            </label>
            <InputText
              id="edit-material-name"
              v-model="editName"
              v-bind="editNameProps"
              fluid
            />
            <small class="materials-page__field-error">{{ editErrors.name }}</small>
          </div>

          <div class="materials-page__form-field">
            <label for="edit-material-type" class="materials-page__form-label required">
              Loại vật tư
            </label>
            <Select
              id="edit-material-type"
              v-model="editMaterialTypeId"
              v-bind="editMaterialTypeIdProps"
              :options="materialTypes"
              fluid
              option-label="name"
              option-value="id"
              placeholder="Chọn loại vật tư"
            />
            <small class="materials-page__field-error">
              {{ editErrors.materialTypeId }}
            </small>
          </div>

          <div class="materials-page__form-field">
            <label for="edit-material-status" class="materials-page__form-label required">
              Trạng thái
            </label>
            <Select
              id="edit-material-status"
              v-model="editStatus"
              v-bind="editStatusProps"
              :options="catalogStatusOptions"
              fluid
              option-label="label"
              option-value="value"
            />
            <small class="materials-page__field-error">{{ editErrors.status }}</small>
          </div>

          <div class="materials-page__form-field">
            <label for="edit-material-note" class="materials-page__form-label">
              Ghi chú
            </label>
            <Textarea
              id="edit-material-note"
              v-model="editNote"
              v-bind="editNoteProps"
              auto-resize
              rows="3"
              fluid
            />
            <small class="materials-page__field-error">{{ editErrors.note }}</small>
          </div>

          <div class="materials-page__dialog-actions">
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
        class="materials-page__dialog"
        header="Xác nhận xóa"
        modal
      >
        <div class="materials-page__delete-message">
          <p>
            Bạn có chắc chắn muốn xóa vật tư
            <strong>{{ selectedMaterial?.name }}</strong> không?
          </p>
          <div v-if="submitError" class="materials-page__submit-error">
            {{ submitError }}
          </div>
        </div>

        <div class="materials-page__dialog-actions">
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

import { useCatalogImport } from '@/composables/useCatalogImport'
import { catalogStatusOptions } from '@/composables/useMaterialTypesPage'
import { useMaterialsPage } from '@/composables/useMaterialsPage'
import AdminLayout from '@/layouts/AdminLayout.vue'
import { usePermissionStore } from '@/stores/permission.store'
import type { CatalogStatus } from '@/types/materials'

const permissionStore = usePermissionStore()
const statusFilterOptions = [
  { label: 'Tất cả', value: '' },
  ...catalogStatusOptions,
]

const {
  materials,
  materialTypes,
  totalMaterials,
  loading,
  generalError,
  submitError,
  selectedMaterial,
  createDialogVisible,
  editDialogVisible,
  deleteDialogVisible,
  isDeleting,
  lazyParams,
  fetchMaterials,
  fetchMaterialTypesLookup,
  openCreateDialog,
  openEditDialog,
  openDeleteDialog,
  submitDelete,
  createCode,
  createCodeProps,
  createName,
  createNameProps,
  createMaterialTypeId,
  createMaterialTypeIdProps,
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
  editMaterialTypeId,
  editMaterialTypeIdProps,
  editStatus,
  editStatusProps,
  editNote,
  editNoteProps,
  editErrors,
  editFormSubmitting,
  submitEdit,
} = useMaterialsPage()

const {
  importDialogVisible,
  importJob,
  importError,
  uploadingImport,
  openImportDialog,
  handleImportUpload,
  downloadTemplate,
  downloadErrorFile,
} = useCatalogImport('materials', fetchMaterials)

let searchTimeout: ReturnType<typeof window.setTimeout> | null = null
function onSearchInput() {
  if (searchTimeout) {
    window.clearTimeout(searchTimeout)
  }
  searchTimeout = window.setTimeout(() => {
    lazyParams.offset = 0
    fetchMaterials()
  }, 400)
}

function onFilterChange() {
  lazyParams.offset = 0
  fetchMaterials()
}

function onPageChange(event: { first: number; rows: number }) {
  lazyParams.offset = event.first
  lazyParams.limit = event.rows
  fetchMaterials()
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
  fetchMaterials()
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

onMounted(async () => {
  await Promise.all([fetchMaterials(), fetchMaterialTypesLookup()])
})
</script>
