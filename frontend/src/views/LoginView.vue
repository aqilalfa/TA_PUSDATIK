<template>
  <div class="login-view">
    <!-- Topbar matches HomeView -->
    <nav class="topbar">
      <div class="topbar-brand">
        <div class="topbar-logo">AH</div>
        <div>
          <div class="topbar-title">Asisten Hukum SPBE</div>
          <div class="topbar-subtitle">Chatbot Hukum untuk Tata Kelola Digital Pemerintah</div>
        </div>
      </div>
    </nav>

    <!-- Login Container -->
    <div class="login-container">
      <div class="login-card">
        <div class="login-header">
          <div class="login-icon">🔒</div>
          <h2 class="login-title">Masuk ke Sistem Internal</h2>
          <p class="login-subtitle">Masuk untuk mengakses konsultasi regulasi, kebijakan, dan tata kelola digital SPBE.</p>
        </div>

        <form @submit.prevent="handleLogin" class="login-form">
          <!-- Error Message -->
          <transition name="fade">
            <div v-if="errorMsg" class="error-msg">
              <svg class="error-icon" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="12"></line>
                <line x1="12" y1="16" x2="12.01" y2="16"></line>
              </svg>
              {{ errorMsg }}
            </div>
          </transition>

          <!-- Email Input -->
          <div class="form-group">
            <label for="email" class="form-label">Alamat Email</label>
            <div class="input-wrapper">
              <input 
                type="email" 
                id="email" 
                v-model="email" 
                placeholder="admin@bssn.go.id" 
                required
                :disabled="loading"
                class="form-input"
              />
              <svg v-if="email" class="input-check" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
            </div>
          </div>

          <!-- Password Input -->
          <div class="form-group">
            <label for="password" class="form-label">Kata Sandi</label>
            <div class="input-wrapper">
              <input 
                type="password" 
                id="password" 
                v-model="password" 
                placeholder="••••••••" 
                required
                :disabled="loading"
                class="form-input"
              />
            </div>
          </div>

          <!-- Submit Button -->
          <button type="submit" class="login-button" :disabled="loading">
            <span v-if="loading" class="button-spinner"></span>
            <span v-else class="button-text">MASUK →</span>
          </button>
        </form>
        
        <div class="login-footer">
          <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
          </svg>
          Sistem internal pemerintah. Data konsultasi tidak digunakan untuk pelatihan model publik.
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { login } from '@/services/auth'
import { SESSION_EXPIRED_NOTICE_KEY } from '@/services/api'

const router = useRouter()
const route = useRoute()

const email = ref('')
const password = ref('')
const errorMsg = ref('')
const loading = ref(false)

onMounted(() => {
  const sessionNotice = window.sessionStorage.getItem(SESSION_EXPIRED_NOTICE_KEY)
  if (sessionNotice) {
    errorMsg.value = sessionNotice
    window.sessionStorage.removeItem(SESSION_EXPIRED_NOTICE_KEY)
  } else if (route.query.reason === 'session-expired') {
    errorMsg.value = 'Sesi Anda telah berakhir. Silakan login kembali.'
  }
})

