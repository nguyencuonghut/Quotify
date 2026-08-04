<template>
  <AdminLayout section-label="Tài khoản cá nhân" title="Hồ sơ">
    <div class="profile-page">
      <section class="profile-page__hero">
        <div class="profile-page__identity">
          <div class="profile-page__avatar-shell">
            <img
              :src="profileAvatarUrl"
              alt="Ảnh đại diện người dùng"
              class="profile-page__avatar-image"
            />
          </div>

          <div class="profile-page__identity-copy">
            <p class="profile-page__eyebrow">Tài khoản đang đăng nhập</p>
            <h3 class="profile-page__name">
              {{ currentUser?.fullName || 'Chưa cập nhật họ tên' }}
            </h3>
            <p class="profile-page__email">
              {{ currentUser?.email || 'Chưa có email' }}
            </p>
          </div>
        </div>

        <dl class="profile-page__meta-grid">
          <div class="profile-page__meta-item">
            <dt>Trạng thái</dt>
            <dd>{{ currentUser?.status || 'Không xác định' }}</dd>
          </div>

          <div class="profile-page__meta-item">
            <dt>Đăng nhập cuối</dt>
            <dd>{{ formatDateTime(currentUser?.lastLoginAt ?? null) }}</dd>
          </div>

          <div class="profile-page__meta-item">
            <dt>Vai trò</dt>
            <dd>{{ rolesDisplay }}</dd>
          </div>

          <div class="profile-page__meta-item">
            <dt>Quyền</dt>
            <dd>{{ permissionsDisplay }}</dd>
          </div>
        </dl>
      </section>

      <div class="profile-page__workspace">
        <section class="profile-page__panel" aria-labelledby="avatar-title">
          <div class="profile-page__panel-header">
            <span class="profile-page__panel-icon pi pi-image" aria-hidden="true" />
            <div>
              <h3 id="avatar-title" class="profile-page__panel-title">
                Ảnh đại diện
              </h3>
              <p class="profile-page__panel-description">
                Ảnh này được dùng ở topbar, hồ sơ và ghi chú thị trường.
              </p>
            </div>
          </div>

          <div class="profile-page__avatar-editor">
            <div class="profile-page__avatar-preview">
              <img
                :src="profileAvatarUrl"
                alt="Xem trước ảnh đại diện"
                class="profile-page__avatar-preview-image"
              />
            </div>

            <div class="profile-page__avatar-actions">
              <FileUpload
                mode="basic"
                name="avatar"
                accept="image/*"
                :max-file-size="5242880"
                custom-upload
                auto
                choose-label="Đổi ảnh đại diện"
                :disabled="isAvatarUploading"
                @uploader="handleAvatarUpload"
              />
              <small class="profile-page__hint">
                Chỉ chấp nhận tệp ảnh. Dung lượng tối đa 5MB.
              </small>
              <small v-if="avatarError" class="profile-page__error">
                {{ avatarError }}
              </small>
              <small v-if="avatarSuccess" class="profile-page__success">
                {{ avatarSuccess }}
              </small>
            </div>
          </div>
        </section>

        <section class="profile-page__panel" aria-labelledby="password-title">
          <div class="profile-page__panel-header">
            <span class="profile-page__panel-icon pi pi-lock" aria-hidden="true" />
            <div>
              <h3 id="password-title" class="profile-page__panel-title">
                Đổi mật khẩu
              </h3>
              <p class="profile-page__panel-description">
                Mật khẩu mới cần tối thiểu 8 ký tự.
              </p>
            </div>
          </div>

          <form class="profile-page__password-form" @submit.prevent="submitPasswordChange">
            <div class="profile-page__field">
              <label for="current-password" class="profile-page__label required">
                Mật khẩu hiện tại
              </label>
              <Password
                id="current-password"
                v-model="currentPassword"
                v-bind="currentPasswordProps"
                :feedback="false"
                :input-props="{ autocomplete: 'current-password' }"
                fluid
                toggle-mask
              />
              <small v-if="errors.currentPassword" class="profile-page__error">
                {{ errors.currentPassword }}
              </small>
            </div>

            <div class="profile-page__field">
              <label for="new-password" class="profile-page__label required">
                Mật khẩu mới
              </label>
              <Password
                id="new-password"
                v-model="newPassword"
                v-bind="newPasswordProps"
                :input-props="{ autocomplete: 'new-password' }"
                fluid
                toggle-mask
              />
              <small v-if="errors.newPassword" class="profile-page__error">
                {{ errors.newPassword }}
              </small>
            </div>

            <div class="profile-page__field">
              <label for="confirm-password" class="profile-page__label required">
                Xác nhận mật khẩu mới
              </label>
              <Password
                id="confirm-password"
                v-model="confirmPassword"
                v-bind="confirmPasswordProps"
                :feedback="false"
                :input-props="{ autocomplete: 'new-password' }"
                fluid
                toggle-mask
              />
              <small v-if="errors.confirmPassword" class="profile-page__error">
                {{ errors.confirmPassword }}
              </small>
            </div>

            <small v-if="passwordError" class="profile-page__error">
              {{ passwordError }}
            </small>
            <small v-if="passwordSuccess" class="profile-page__success">
              {{ passwordSuccess }}
            </small>

            <Button
              type="submit"
              icon="pi pi-save"
              label="Cập nhật mật khẩu"
              :loading="isPasswordSubmitting"
              :disabled="isPasswordSubmitting"
            />
          </form>
        </section>
      </div>
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import Button from 'primevue/button'
import FileUpload from 'primevue/fileupload'
import Password from 'primevue/password'

import { useProfilePage } from '@/composables/useProfilePage'
import AdminLayout from '@/layouts/AdminLayout.vue'

const {
  avatarError,
  avatarSuccess,
  confirmPassword,
  confirmPasswordProps,
  currentPassword,
  currentPasswordProps,
  currentUser,
  errors,
  formatDateTime,
  handleAvatarUpload,
  isAvatarUploading,
  isPasswordSubmitting,
  newPassword,
  newPasswordProps,
  passwordError,
  passwordSuccess,
  permissionsDisplay,
  profileAvatarUrl,
  rolesDisplay,
  submitPasswordChange,
} = useProfilePage()
</script>
