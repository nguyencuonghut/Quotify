<template>
  <AdminLayout section-label="Tài khoản cá nhân" title="Hồ sơ">
    <div class="profile-page">
      <section class="profile-page__card">
        <div class="profile-page__identity">
          <div class="profile-page__avatar-shell">
            <img
              v-if="currentUser?.avatarUrl"
              :src="currentUser.avatarUrl"
              alt="Ảnh đại diện người dùng"
              class="profile-page__avatar-image"
            />
            <span v-else class="profile-page__avatar-fallback">
              {{ profileInitials }}
            </span>
          </div>

          <div class="profile-page__identity-copy">
            <p class="profile-page__eyebrow">Thông tin đăng nhập</p>
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
            <dd>{{ currentUser?.roles?.join(', ') || 'Chưa gán vai trò' }}</dd>
          </div>

          <div class="profile-page__meta-item">
            <dt>Quyền</dt>
            <dd>
              {{ currentUser?.permissions?.length || 0 }} quyền đã được cấp
            </dd>
          </div>
        </dl>
      </section>
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import { useProfilePage } from '@/composables/useProfilePage'
import AdminLayout from '@/layouts/AdminLayout.vue'

const { currentUser, profileInitials, formatDateTime } = useProfilePage()
</script>
