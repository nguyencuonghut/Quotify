<template>
  <section class="login-page">
    <div class="login-page__card" aria-labelledby="login-title">
      <header class="login-page__header">
        <img alt="" class="login-page__logo" src="/favico.png" />

        <div>
          <h1 id="login-title" class="login-page__title">Quotify</h1>
          <p class="login-page__subtitle">Hệ thống phân tích báo giá nguyên liệu</p>
        </div>
      </header>

      <div v-if="generalError" class="login-page__general-error">
        <i class="pi pi-exclamation-triangle" aria-hidden="true" />
        <span>{{ generalError }}</span>
      </div>

      <form class="login-page__form" @submit.prevent="submitLogin">
        <div class="login-page__field">
          <label class="login-page__label required" for="email">Email</label>
          <InputText
            id="email"
            v-model="email"
            autocomplete="username"
            class="login-page__input"
            fluid
            placeholder="Nhập email đăng nhập"
            type="email"
            v-bind="emailProps"
          />
          <small v-if="errors.email" class="login-page__error">
            {{ errors.email }}
          </small>
        </div>

        <div class="login-page__field">
          <label class="login-page__label required" for="password"
            >Mật khẩu</label
          >
          <Password
            id="password"
            v-model="password"
            :feedback="false"
            :inputProps="{ autocomplete: 'current-password' }"
            class="login-page__password"
            fluid
            placeholder="Nhập mật khẩu"
            toggle-mask
            v-bind="passwordProps"
          />

          <small v-if="errors.password" class="login-page__error">
            {{ errors.password }}
          </small>
        </div>

        <Button
          :disabled="isSubmitting"
          :loading="isSubmitting"
          class="login-page__submit"
          icon="pi pi-sign-in"
          label="Đăng nhập"
          type="submit"
        />
      </form>
    </div>
  </section>
</template>

<script setup lang="ts">
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import { useRouter, useRoute } from 'vue-router'

import { useLoginPage } from '@/composables/useLoginPage'

const route = useRoute()
const router = useRouter()

const {
  email,
  emailProps,
  errors,
  generalError,
  isSubmitting,
  password,
  passwordProps,
  submitLogin,
} = useLoginPage(async () => {
  const redirectTarget =
    typeof route.query.redirect === 'string' ? route.query.redirect : '/'

  await router.replace(redirectTarget)
})
</script>
