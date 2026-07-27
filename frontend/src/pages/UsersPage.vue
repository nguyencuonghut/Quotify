<template>
  <AdminLayout section-label="Quản trị hệ thống" title="Danh sách tài khoản">
    <div class="users-page">
      <!-- Top Filters and Actions -->
      <section class="users-page__header">
        <div class="users-page__filters">
          <label class="users-page__filter-field">
            <span class="users-page__filter-label">Tìm kiếm email</span>
            <InputText
              v-model="lazyParams.search"
              placeholder="Nhập email..."
              class="users-page__input-search"
              @input="onSearchInput"
            />
          </label>

          <label class="users-page__filter-field">
            <span class="users-page__filter-label">Trạng thái</span>
            <Select
              v-model="lazyParams.status_filter"
              :options="statusFilterOptions"
              option-label="label"
              option-value="value"
              placeholder="Tất cả"
              class="users-page__status-select"
              @change="onFilterChange"
            />
          </label>
        </div>

        <div class="users-page__actions">
          <Button
            v-if="permissionStore.can('users.import')"
            label="Nhập Excel/CSV"
            icon="pi pi-upload"
            severity="secondary"
            outlined
            class="users-page__action-btn"
            @click="openImportDialog"
          />
          <Button
            v-if="permissionStore.can('users.export')"
            label="Xuất Excel/CSV"
            icon="pi pi-download"
            severity="secondary"
            outlined
            class="users-page__action-btn"
            @click="openExportDialog"
          />
          <Button
            v-if="permissionStore.can('users.create')"
            label="Thêm tài khoản"
            icon="pi pi-plus"
            class="users-page__action-btn"
            @click="openCreateDialog"
          />
        </div>
      </section>

      <!-- Main Data Table -->
      <div v-if="generalError" class="users-page__general-error">
        <i class="pi pi-exclamation-triangle" aria-hidden="true" />
        <span>{{ generalError }}</span>
      </div>

      <section class="users-page__table-wrapper">
        <DataTable
          :loading="loading"
          :rows="lazyParams.limit"
          :total-records="totalUsers"
          :value="users"
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
          <Column field="email" header="Email" sortable />
          <Column field="full_name" header="Họ và tên" sortable>
            <template #body="{ data }">
              {{ data.fullName || '-' }}
            </template>
          </Column>
          <Column field="status" header="Trạng thái">
            <template #body="{ data }">
              <Tag
                :severity="statusSeverity(data.status)"
                :value="statusLabel(data.status)"
              />
            </template>
          </Column>
          <Column header="Vai trò">
            <template #body="{ data }">
              <div class="users-page__role-tags">
                <Tag
                  v-for="role in data.roles"
                  :key="role"
                  :value="role"
                  severity="secondary"
                  class="users-page__role-tag"
                />
              </div>
            </template>
          </Column>
          <Column field="last_login_at" header="Đăng nhập cuối" sortable>
            <template #body="{ data }">
              {{ formatDateTime(data.lastLoginAt) }}
            </template>
          </Column>
          <Column header="Thao tác" class="users-page__actions-column">
            <template #body="{ data }">
              <div class="users-page__row-actions">
                <Button
                  v-if="permissionStore.can('users.update')"
                  icon="pi pi-pencil"
                  severity="secondary"
                  text
                  rounded
                  aria-label="Chỉnh sửa"
                  @click="openEditDialog(data)"
                />
                <Button
                  v-if="permissionStore.can('users.delete')"
                  :disabled="data.id === authStore.currentUser?.id"
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

      <!-- Create User Dialog -->
      <Dialog
        v-model:visible="createDialogVisible"
        header="Thêm tài khoản mới"
        modal
        class="users-page__dialog"
      >
        <form class="users-page__form" @submit.prevent="submitCreate">
          <div v-if="submitError" class="users-page__submit-error">
            {{ submitError }}
          </div>

          <div class="users-page__form-field">
            <label for="create-email" class="users-page__form-label required"
              >Email</label
            >
            <InputText
              id="create-email"
              v-model="createEmail"
              v-bind="createEmailProps"
              fluid
              placeholder="username@domain.com"
            />
            <small class="users-page__field-error">{{
              createErrors.email
            }}</small>
          </div>

          <div class="users-page__form-field">
            <label for="create-fullname" class="users-page__form-label required"
              >Họ và tên</label
            >
            <InputText
              id="create-fullname"
              v-model="createFullName"
              v-bind="createFullNameProps"
              fluid
              placeholder="Nguyễn Văn A"
            />
            <small class="users-page__field-error">{{
              createErrors.fullName
            }}</small>
          </div>

          <div class="users-page__form-field">
            <span class="users-page__form-label">Ảnh đại diện</span>
            <div class="users-page__avatar-field">
              <div class="users-page__avatar-preview-shell">
                <img
                  v-if="createAvatarUrl"
                  :src="createAvatarUrl"
                  alt="Xem trước ảnh đại diện mới"
                  class="users-page__avatar-preview-image"
                />
                <div v-else class="users-page__avatar-placeholder">
                  <i class="pi pi-user" aria-hidden="true" />
                </div>
              </div>

              <div class="users-page__avatar-actions">
                <FileUpload
                  mode="basic"
                  name="avatar"
                  accept="image/*"
                  :max-file-size="5242880"
                  custom-upload
                  auto
                  choose-label="Tải ảnh đại diện"
                  @uploader="handleCreateAvatarUpload"
                />
                <Button
                  v-if="createAvatarUrl"
                  label="Gỡ ảnh"
                  severity="secondary"
                  outlined
                  @click="clearCreateAvatar"
                />
              </div>
            </div>
            <small class="users-page__field-hint"
              >Chỉ chấp nhận tệp ảnh. Ảnh sẽ được lưu vào MinIO và gắn vào tài
              khoản sau khi lưu form.</small
            >
            <small class="users-page__field-error">{{
              createAvatarError || createErrors.avatarUrl
            }}</small>
          </div>

          <div class="users-page__form-field">
            <label for="create-password" class="users-page__form-label required"
              >Mật khẩu</label
            >
            <InputText
              id="create-password"
              v-model="createPassword"
              v-bind="createPasswordProps"
              type="password"
              fluid
              placeholder="Tối thiểu 8 ký tự"
            />
            <small class="users-page__field-error">{{
              createErrors.password
            }}</small>
          </div>

          <div class="users-page__form-field">
            <label for="create-status" class="users-page__form-label required"
              >Trạng thái</label
            >
            <Select
              id="create-status"
              v-model="createStatus"
              v-bind="createStatusProps"
              :options="statusOptions"
              option-label="label"
              option-value="value"
              fluid
            />
            <small class="users-page__field-error">{{
              createErrors.status
            }}</small>
          </div>

          <div class="users-page__form-field">
            <label for="create-roles" class="users-page__form-label required"
              >Vai trò</label
            >
            <MultiSelect
              id="create-roles"
              v-model="createRoleNames"
              v-bind="createRoleNamesProps"
              :options="roles"
              option-label="name"
              option-value="name"
              placeholder="Chọn vai trò..."
              fluid
              display="chip"
            />
            <small class="users-page__field-error">{{
              createErrors.roleNames
            }}</small>
          </div>

          <div class="users-page__dialog-actions">
            <Button
              label="Hủy"
              severity="secondary"
              text
              @click="createDialogVisible = false"
            />
            <Button
              :loading="createFormSubmitting || isCreateAvatarUploading"
              :disabled="isCreateAvatarUploading"
              label="Lưu tài khoản"
              type="submit"
            />
          </div>
        </form>
      </Dialog>

      <!-- Edit User Dialog -->
      <Dialog
        v-model:visible="editDialogVisible"
        header="Chỉnh sửa tài khoản"
        modal
        class="users-page__dialog"
      >
        <form class="users-page__form" @submit.prevent="submitEdit">
          <div v-if="submitError" class="users-page__submit-error">
            {{ submitError }}
          </div>

          <div class="users-page__form-field">
            <label for="edit-email" class="users-page__form-label required"
              >Email</label
            >
            <InputText
              id="edit-email"
              v-model="editEmail"
              v-bind="editEmailProps"
              fluid
              placeholder="username@domain.com"
            />
            <small class="users-page__field-error">{{
              editErrors.email
            }}</small>
          </div>

          <div class="users-page__form-field">
            <label for="edit-fullname" class="users-page__form-label required"
              >Họ và tên</label
            >
            <InputText
              id="edit-fullname"
              v-model="editFullName"
              v-bind="editFullNameProps"
              fluid
              placeholder="Nguyễn Văn A"
            />
            <small class="users-page__field-error">{{
              editErrors.fullName
            }}</small>
          </div>

          <div class="users-page__form-field">
            <span class="users-page__form-label">Ảnh đại diện</span>
            <div class="users-page__avatar-field">
              <div class="users-page__avatar-preview-shell">
                <img
                  v-if="editAvatarUrl"
                  :src="editAvatarUrl"
                  alt="Xem trước ảnh đại diện"
                  class="users-page__avatar-preview-image"
                />
                <div v-else class="users-page__avatar-placeholder">
                  <i class="pi pi-user" aria-hidden="true" />
                </div>
              </div>

              <div class="users-page__avatar-actions">
                <FileUpload
                  mode="basic"
                  name="avatar"
                  accept="image/*"
                  :max-file-size="5242880"
                  custom-upload
                  auto
                  choose-label="Thay ảnh đại diện"
                  @uploader="handleEditAvatarUpload"
                />
                <Button
                  v-if="editAvatarUrl"
                  label="Gỡ ảnh"
                  severity="secondary"
                  outlined
                  @click="clearEditAvatar"
                />
              </div>
            </div>
            <small class="users-page__field-hint"
              >Chỉ chấp nhận tệp ảnh. Nếu không tải ảnh mới, hệ thống giữ nguyên
              ảnh hiện tại.</small
            >
            <small class="users-page__field-error">{{
              editAvatarError || editErrors.avatarUrl
            }}</small>
          </div>

          <div class="users-page__form-field">
            <label for="edit-password" class="users-page__form-label">
              Mật khẩu mới (bỏ trống nếu không đổi)
            </label>
            <InputText
              id="edit-password"
              v-model="editPassword"
              v-bind="editPasswordProps"
              type="password"
              fluid
              placeholder="Tối thiểu 8 ký tự"
            />
            <small class="users-page__field-error">{{
              editErrors.password
            }}</small>
          </div>

          <div class="users-page__form-field">
            <label for="edit-status" class="users-page__form-label required"
              >Trạng thái</label
            >
            <Select
              id="edit-status"
              v-model="editStatus"
              v-bind="editStatusProps"
              :options="statusOptions"
              option-label="label"
              option-value="value"
              fluid
            />
            <small class="users-page__field-error">{{
              editErrors.status
            }}</small>
          </div>

          <div class="users-page__form-field">
            <label for="edit-roles" class="users-page__form-label required"
              >Vai trò</label
            >
            <MultiSelect
              id="edit-roles"
              v-model="editRoleNames"
              v-bind="editRoleNamesProps"
              :options="roles"
              option-label="name"
              option-value="name"
              placeholder="Chọn vai trò..."
              fluid
              display="chip"
            />
            <small class="users-page__field-error">{{
              editErrors.roleNames
            }}</small>
          </div>

          <div class="users-page__dialog-actions">
            <Button
              label="Hủy"
              severity="secondary"
              text
              @click="editDialogVisible = false"
            />
            <Button
              :loading="editFormSubmitting || isEditAvatarUploading"
              :disabled="isEditAvatarUploading"
              label="Cập nhật"
              type="submit"
            />
          </div>
        </form>
      </Dialog>

      <!-- Delete User Dialog -->
      <Dialog
        v-model:visible="deleteDialogVisible"
        header="Xác nhận xóa tài khoản"
        modal
        class="users-page__dialog"
      >
        <div class="users-page__delete-confirm">
          <i
            class="pi pi-exclamation-triangle users-page__delete-icon"
            aria-hidden="true"
          />
          <p>
            Bạn có chắc chắn muốn xóa vĩnh viễn tài khoản
            <strong>{{ selectedUser?.email }}</strong
            >? Thao tác này không thể hoàn tác.
          </p>
        </div>

        <div v-if="submitError" class="users-page__submit-error">
          {{ submitError }}
        </div>

        <div class="users-page__dialog-actions">
          <Button
            label="Hủy"
            severity="secondary"
            text
            @click="deleteDialogVisible = false"
          />
          <Button
            :loading="isDeleting"
            label="Xóa tài khoản"
            severity="danger"
            @click="submitDelete"
          />
        </div>
      </Dialog>

      <!-- Import Users Dialog -->
      <Dialog
        v-model:visible="importDialogVisible"
        header="Nhập tài khoản từ tập tin (CSV)"
        modal
        class="users-page__dialog users-page__dialog--large"
      >
        <div class="users-page__import-form">
          <div class="users-page__form-field">
            <label class="users-page__form-label required"
              >Chọn tệp tài liệu CSV</label
            >
            <FileUpload
              mode="basic"
              name="file"
              accept=".csv"
              :max-file-size="10485760"
              custom-upload
              auto
              fluid
              choose-label="Tải lên tệp CSV"
              @uploader="handleImportUpload"
            />
          </div>

          <h5 class="users-page__section-title">Lịch sử tiến trình nhập</h5>
          <DataTable
            v-model:expanded-rows="expandedRows"
            :rows="10"
            :value="importJobs"
            data-key="id"
            paginator
            current-page-report-template="Hiển thị từ {first} đến {last} trên tổng số {totalRecords} dòng"
            :rows-per-page-options="[10, 20, 30, 50]"
            paginator-template="RowsPerPageDropdown FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink CurrentPageReport"
            responsive-layout="scroll"
            class="users-page__jobs-table"
          >
            <template #empty>
              <div class="users-page__empty-state">
                Chưa thực hiện tiến trình nhập nào.
              </div>
            </template>
            <Column expander style="width: 3rem" />
            <Column field="createdAt" header="Thời gian">
              <template #body="{ data }">
                {{ formatDateTime(data.createdAt) }}
              </template>
            </Column>
            <Column field="status" header="Trạng thái">
              <template #body="{ data }">
                <Tag
                  :severity="statusJobSeverity(data.status)"
                  :value="statusJobLabel(data.status)"
                />
              </template>
            </Column>
            <Column header="Tiến độ">
              <template #body="{ data }">
                <div class="users-page__progress-cell">
                  <div class="users-page__progress-text">
                    {{ data.processedRows }} / {{ data.totalRows }} hợp lệ
                  </div>
                  <ProgressBar
                    :value="getProgressPercentage(data)"
                    :show-value="false"
                    class="users-page__progress-bar"
                  />
                </div>
              </template>
            </Column>
            <Column field="failedRows" header="Thất bại" />

            <template #expansion="{ data }">
              <div
                v-if="data.errorsJson && data.errorsJson.length > 0"
                class="users-page__job-errors"
              >
                <h6 class="users-page__error-title">
                  Chi tiết lỗi dòng kiểm tra
                </h6>
                <DataTable
                  :rows="10"
                  :value="data.errorsJson"
                  class="p-datatable-sm"
                  paginator
                  current-page-report-template="Hiển thị từ {first} đến {last} trên tổng số {totalRecords} dòng"
                  :rows-per-page-options="[10, 20, 30, 50]"
                  paginator-template="RowsPerPageDropdown FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink CurrentPageReport"
                >
                  <Column field="row" header="Dòng" style="width: 5rem" />
                  <Column field="email" header="Email" style="width: 15rem" />
                  <Column header="Lỗi">
                    <template #body="{ data: err }">
                      <ul class="users-page__row-error-list">
                        <li v-for="(e, i) in err.errors" :key="i">{{ e }}</li>
                      </ul>
                    </template>
                  </Column>
                </DataTable>
              </div>
              <div v-else class="users-page__job-no-errors">
                Không phát hiện lỗi kiểm tra dòng nào.
              </div>
            </template>
          </DataTable>
        </div>
      </Dialog>

      <!-- Export Users Dialog -->
      <Dialog
        v-model:visible="exportDialogVisible"
        header="Xuất danh sách tài khoản"
        modal
        class="users-page__dialog users-page__dialog--large"
      >
        <div class="users-page__export-form">
          <div class="users-page__export-confirm">
            <p>
              Tệp xuất dữ liệu tài khoản (CSV) sẽ được tạo dựa trên các bộ lọc
              tìm kiếm hiện tại:
            </p>
            <ul class="users-page__export-filters-list">
              <li>
                Tìm kiếm email:
                <strong>{{ lazyParams.search || 'Tất cả' }}</strong>
              </li>
              <li>
                Trạng thái:
                <strong>{{
                  statusLabel(lazyParams.status_filter || '')
                }}</strong>
              </li>
            </ul>
            <Button
              label="Bắt đầu xuất dữ liệu"
              icon="pi pi-download"
              class="w-full mt-3"
              @click="handleExportTrigger"
            />
          </div>

          <h5 class="users-page__section-title mt-4">Danh sách tệp đã xuất</h5>
          <DataTable
            :rows="10"
            :value="exportJobs"
            data-key="id"
            paginator
            current-page-report-template="Hiển thị từ {first} đến {last} trên tổng số {totalRecords} dòng"
            :rows-per-page-options="[10, 20, 30, 50]"
            paginator-template="RowsPerPageDropdown FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink CurrentPageReport"
            class="users-page__jobs-table"
          >
            <template #empty>
              <div class="users-page__empty-state">
                Chưa có tệp xuất nào được tạo.
              </div>
            </template>
            <Column field="createdAt" header="Thời gian">
              <template #body="{ data }">
                {{ formatDateTime(data.createdAt) }}
              </template>
            </Column>
            <Column field="status" header="Trạng thái">
              <template #body="{ data }">
                <Tag
                  :severity="statusJobSeverity(data.status)"
                  :value="statusJobLabel(data.status)"
                />
              </template>
            </Column>
            <Column header="Thao tác">
              <template #body="{ data }">
                <Button
                  v-if="data.status === 'completed' && data.file"
                  icon="pi pi-download"
                  label="Tải về"
                  text
                  severity="success"
                  @click="downloadJobFile(data.file)"
                />
                <span v-else-if="data.status === 'failed'" class="text-danger"
                  >Lỗi: {{ data.errorSummary }}</span
                >
                <span v-else-if="data.status === 'processing'"
                  >Đang tạo tệp...</span
                >
                <span v-else>Đang chờ xử lý...</span>
              </template>
            </Column>
          </DataTable>
        </div>
      </Dialog>
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
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

