<template>
  <AdminLayout section-label="Điều hướng" title="Không tìm thấy trang">
    <section class="not-found-page">
      <div class="not-found-page__icon" aria-hidden="true">
        <i class="pi pi-compass" />
      </div>
      <div class="not-found-page__content">
        <p class="not-found-page__eyebrow">404</p>
        <h2 class="not-found-page__title">
          Trang bạn đang mở không tồn tại.
        </h2>
        <p class="not-found-page__body">
          Đường dẫn này có thể đã được thay đổi, bị gỡ khỏi Quotify hoặc không
          còn nằm trong phạm vi sản phẩm hiện tại.
        </p>
        <RouterLink class="not-found-page__link" to="/">
          Quay về bảng điều khiển
        </RouterLink>
      </div>
    </section>
  </AdminLayout>
</template>

<script setup lang="ts">
import { RouterLink } from 'vue-router'

import AdminLayout from '@/layouts/AdminLayout.vue'
</script>
