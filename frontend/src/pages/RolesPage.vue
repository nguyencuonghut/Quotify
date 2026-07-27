<template>
  <AdminLayout section-label="Quản trị hệ thống" title="Danh sách vai trò">
    <div class="roles-page">
      <!-- Top Filters and Actions -->
      <section class="roles-page__header">
        <div class="roles-page__filters">
          <label class="roles-page__filter-field">
            <span class="roles-page__filter-label">Tìm kiếm vai trò</span>
            <InputText
              v-model="lazyParams.search"
              placeholder="Nhập tên vai trò..."
              class="roles-page__input-search"
              @input="onSearchInput"
            />
          </label>
        </div>

        <div class="roles-page__actions">
          <Button
            v-if="permissionStore.can('roles.create')"
            label="Thêm vai trò"
            icon="pi pi-plus"
            @click="openCreateDialog"
          />
        </div>
      </section>

      <!-- Main Data Table -->
      <div v-if="generalError" class="roles-page__general-error">
        <i class="pi pi-exclamation-triangle" aria-hidden="true" />
        <span>{{ generalError }}</span>
      </div>

      <section class="roles-page__table-wrapper">
        <DataTable
          :loading="loading"
          :rows="lazyParams.limit"
          :total-records="totalRoles"
          :value="roles"
          data-key="id"
          lazy
          paginator
          current-page-report-template="Hiển thị từ {first} đến {last} trên tổng số {totalRecords} dòng"
          :rows-per-page-options="[10, 20, 30, 50]"
          paginator-template="RowsPerPageDropdown FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink CurrentPageReport"
          responsive-layout="scroll"
          @page="onPageChange"
          @sort="onSortChange"
        >
          <Column field="name" header="Tên vai trò" sortable />
          <Column field="description" header="Mô tả" />
          <Column field="is_system" header="Loại vai trò">
            <template #body="{ data }">
              <Tag
                :severity="data.isSystem ? 'info' : 'secondary'"
                :value="data.isSystem ? 'Hệ thống' : 'Tự định nghĩa'"
              />
            </template>
          </Column>
          <Column header="Danh sách quyền">
            <template #body="{ data }">
              <div class="roles-page__permission-tags">
                <Tag
                  v-for="perm in data.permissions"
                  :key="perm"
                  :value="perm"
                  severity="secondary"
                  class="roles-page__permission-tag"
                />
              </div>
            </template>
          </Column>
          <Column header="Thao tác" class="roles-page__actions-column">
            <template #body="{ data }">
              <div class="roles-page__row-actions">
                <Button
                  v-if="permissionStore.can('roles.update')"
                  icon="pi pi-pencil"
                  severity="secondary"
                  text
                  rounded
                  aria-label="Chỉnh sửa"
                  @click="openEditDialog(data)"
                />
                <Button
                  v-if="permissionStore.can('roles.delete')"
                  :disabled="data.isSystem"
                  icon="pi pi-trash"
                  severity="danger"
                  text
                  rounded
                  aria-label="Xóa"
                  @click="openDeleteDialog(data)"
                />
              </div>
            </template>
          </Column>
        </DataTable>
      </section>

      <!-- Create Role Dialog -->
      <Dialog
        v-model:visible="createDialogVisible"
        header="Thêm vai trò mới"
        modal
        class="roles-page__dialog"
      >
        <form class="roles-page__form" @submit.prevent="submitCreate">
          <div v-if="submitError" class="roles-page__submit-error">
            {{ submitError }}
          </div>

          <div class="roles-page__form-field">
            <label for="create-name" class="roles-page__form-label required"
              >Tên vai trò</label
            >
            <InputText
              id="create-name"
              v-model="createName"
              v-bind="createNameProps"
              fluid
              placeholder="Ví dụ: hr_manager"
            />
            <small class="roles-page__field-error">{{
              createErrors.name
            }}</small>
          </div>

          <div class="roles-page__form-field">
            <label for="create-description" class="roles-page__form-label"
              >Mô tả</label
            >
            <InputText
              id="create-description"
              v-model="createDescription"
              v-bind="createDescriptionProps"
              fluid
              placeholder="Nhập mô tả cho vai trò..."
            />
            <small class="roles-page__field-error">{{
              createErrors.description
            }}</small>
          </div>

          <div class="roles-page__form-field">
            <label
              for="create-permissions"
              class="roles-page__form-label required"
            >
              >Quyền hạn</label
            >
            <MultiSelect
              id="create-permissions"
              v-model="createPermissions"
              v-bind="createPermissionsProps"
              :options="permissions"
              option-label="code"
              option-value="code"
              placeholder="Chọn quyền..."
              fluid
              display="chip"
            />
            <small class="roles-page__field-error">{{
              createErrors.permissions
            }}</small>
          </div>

          <div class="roles-page__dialog-actions">
            <Button
              label="Hủy"
              severity="secondary"
              text
              @click="createDialogVisible = false"
            />
            <Button
              type="submit"
              label="Lưu lại"
              :loading="createFormSubmitting"
            />
          </div>
        </form>
      </Dialog>

      <!-- Edit Role Dialog -->
      <Dialog
        v-model:visible="editDialogVisible"
        header="Chỉnh sửa vai trò"
        modal
        class="roles-page__dialog"
      >
        <form class="roles-page__form" @submit.prevent="submitEdit">
          <div v-if="submitError" class="roles-page__submit-error">
            {{ submitError }}
          </div>

          <div class="roles-page__form-field">
            <label for="edit-name" class="roles-page__form-label required"
              >Tên vai trò</label
            >
            <InputText
              id="edit-name"
              v-model="editName"
              v-bind="editNameProps"
              fluid
              :disabled="selectedRole?.isSystem"
              placeholder="Ví dụ: hr_manager"
            />
            <small class="roles-page__field-error">{{ editErrors.name }}</small>
          </div>

          <div class="roles-page__form-field">
            <label for="edit-description" class="roles-page__form-label"
              >Mô tả</label
            >
            <InputText
              id="edit-description"
              v-model="editDescription"
              v-bind="editDescriptionProps"
              fluid
              placeholder="Nhập mô tả cho vai trò..."
            />
            <small class="roles-page__field-error">{{
              editErrors.description
            }}</small>
          </div>

          <div class="roles-page__form-field">
            <label
              for="edit-permissions"
              class="roles-page__form-label required"
            >
              >Quyền hạn</label
            >
            <MultiSelect
              id="edit-permissions"
              v-model="editPermissions"
              v-bind="editPermissionsProps"
              :options="permissions"
              option-label="code"
              option-value="code"
              placeholder="Chọn quyền..."
              fluid
              display="chip"
            />
            <small class="roles-page__field-error">{{
              editErrors.permissions
            }}</small>
          </div>

          <div class="roles-page__dialog-actions">
            <Button
              label="Hủy"
              severity="secondary"
              text
              @click="editDialogVisible = false"
            />
            <Button
              type="submit"
              label="Cập nhật"
              :loading="editFormSubmitting"
            />
          </div>
        </form>
      </Dialog>

      <!-- Delete Confirmation Dialog -->
      <Dialog
        v-model:visible="deleteDialogVisible"
        header="Xác nhận xóa"
        modal
        class="roles-page__dialog"
      >
        <div class="roles-page__delete-message">
          <p>
            Bạn có chắc chắn muốn xóa vai trò
            <strong>{{ selectedRole?.name }}</strong> không? Hành động này không
            thể hoàn tác.
          </p>
          <div v-if="submitError" class="roles-page__submit-error">
            {{ submitError }}
          </div>
        </div>

        <div class="roles-page__dialog-actions">
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
import InputText from 'primevue/inputtext'
import MultiSelect from 'primevue/multiselect'
import Tag from 'primevue/tag'