import { useUsersPage } from '@/composables/useUsersPage'
import AdminLayout from '@/layouts/AdminLayout.vue'
import { useAuthStore } from '@/stores/auth.store'
import { usePermissionStore } from '@/stores/permission.store'
import type { FileDomain } from '@/types/files'
import type { ImportJobDomain } from '@/types/jobs'

const authStore = useAuthStore()
const permissionStore = usePermissionStore()

const {
  users,
  totalUsers,
  loading,
  roles,
  lazyParams,
  generalError,
  submitError,
  createDialogVisible,
  editDialogVisible,
  deleteDialogVisible,
  selectedUser,
  isDeleting,
  fetchUsers,
  fetchRoles,
  openCreateDialog,
  openEditDialog,
  openDeleteDialog,
  submitDelete,
  createEmail,
  createEmailProps,
  createPassword,
  createPasswordProps,
  createStatus,
  createStatusProps,
  createRoleNames,
  createRoleNamesProps,
  createFullName,
  createFullNameProps,
  createAvatarUrl,
  createErrors,
  createAvatarError,
  isCreateAvatarUploading,
  handleCreateAvatarUpload,
  clearCreateAvatar,
  submitCreate,
  createFormSubmitting,
  editEmail,
  editEmailProps,
  editPassword,
  editPasswordProps,
  editStatus,
  editStatusProps,
  editRoleNames,
  editRoleNamesProps,
  editFullName,
  editFullNameProps,
  editAvatarUrl,
  editErrors,
  editAvatarError,
  isEditAvatarUploading,
  handleEditAvatarUpload,
  clearEditAvatar,
  submitEdit,
  editFormSubmitting,
  importDialogVisible,
  exportDialogVisible,
  importJobs,
  exportJobs,
  fetchImportJobs,
  fetchExportJobs,
  handleImportUpload,
  handleExportTrigger,
} = useUsersPage()

