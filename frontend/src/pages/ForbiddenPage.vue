<template>
  <AdminLayout section-label="Phân quyền" title="Không có quyền truy cập">
    <section class="forbidden-page">
      <p class="forbidden-page__eyebrow">Kiểm soát truy cập</p>
      <h2 class="forbidden-page__title">
        Tài khoản hiện tại không có quyền để mở màn hình này.
      </h2>
      <p class="forbidden-page__body">
        Cơ chế kiểm soát truy cập chỉ phản ánh quyền do backend trả về trong
        <code>/api/v1/auth/me</code>. Hãy liên hệ quản trị viên nếu cần mở thêm
        quyền.
      </p>
      <RouterLink class="forbidden-page__link" to="/">
        Quay về bảng điều khiển
      </RouterLink>
    </section>
  </AdminLayout>
</template>

<script setup lang="ts">
import { RouterLink } from 'vue-router'

import AdminLayout from '@/layouts/AdminLayout.vue'
</script>
