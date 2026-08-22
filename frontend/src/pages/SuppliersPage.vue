<template>
  <AdminLayout section-label="Danh mục" title="Nhà cung cấp">
    <div class="suppliers-page">
      <section class="suppliers-page__header">
        <div class="suppliers-page__filters">
          <label class="suppliers-page__filter-field">
            <span class="suppliers-page__filter-label">Tìm kiếm</span>
            <InputText
              v-model="lazyParams.search"
              class="suppliers-page__input-search"
              placeholder="Mã hoặc tên NCC..."
              @input="onSearchInput"
            />
          </label>

          <label class="suppliers-page__filter-field">
            <span class="suppliers-page__filter-label">Loại NCC</span>
            <Select
              v-model="lazyParams.supplier_type"
              :options="supplierTypeFilterOptions"
              class="suppliers-page__type-filter"
              option-label="label"
              option-value="value"
              placeholder="Tất cả"
              show-clear
              @change="onFilterChange"
            />
          </label>

          <label class="suppliers-page__filter-field">
            <span class="suppliers-page__filter-label">Trạng thái</span>
            <Select
              v-model="lazyParams.status"
              :options="statusFilterOptions"
              class="suppliers-page__status-filter"
              option-label="label"
              option-value="value"
              placeholder="Tất cả"
              show-clear
              @change="onFilterChange"
            />
          </label>
        </div>

        <div class="suppliers-page__actions">
          <Button
            v-if="permissionStore.can('suppliers.import')"
            icon="pi pi-upload"
            label="Import CSV"
            severity="secondary"
            @click="openImportDialog"
          />
          <Button
            v-if="permissionStore.can('suppliers.create')"
            icon="pi pi-plus"
            label="Thêm NCC"
            @click="openCreateDialog"
          />
        </div>
      </section>

      <div v-if="generalError" class="suppliers-page__general-error">
        <i class="pi pi-exclamation-triangle" aria-hidden="true" />
        <span>{{ generalError }}</span>
      </div>

      <section class="suppliers-page__table-wrapper">
        <DataTable
          :loading="loading"
          :rows="lazyParams.limit"
          :rows-per-page-options="[10, 20, 30, 50]"
          :total-records="totalSuppliers"
          :value="suppliers"
          current-page-report-template="Hiển thị từ {first} đến {last} trên tổng số {totalRecords} dòng"
          data-key="id"
          lazy
          paginator
          paginator-template="RowsPerPageDropdown FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink CurrentPageReport"
          responsive-layout="scroll"
          @page="onPageChange"
          @sort="onSortChange"
        >
          <Column field="code" header="Mã NCC" sortable />
          <Column field="name" header="Tên NCC" sortable />
          <Column field="supplierType" header="Loại NCC" sortable>
            <template #body="{ data }">
              <span>{{ formatSupplierType(data.supplierType) }}</span>
            </template>
          </Column>
          <Column header="Liên hệ">
            <template #body="{ data }">
              <span>{{ data.contacts.length }} liên hệ</span>
            </template>
          </Column>
          <Column header="Vật tư cung cấp">
            <template #body="{ data }">
              <span
                class="suppliers-page__materials-cell"
                :title="formatMaterialNames(data.materials)"
                >{{ formatMaterialNames(data.materials) }}</span
              >
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
          <Column header="Thao tác" class="suppliers-page__actions-column">
            <template #body="{ data }">
              <div class="suppliers-page__row-actions">
                <Button
                  v-if="permissionStore.can('suppliers.update')"
                  aria-label="Chỉnh sửa"
                  icon="pi pi-pencil"
                  rounded
                  severity="secondary"
                  text
                  @click.stop="openEditDialog(data)"
                />
                <Button
                  v-if="permissionStore.can('suppliers.delete')"
                  aria-label="Xóa"
                  icon="pi pi-trash"
                  rounded
                  severity="danger"
                  text
                  @click.stop="openDeleteDialog(data)"
                />
              </div>
            </template>
          </Column>
          <template #empty>
            <span class="suppliers-page__table-empty">
              Không tìm thấy nhà cung cấp phù hợp với bộ lọc hiện tại.
            </span>
          </template>
        </DataTable>
      </section>

      <Dialog
        v-model:visible="importDialogVisible"
        class="suppliers-page__dialog"
        header="Import nhà cung cấp"
        modal
      >
        <div class="suppliers-page__form">
          <div v-if="importError" class="suppliers-page__submit-error">
            {{ importError }}
          </div>
          <div class="suppliers-page__dialog-actions">
            <Button
              icon="pi pi-download"
              :label="`Tải template ${fileFormatLabel}`"
              severity="secondary"
              text
              @click="downloadTemplate"
            />
          </div>
          <FileUpload
            :accept="fileAccept"
            :choose-label="`Chọn file ${fileFormatLabel}`"
            custom-upload
            mode="basic"
            name="file"
            :auto="true"
            :disabled="uploadingImport"
            @uploader="handleImportUpload"
          />
          <div
            v-if="importJob"
            class="suppliers-page__import-status"
            :class="{
              'suppliers-page__import-status--success':
                importJob.status === 'completed' && importJob.failedRows === 0,
              'suppliers-page__import-status--failed': importJob.failedRows > 0,
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
        class="suppliers-page__dialog"
        header="Thêm NCC"
        modal
      >
        <form class="suppliers-page__form" @submit.prevent="submitCreate">
          <div v-if="submitError" class="suppliers-page__submit-error">
            {{ submitError }}
          </div>

          <section class="suppliers-page__form-section">
            <h3 class="suppliers-page__section-title">Thông tin chính</h3>
            <div class="suppliers-page__form-grid">
              <div class="suppliers-page__form-field">
                <label class="suppliers-page__form-label required">Mã NCC</label>
                <InputText
                  v-model="createCode"
                  v-bind="createCodeProps"
                  fluid
                  placeholder="Ví dụ: SUP-001"
                />
              </div>
              <div class="suppliers-page__form-field">
                <label class="suppliers-page__form-label required">Tên NCC</label>
                <InputText
                  v-model="createName"
                  v-bind="createNameProps"
                  fluid
                  placeholder="Tên nhà cung cấp"
                />
              </div>
              <div class="suppliers-page__form-field">
                <label class="suppliers-page__form-label required">Loại NCC</label>
                <MultiSelect
                  v-model="createSupplierType"
                  v-bind="createSupplierTypeProps"
                  :options="supplierTypeOptions"
                  display="chip"
                  fluid
                  option-label="label"
                  option-value="value"
                  placeholder="Chọn loại NCC"
                />
              </div>
              <div class="suppliers-page__form-field">
                <label class="suppliers-page__form-label required">Trạng thái</label>
                <Select
                  v-model="createStatus"
                  v-bind="createStatusProps"
                  :options="catalogStatusOptions"
                  fluid
                  option-label="label"
                  option-value="value"
                />
              </div>
              <div class="suppliers-page__form-field">
                <label class="suppliers-page__form-label">Mã số thuế</label>
                <InputText v-model="createTaxCode" v-bind="createTaxCodeProps" fluid />
              </div>
              <div class="suppliers-page__form-field">
                <label class="suppliers-page__form-label">Địa chỉ</label>
                <InputText v-model="createAddress" v-bind="createAddressProps" fluid />
              </div>
            </div>
            <div class="suppliers-page__form-field">
              <label class="suppliers-page__form-label">Ghi chú</label>
              <Textarea
                v-model="createNote"
                v-bind="createNoteProps"
                auto-resize
                fluid
                rows="3"
              />
            </div>
          </section>

          <section class="suppliers-page__form-section">
            <div class="suppliers-page__section-heading">
              <h3 class="suppliers-page__section-title">Liên hệ</h3>
              <Button
                icon="pi pi-plus"
                label="Thêm liên hệ"
                severity="secondary"
                text
                type="button"
                @click="addContact('create')"
              />
            </div>
            <p v-if="createContacts.length === 0" class="suppliers-page__empty-text">
              Chưa có liên hệ.
            </p>
            <div
              v-for="contact in createContacts"
              :key="contact.localId"
              class="suppliers-page__contact-row"
            >
              <InputText v-model="contact.name" placeholder="Tên liên hệ *" />
              <InputText v-model="contact.title" placeholder="Chức danh" />
              <InputText v-model="contact.email" placeholder="Email" />
              <InputText v-model="contact.phone" placeholder="Điện thoại" />
              <Select
                v-model="contact.status"
                :options="catalogStatusOptions"
                option-label="label"
                option-value="value"
              />
              <Button
                aria-label="Xóa liên hệ"
                icon="pi pi-times"
                severity="danger"
                rounded
                text
                type="button"
                @click="removeContact('create', contact.localId)"
              />
            </div>
          </section>

          <section class="suppliers-page__form-section">
            <h3 class="suppliers-page__section-title">Vật tư cung cấp</h3>
            <MultiSelect
              v-model="createMaterialIds"
              :options="materials"
              display="chip"
              filter
              option-label="name"
              option-value="id"
              placeholder="Chọn vật tư NCC có thể cung cấp"
            />
          </section>

          <div class="suppliers-page__dialog-actions">
            <Button
              label="Hủy"
              severity="secondary"
              text
              type="button"
              @click="createDialogVisible = false"
            />
            <Button label="Lưu lại" type="submit" />
          </div>
        </form>
      </Dialog>

      <Dialog
        v-model:visible="editDialogVisible"
        class="suppliers-page__dialog"
        header="Chỉnh sửa NCC"
        modal
      >
        <form class="suppliers-page__form" @submit.prevent="submitEdit">
          <div v-if="submitError" class="suppliers-page__submit-error">
            {{ submitError }}
          </div>

          <section class="suppliers-page__form-section">
            <h3 class="suppliers-page__section-title">Thông tin chính</h3>
            <div class="suppliers-page__form-grid">
              <div class="suppliers-page__form-field">
                <label class="suppliers-page__form-label required">Mã NCC</label>
                <InputText
                  v-model="editCode"
                  v-bind="editCodeProps"
                  fluid
                  placeholder="Ví dụ: SUP-001"
                />
              </div>
              <div class="suppliers-page__form-field">
                <label class="suppliers-page__form-label required">Tên NCC</label>
                <InputText
                  v-model="editName"
                  v-bind="editNameProps"
                  fluid
                  placeholder="Tên nhà cung cấp"
                />
              </div>
              <div class="suppliers-page__form-field">
                <label class="suppliers-page__form-label required">Loại NCC</label>
                <MultiSelect
                  v-model="editSupplierType"
                  v-bind="editSupplierTypeProps"
                  :options="supplierTypeOptions"
                  display="chip"
                  fluid
                  option-label="label"
                  option-value="value"
                  placeholder="Chọn loại NCC"
                />
              </div>
              <div class="suppliers-page__form-field">
                <label class="suppliers-page__form-label required">Trạng thái</label>
                <Select
                  v-model="editStatus"
                  v-bind="editStatusProps"
                  :options="catalogStatusOptions"
                  fluid
                  option-label="label"
                  option-value="value"
                />
              </div>
              <div class="suppliers-page__form-field">
                <label class="suppliers-page__form-label">Mã số thuế</label>
                <InputText v-model="editTaxCode" v-bind="editTaxCodeProps" fluid />
              </div>
              <div class="suppliers-page__form-field">
                <label class="suppliers-page__form-label">Địa chỉ</label>
                <InputText v-model="editAddress" v-bind="editAddressProps" fluid />
              </div>
            </div>
            <div class="suppliers-page__form-field">
              <label class="suppliers-page__form-label">Ghi chú</label>
              <Textarea
                v-model="editNote"
                v-bind="editNoteProps"
                auto-resize
                fluid
                rows="3"
              />
            </div>
          </section>

          <section class="suppliers-page__form-section">
            <div class="suppliers-page__section-heading">
              <h3 class="suppliers-page__section-title">Liên hệ</h3>
              <Button
                icon="pi pi-plus"
                label="Thêm liên hệ"
                severity="secondary"
                text
                type="button"
                @click="addContact('edit')"
              />
            </div>
            <p v-if="editContacts.length === 0" class="suppliers-page__empty-text">
              Chưa có liên hệ.
            </p>
            <div
              v-for="contact in editContacts"
              :key="contact.localId"
              class="suppliers-page__contact-row"
            >
              <InputText v-model="contact.name" placeholder="Tên liên hệ *" />
              <InputText v-model="contact.title" placeholder="Chức danh" />
              <InputText v-model="contact.email" placeholder="Email" />
              <InputText v-model="contact.phone" placeholder="Điện thoại" />
              <Select
                v-model="contact.status"
                :options="catalogStatusOptions"
                option-label="label"
                option-value="value"
              />
              <Button
                aria-label="Xóa liên hệ"
                icon="pi pi-times"
                severity="danger"
                rounded
                text
                type="button"
                @click="removeContact('edit', contact.localId)"
              />
            </div>
          </section>

          <section class="suppliers-page__form-section">
            <h3 class="suppliers-page__section-title">Vật tư cung cấp</h3>
            <MultiSelect
              v-model="editMaterialIds"
              :options="materials"
              display="chip"
              filter
              option-label="name"
              option-value="id"
              placeholder="Chọn vật tư NCC có thể cung cấp"
            />
          </section>

          <div class="suppliers-page__dialog-actions">
            <Button
              label="Hủy"
              severity="secondary"
              text
              type="button"
              @click="editDialogVisible = false"
            />
            <Button label="Cập nhật" type="submit" />
          </div>
        </form>
      </Dialog>

      <Dialog
        v-model:visible="deleteDialogVisible"
        class="suppliers-page__dialog suppliers-page__dialog--compact"
        header="Xóa NCC"
        modal
      >
        <div class="suppliers-page__delete-message">
          <p>
            Bạn có chắc muốn xóa NCC
            <strong>{{ selectedSupplier?.name }}</strong>?
          </p>
          <div v-if="submitError" class="suppliers-page__submit-error">
            {{ submitError }}
          </div>
        </div>
        <div class="suppliers-page__dialog-actions">
          <Button
            label="Hủy"
            severity="secondary"
            text
            @click="deleteDialogVisible = false"
          />
          <Button
            label="Xóa"
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
import MultiSelect from 'primevue/multiselect'
import ProgressBar from 'primevue/progressbar'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import Textarea from 'primevue/textarea'