const expandedRows = ref([])

function openImportDialog() {
  importDialogVisible.value = true
  fetchImportJobs()
}

function openExportDialog() {
  exportDialogVisible.value = true
  fetchExportJobs()
}

async function downloadJobFile(file: FileDomain) {
  if (!file || !file.url) return
  try {
    const response = await window.fetch(file.url, {
      headers: {
        Authorization: `Bearer ${authStore.accessToken}`,
      },
    })
    if (!response.ok) {
      throw new Error('Failed to download file content')
    }
    const blob = await response.blob()
    const objectUrl = window.URL.createObjectURL(blob)

    const link = document.createElement('a')
    link.href = objectUrl
    link.download = file.filename
    document.body.appendChild(link)
    link.click()
    link.remove()
  } catch {
    // ignore
  }
}

function getProgressPercentage(job: ImportJobDomain) {
  if (!job.totalRows) return 0
  return Math.round(
    ((job.processedRows + job.failedRows) / job.totalRows) * 100,
  )
}

function statusJobSeverity(status: string) {
  switch (status) {
    case 'completed':
      return 'success'
    case 'failed':
      return 'danger'
    case 'processing':
      return 'info'
    default:
      return 'warn'
  }
}

function statusJobLabel(status: string) {
  switch (status) {
    case 'completed':
      return 'Thành công'
    case 'failed':
      return 'Thất bại'
    case 'processing':
      return 'Đang xử lý'
    default:
      return 'Chờ xử lý'
  }
}