const handleLogin = async () => {
  errorMsg.value = ''
  loading.value = true
  try {
    await login(email.value, password.value)
    // Redirect to requested page or home
    const redirectPath = route.query.redirect || '/'
    router.push(redirectPath)
  } catch (error) {
    console.error('Login failed', error)
    if (error.response && error.response.status === 401) {
      errorMsg.value = 'Email atau password salah.'
    } else {
      errorMsg.value = 'Terjadi kesalahan pada sistem. Silakan coba lagi.'
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-view {
  min-height: 100vh;
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
  background: var(--color-cream);
}

.login-container {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  background: linear-gradient(160deg, var(--color-navy) 0%, var(--color-navy-darker) 55%, var(--color-navy-darkest) 100%);
  position: relative;
  overflow: hidden;
}


.login-card {
  width: 100%;
  max-width: 420px;
  background: #ffffff;
  border-radius: 4px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
  padding: 40px;
  position: relative;
  z-index: 1;
  border-top: 4px solid var(--color-gold);
  animation: slideIn 0.3s ease-out;
}

.login-header {
  text-align: center;
  margin-bottom: 30px;
}

.login-icon {
  font-size: 32px;
  margin-bottom: 15px;
  display: inline-block;
  background: #eef2f9;
  width: 64px;
  height: 64px;
  line-height: 64px;
  border-radius: 50%;
  color: var(--color-navy);
}

.login-title {
  font-family: var(--font-display);
  font-size: 24px;
  font-weight: 700;
  color: var(--color-navy);
  margin-bottom: 8px;
}

.login-subtitle {
  font-size: 14px;
  color: #666666;
  line-height: 1.5;
}

/* Error Message */
.error-msg {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  background: var(--color-danger-bg);
  color: var(--color-danger-strong);
  padding: 12px 14px;
  border-radius: 3px;
  font-size: 12px;
  margin-bottom: 20px;
  border: 1px solid rgba(211, 47, 47, 0.28);
  animation: slideDown 0.25s ease-out;
}

.error-icon {
  color: var(--color-danger-strong);
  flex-shrink: 0;
  margin-top: 2px;
}

/* Form Group */
.form-group {
  margin-bottom: 20px;
}

.form-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--color-navy);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
  font-family: var(--font-ui);
}

.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.form-input {
  width: 100%;
  padding: 12px 16px;
  padding-right: 36px;
  font-family: var(--font-ui);
  font-size: 14px;
  border: 1px solid var(--color-border);
  border-radius: 3px;
  background: var(--color-input-bg);
  color: var(--color-text);
  transition: all 0.15s ease-in-out;
}

.form-input:hover:not(:disabled) {
  border-color: var(--color-input-border-hover);
}

.form-input:focus {
  outline: none;
  border-color: var(--color-gold);
  background: var(--color-white);
  box-shadow: 0 0 0 3px rgba(201, 168, 76, 0.1);
}

.form-input::placeholder {
  color: var(--color-text-placeholder);
}

.form-input:disabled {
  opacity: 0.65;
  cursor: not-allowed;
  background: var(--color-input-bg-disabled);
}

.input-check {
  position: absolute;
  right: 12px;
  color: var(--color-gold);
  stroke-width: 3;
  animation: popIn 0.2s ease-out;
}

/* Login Button */
.login-button {
  width: 100%;
  background: var(--color-gold);
  color: var(--color-navy);
  border: none;
  padding: 14px;
  font-family: var(--font-ui);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  border-radius: 3px;
  cursor: pointer;
  transition: all 0.2s ease-in-out;
  margin-top: 10px;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 46px;
  position: relative;
}

.login-button:hover:not(:disabled) {
  background: var(--color-gold-hover);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.login-button:active:not(:disabled) {
  transform: translateY(0);
}

.login-button:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.button-spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(26, 58, 107, 0.3);
  border-top-color: var(--color-navy);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.button-text {
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Login Footer */
.login-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid var(--color-border);
  text-align: center;
  font-size: 11px;
  color: var(--color-text-muted);
  line-height: 1.5;
}

.login-footer svg {
  width: 13px;
  height: 13px;
  color: var(--color-text-muted);
  flex-shrink: 0;
}

/* Responsive Design */
@media (max-width: 600px) {
  .login-card {
    padding: 30px 24px;
    border-radius: 3px;
  }

  .login-icon {
    width: 56px;
    height: 56px;
    line-height: 56px;
    font-size: 28px;
  }

  .login-title {
    font-size: 20px;
    margin-bottom: 8px;
  }

  .login-subtitle {
    font-size: 13px;
  }

  .form-label {
    font-size: 11px;
  }

  .form-input {
    padding: 11px 14px;
    font-size: 13px;
  }

  .login-button {
    padding: 12px;
    font-size: 12px;
    min-height: 44px;
  }

  .login-footer {
    font-size: 10px;
  }
}

@media (max-width: 400px) {
  .login-container {
    padding: 20px 16px;
  }

  .login-card {
    padding: 24px 18px;
  }

  .login-title {
    font-size: 18px;
  }

  .login-subtitle {
    font-size: 12px;
  }
}

/* Animations */
@keyframes slideIn {
  from {
    opacity: 0;
    transform: scale(0.95);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes popIn {
  from {
    opacity: 0;
    transform: scale(0.8);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

/* Vue Transition */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease-in-out;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.fade-enter-to,
.fade-leave-from {
  opacity: 1;
}
</style>