import { useCatalogImport } from '@/composables/useCatalogImport'
import AdminLayout from '@/layouts/AdminLayout.vue'
import {
  catalogStatusOptions,
  statusFilterOptions,
  supplierTypeFilterOptions,
  supplierTypeOptions,
  useSuppliersPage,
} from '@/composables/useSuppliersPage'
import { usePermissionStore } from '@/stores/permission.store'
import type { SupplierMaterialDomain } from '@/types/suppliers'

const permissionStore = usePermissionStore()

const {
  suppliers,
  materials,
  totalSuppliers,
  loading,
  generalError,
  submitError,
  selectedSupplier,
  createDialogVisible,
  editDialogVisible,
  deleteDialogVisible,
  isDeleting,
  createContacts,
  editContacts,
  createMaterialIds,
  editMaterialIds,
  lazyParams,
  fetchSuppliers,
  fetchMaterialsLookup,
  openCreateDialog,
  openEditDialog,
  openDeleteDialog,
  submitDelete,
  addContact,
  removeContact,
  createCode,
  createCodeProps,
  createName,
  createNameProps,
  createSupplierType,
  createSupplierTypeProps,
  createStatus,
  createStatusProps,
  createTaxCode,
  createTaxCodeProps,
  createAddress,
  createAddressProps,
  createNote,
  createNoteProps,
  editCode,
  editCodeProps,
  editName,
  editNameProps,
  editSupplierType,
  editSupplierTypeProps,
  editStatus,
  editStatusProps,
  editTaxCode,
  editTaxCodeProps,
  editAddress,
  editAddressProps,
  editNote,
  editNoteProps,
  submitCreate,
  submitEdit,
  formatStatus,
  formatSupplierType,
  onPageChange,
  onSortChange,
  onSearchInput,
  onFilterChange,
} = useSuppliersPage()

const {
  importDialogVisible,
  importJob,
  importError,
  uploadingImport,
  fileAccept,
  fileFormatLabel,
  openImportDialog,
  handleImportUpload,
  downloadTemplate,
  downloadErrorFile,
} = useCatalogImport('suppliers', fetchSuppliers)

function formatMaterialNames(materialsList: SupplierMaterialDomain[]) {
  if (materialsList.length === 0) return 'Chưa gắn vật tư'
  return materialsList.map((material) => material.materialName).join(', ')
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

onMounted(() => {
  void fetchSuppliers()
  void fetchMaterialsLookup()
})
</script>