const statusOptions = [
  { label: 'Đang hoạt động', value: 'active' },
  { label: 'Tạm ngưng', value: 'inactive' },
  { label: 'Bị khóa', value: 'locked' },
]

const statusFilterOptions = [
  { label: 'Tất cả', value: '' },
  { label: 'Đang hoạt động', value: 'active' },
  { label: 'Tạm ngưng', value: 'inactive' },
  { label: 'Bị khóa', value: 'locked' },
]

const statusSeverityMap = {
  active: 'success',
  inactive: 'warn',
  locked: 'danger',
} as const

const statusLabelMap = {
  active: 'Đang hoạt động',
  inactive: 'Tạm ngưng',
  locked: 'Bị khóa',
} as const

function statusSeverity(statusVal: string) {
  return (
    statusSeverityMap[statusVal as keyof typeof statusSeverityMap] ||
    'secondary'
  )
}

function statusLabel(statusVal: string) {
  return statusLabelMap[statusVal as keyof typeof statusLabelMap] || statusVal
}

// Debounced search
let searchTimeout: ReturnType<typeof window.setTimeout> | null = null
function onSearchInput() {
  if (searchTimeout) {
    window.clearTimeout(searchTimeout)
  }
  searchTimeout = window.setTimeout(() => {
    lazyParams.offset = 0
    fetchUsers()
  }, 400)
}

function onFilterChange() {
  lazyParams.offset = 0
  fetchUsers()
}

function onPageChange(event: { first: number; rows: number }) {
  lazyParams.offset = event.first
  lazyParams.limit = event.rows
  fetchUsers()
}

function onSortChange(event: {
  sortField?: string | ((item: unknown) => string)
  sortOrder?: number | null
}) {
  const sortField =
    typeof event.sortField === 'string' ? event.sortField : undefined
  lazyParams.sort_by = sortField || 'created_at'
  lazyParams.sort_order = event.sortOrder === 1 ? 'asc' : 'desc'
  lazyParams.offset = 0
  fetchUsers()
}

function formatDateTime(val: string | null) {
  if (!val) return 'Chưa từng đăng nhập'
  try {
    const tz = import.meta.env.VITE_APP_TIMEZONE ?? 'Asia/Ho_Chi_Minh'
    return new Intl.DateTimeFormat('vi-VN', {
      dateStyle: 'medium',
      timeStyle: 'short',
      timeZone: tz,
    }).format(new Date(val))
  } catch {
    return val
  }
}

onMounted(async () => {
  await Promise.all([fetchUsers(), fetchRoles()])
})
</script>