import { useRolesPage } from '@/composables/useRolesPage'
import AdminLayout from '@/layouts/AdminLayout.vue'
import { usePermissionStore } from '@/stores/permission.store'

const permissionStore = usePermissionStore()

const {
  roles,
  totalRoles,
  loading,
  permissions,
  lazyParams,
  generalError,
  submitError,
  createDialogVisible,
  editDialogVisible,
  deleteDialogVisible,
  selectedRole,
  isDeleting,
  fetchRoles,
  fetchPermissions,
  openCreateDialog,
  openEditDialog,
  openDeleteDialog,
  submitDelete,
  createName,
  createNameProps,
  createDescription,
  createDescriptionProps,
  createPermissions,
  createPermissionsProps,
  createErrors,
  submitCreate,
  createFormSubmitting,
  editName,
  editNameProps,
  editDescription,
  editDescriptionProps,
  editPermissions,
  editPermissionsProps,
  editErrors,
  submitEdit,
  editFormSubmitting,
} = useRolesPage()

// Debounced search
let searchTimeout: ReturnType<typeof window.setTimeout> | null = null
function onSearchInput() {
  if (searchTimeout) {
    window.clearTimeout(searchTimeout)
  }
  searchTimeout = window.setTimeout(() => {
    lazyParams.offset = 0
    fetchRoles()
  }, 400)
}

function onPageChange(event: { first: number; rows: number }) {
  lazyParams.offset = event.first
  lazyParams.limit = event.rows
  fetchRoles()
}

function onSortChange(event: {
  sortField?: string | ((item: unknown) => string)
  sortOrder?: number | null
}) {
  const sortField =
    typeof event.sortField === 'string' ? event.sortField : undefined
  lazyParams.sort_by = sortField || 'name'
  lazyParams.sort_order = event.sortOrder === 1 ? 'asc' : 'desc'
  lazyParams.offset = 0
  fetchRoles()
}

onMounted(async () => {
  await Promise.all([fetchRoles(), fetchPermissions()])
})
</script>
