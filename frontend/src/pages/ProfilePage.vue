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

        <section
          v-if="isTelegramVisible"
          class="profile-page__panel profile-page__panel--wide"
          aria-labelledby="telegram-title"
          data-testid="profile-telegram-panel"
        >
          <div class="profile-page__panel-header">
            <span
              class="profile-page__panel-icon pi pi-send"
              aria-hidden="true"
            />
            <div>
              <h3 id="telegram-title" class="profile-page__panel-title">
                Thông báo Telegram
              </h3>
              <p class="profile-page__panel-description">
                Liên kết tài khoản Telegram để nhận thông báo biến động giá từ
                Quotify.
              </p>
            </div>
          </div>

          <div
            v-if="telegramAccount"
            class="profile-page__telegram-account"
            data-testid="profile-telegram-account"
          >
            <dl class="profile-page__telegram-details">
              <div class="profile-page__meta-item">
                <dt>Tài khoản Telegram</dt>
                <dd>
                  {{
                    telegramAccount.username
                      ? `@${telegramAccount.username}`
                      : telegramAccount.firstName || 'Tài khoản Telegram'
                  }}
                </dd>
              </div>
              <div class="profile-page__meta-item">
                <dt>Liên kết lúc</dt>
                <dd>{{ formatDateTime(telegramAccount.linkedAt) }}</dd>
              </div>
              <div class="profile-page__meta-item">
                <dt>Trạng thái</dt>
                <dd
                  :class="
                    telegramAccount.status === 'blocked'
                      ? 'profile-page__telegram-status profile-page__telegram-status--blocked'
                      : 'profile-page__telegram-status'
                  "
                >
                  {{
                    telegramAccount.status === 'blocked'
                      ? 'Bot đang bị chặn'
                      : 'Đang hoạt động'
                  }}
                </dd>
              </div>
            </dl>
            <p
              v-if="telegramAccount.status === 'blocked'"
              class="profile-page__hint"
              data-testid="profile-telegram-blocked-hint"
            >
              Bạn đã chặn bot hoặc bot không gửi được tin. Mở Telegram, bỏ chặn
              bot rồi gõ /start để nhận lại thông báo.
            </p>
          </div>
          <p
            v-else-if="telegramMode !== 'error'"
            class="profile-page__hint"
            data-testid="profile-telegram-empty"
          >
            Chưa có tài khoản Telegram nào được liên kết.
          </p>

          <div
            v-if="isTelegramPending"
            class="profile-page__telegram-pending"
            data-testid="profile-telegram-pending"
          >
            <p
              class="profile-page__telegram-countdown"
              data-testid="profile-telegram-countdown"
            >
              <template v-if="isTelegramExpired">
                Đường dẫn liên kết đã hết hạn. Hãy tạo đường dẫn mới.
              </template>
              <template v-else>
                Đường dẫn liên kết còn hiệu lực
                <strong>{{ telegramRemainingLabel }}</strong>
              </template>
            </p>

            <template v-if="telegramDeepLink && !isTelegramExpired">
              <div class="profile-page__telegram-pending-body">
                <svg
                  v-if="telegramQr"
                  class="profile-page__telegram-qr"
                  role="img"
                  aria-label="Mã QR của đường dẫn liên kết Telegram. Quét bằng điện thoại để mở Telegram."
                  shape-rendering="crispEdges"
                  :viewBox="`0 0 ${telegramQr.size} ${telegramQr.size}`"
                  data-testid="profile-telegram-qr"
                >
                  <rect
                    class="profile-page__telegram-qr-background"
                    :width="telegramQr.size"
                    :height="telegramQr.size"
                  />
                  <path
                    class="profile-page__telegram-qr-modules"
                    :d="telegramQr.path"
                  />
                </svg>
                <div class="profile-page__telegram-pending-copy">
                  <div class="profile-page__telegram-link-row">
                    <input
                      class="p-inputtext profile-page__telegram-link-input"
                      type="text"
                      readonly
                      aria-label="Đường dẫn liên kết Telegram"
                      :value="telegramDeepLink"
                      data-testid="profile-telegram-link-input"
                    />
                    <Button
                      as="a"
                      icon="pi pi-external-link"
                      label="Mở Telegram"
                      :href="telegramDeepLink"
                      target="_blank"
                      rel="noopener noreferrer"
                      data-testid="profile-telegram-open-link"
                    />
                    <Button
                      type="button"
                      severity="secondary"
                      outlined
                      :icon="isTelegramCopied ? 'pi pi-check' : 'pi pi-copy'"
                      :label="
                        isTelegramCopied ? 'Đã sao chép' : 'Sao chép đường dẫn'
                      "
                      data-testid="profile-telegram-copy-button"
                      @click="copyTelegramLink"
                    />
                  </div>
                  <small class="profile-page__hint">
                    Mở đường dẫn trong ứng dụng Telegram rồi bấm Start. Đường
                    dẫn chỉ dùng được một lần.
                  </small>
                  <small v-if="telegramQr" class="profile-page__hint">
                    Hoặc quét mã QR bằng camera điện thoại.
                  </small>
                </div>
              </div>
            </template>
            <small
              v-else-if="!telegramDeepLink"
              class="profile-page__hint"
              data-testid="profile-telegram-lost-link"
            >
              Đường dẫn chỉ hiển thị một lần ở phiên này. Tạo đường dẫn mới để
              lấy lại đường dẫn.
            </small>
          </div>

          <p
            v-if="telegramErrorMessage"
            class="profile-page__error"
            role="alert"
            data-testid="profile-telegram-error"
          >
            {{ telegramErrorMessage }}
          </p>
          <p
            v-if="telegramSuccessMessage"
            class="profile-page__success"
            role="status"
            data-testid="profile-telegram-success"
          >
            {{ telegramSuccessMessage }}
          </p>
          <p
            v-if="telegramInfoMessage"
            class="profile-page__info"
            role="status"
            data-testid="profile-telegram-info"
          >
            {{ telegramInfoMessage }}
          </p>

          <div class="profile-page__telegram-actions">
            <Button
              v-if="telegramMode === 'error'"
              type="button"
              icon="pi pi-refresh"
              label="Thử lại"
              data-testid="profile-telegram-retry-button"
              @click="reloadTelegram"
            />
            <template v-else>
              <Button
                v-if="isTelegramPending"
                type="button"
                icon="pi pi-link"
                label="Tạo đường dẫn mới"
                :loading="isTelegramBusy"
                :disabled="isTelegramBusy"
                :title="telegramBusyTitle"
                data-testid="profile-telegram-new-link-button"
                @click="startTelegramLinking"
              />
              <Button
                v-else
                type="button"
                icon="pi pi-link"
                :label="
                  telegramAccount
                    ? 'Đổi tài khoản Telegram'
                    : 'Liên kết Telegram'
                "
                :loading="isTelegramBusy"
                :disabled="isTelegramBusy"
                :title="telegramBusyTitle"
                data-testid="profile-telegram-link-button"
                @click="startTelegramLinking"
              />
              <Button
                v-if="isTelegramPending"
                type="button"
                severity="secondary"
                outlined
                label="Hủy yêu cầu"
                :disabled="isTelegramBusy"
                :title="telegramBusyTitle"
                data-testid="profile-telegram-cancel-button"
                @click="cancelTelegramPending"
              />
              <Button
                v-if="telegramAccount"
                type="button"
                severity="danger"
                outlined
                icon="pi pi-times"
                label="Hủy liên kết"
                :disabled="isTelegramBusy"
                :title="telegramBusyTitle"
                data-testid="profile-telegram-unlink-button"
                @click="openTelegramUnlinkDialog"
              />
            </template>
          </div>
        </section>

        <AlertPreferencesPanel v-if="isTelegramEnabled" />
      </div>

      <Dialog
        v-model:visible="isTelegramUnlinkDialogVisible"
        header="Hủy liên kết Telegram"
        modal
        class="profile-page__dialog"
        :closable="!isTelegramBusy"
      >
        <p class="profile-page__dialog-text">
          Sau khi hủy, bạn sẽ không nhận thông báo biến động giá qua Telegram
          nữa. Bạn có thể liên kết lại bất cứ lúc nào.
        </p>
        <template #footer>
          <Button
            type="button"
            label="Giữ liên kết"
            severity="secondary"
            text
            :disabled="isTelegramBusy"
            data-testid="profile-telegram-cancel-unlink"
            @click="closeTelegramUnlinkDialog"
          />
          <Button
            type="button"
            label="Hủy liên kết"
            severity="danger"
            :loading="isTelegramBusy"
            :disabled="isTelegramBusy"
            data-testid="profile-telegram-confirm-unlink"
            @click="confirmTelegramUnlink"
          />
        </template>
      </Dialog>
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import FileUpload from 'primevue/fileupload'
import Password from 'primevue/password'
import { computed, onMounted } from 'vue'

import AlertPreferencesPanel from '@/components/profile/AlertPreferencesPanel.vue'
import { useProfilePage } from '@/composables/useProfilePage'
import { useQrCode } from '@/composables/useQrCode'
import { useTelegramLink } from '@/composables/useTelegramLink'
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

const {
  account: telegramAccount,
  bootstrap: bootstrapTelegram,
  cancelPending: cancelTelegramPending,
  closeUnlinkDialog: closeTelegramUnlinkDialog,
  confirmUnlink: confirmTelegramUnlink,
  copyLink: copyTelegramLink,
  deepLink: telegramDeepLink,
  enabled: isTelegramEnabled,
  errorMessage: telegramErrorMessage,
  infoMessage: telegramInfoMessage,
  isBusy: isTelegramBusy,
  isCopied: isTelegramCopied,
  isExpired: isTelegramExpired,
  isPending: isTelegramPending,
  isUnlinkDialogVisible: isTelegramUnlinkDialogVisible,
  isVisible: isTelegramVisible,
  mode: telegramMode,
  openUnlinkDialog: openTelegramUnlinkDialog,
  reload: reloadTelegram,
  remainingLabel: telegramRemainingLabel,
  startLinking: startTelegramLinking,
  successMessage: telegramSuccessMessage,
} = useTelegramLink()

const { qr: telegramQr } = useQrCode(telegramDeepLink)

const telegramBusyTitle = computed(() =>
  isTelegramBusy.value ? 'Đang xử lý, vui lòng đợi.' : undefined,
)

onMounted(() => {
  void bootstrapTelegram()
})
</script>
