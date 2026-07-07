<template>
  <div class="logout-view">
    <div class="logout-shell">
      <div class="logout-brand">
        <div class="logout-logo">AH</div>
        <div>
          <div class="logout-brand-title">Asisten Hukum SPBE</div>
          <div class="logout-brand-subtitle">Chatbot Hukum untuk Tata Kelola Digital Pemerintah</div>
        </div>
      </div>

      <div class="logout-card">
        <div class="logout-icon" :class="status">{{ iconText }}</div>
        <p class="eyebrow">Konfirmasi Keluar</p>
        <h1>{{ titleText }}</h1>
        <p class="logout-message">{{ message }}</p>

        <div v-if="user" class="identity-card">
          <div class="identity-avatar">{{ userInitial }}</div>
          <div class="identity-details">
            <div class="identity-label">Akun yang sedang login</div>
            <div class="identity-name">{{ user.display_name }}</div>
            <div class="identity-email">{{ user.username }}</div>
            <div class="role-list">
              <span v-for="role in roleLabels" :key="role" class="role-chip">{{ role }}</span>
            </div>
          </div>
        </div>

        <div v-if="status === 'confirm'" class="logout-actions">
          <button type="button" class="secondary-btn" @click="cancelLogout">
            Batal
          </button>
          <button type="button" class="danger-btn" @click="confirmLogout">
            Ya, Keluar
          </button>
        </div>

        <div v-else-if="status === 'signed-out'" class="logout-actions single">
          <router-link to="/login" class="danger-btn link-btn">Ke Halaman Login</router-link>
        </div>

        <div v-else class="progress-row">
          <span class="spinner"></span>
          Mengakhiri sesi dengan aman...
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { formatRoleLabel, getCurrentUserProfile, isAuthenticated, logout } from '@/services/auth'

const router = useRouter()
const user = ref(getCurrentUserProfile())
const status = ref(isAuthenticated() ? 'confirm' : 'signed-out')
const message = ref(
  isAuthenticated()
    ? 'Pastikan konsultasi Anda sudah selesai. Setelah keluar, Anda perlu login kembali untuk mengakses layanan konsultasi, dokumen hukum, dan pengaturan model.'
    : 'Anda sudah keluar dari sistem. Silakan login kembali untuk melanjutkan.'
)

const roleLabels = computed(() => {
  if (!user.value?.roles?.length) return ['Pengguna']
  return user.value.roles.map(formatRoleLabel)
})

const userInitial = computed(() => {
  const source = user.value?.display_name || user.value?.username || 'P'
  return source.charAt(0).toUpperCase()
})

const iconText = computed(() => {
  if (status.value === 'processing') return '…'
  if (status.value === 'signed-out') return '✓'
  return '!'
})

const titleText = computed(() => {
  if (status.value === 'processing') return 'Sedang keluar dari sistem'
  if (status.value === 'signed-out') return 'Sesi telah berakhir'
  return 'Anda yakin ingin keluar?'
})

function cancelLogout() {
  router.replace('/')
}

async function confirmLogout() {
  status.value = 'processing'
  message.value = 'Token akses dan refresh session sedang dihapus dari perangkat ini.'

  try {
    await logout()
    message.value = 'Sesi berhasil diakhiri. Mengarahkan ke halaman login...'
  } catch (error) {
    console.error('Logout failed:', error)
    message.value = 'Sesi lokal dihapus. Mengarahkan ke halaman login...'
  } finally {
    status.value = 'signed-out'
    setTimeout(() => router.replace('/login'), 700)
  }
}
</script>

<style scoped>
.logout-view {
  min-height: 100vh;
  min-height: 100dvh;
  background: linear-gradient(160deg, #1a3a6b 0%, #0f2444 52%, #071528 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 28px;
}

.logout-shell {
  width: min(520px, 100%);
}

.logout-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #ffffff;
  margin-bottom: 18px;
}

.logout-logo {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  background: var(--color-gold);
  color: var(--color-navy);
  font-family: var(--font-display);
  font-weight: 700;
  border-radius: 6px;
}

.logout-brand-title {
  font-family: var(--font-display);
  font-weight: 700;
  letter-spacing: -0.2px;
}

.logout-brand-subtitle {
  margin-top: 2px;
  color: rgba(255, 255, 255, 0.52);
  font-size: 9px;
  letter-spacing: 1.6px;
  text-transform: uppercase;
}

.logout-card {
  background: rgba(255, 255, 255, 0.97);
  border: 1px solid rgba(201, 168, 76, 0.35);
  border-radius: 14px;
  box-shadow: 0 28px 80px rgba(0, 0, 0, 0.28);
  padding: 34px;
}

.logout-icon {
  width: 54px;
  height: 54px;
  border-radius: 18px;
  display: grid;
  place-items: center;
  background: rgba(201, 168, 76, 0.14);
  color: var(--color-navy);
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 700;
  margin-bottom: 18px;
}

.logout-icon.processing {
  color: var(--color-gold-dark);
}

.logout-icon.signed-out {
  background: rgba(79, 151, 102, 0.13);
  color: #2f7a4a;
}

.eyebrow {
  margin: 0 0 6px;
  font-family: var(--font-ui);
  font-size: 10px;
  letter-spacing: 1.8px;
  text-transform: uppercase;
  color: var(--color-gold-dark);
}

h1 {
  margin: 0 0 10px;
  color: var(--color-navy);
  font-family: var(--font-display);
  font-size: 28px;
  letter-spacing: -0.5px;
}

.logout-message {
  margin: 0;
  color: var(--color-text-muted);
  font-size: 14px;
  line-height: 1.7;
}

.identity-card {
  display: flex;
  gap: 14px;
  margin: 24px 0;
  padding: 16px;
  background: #f7f4ec;
  border: 1px solid rgba(201, 168, 76, 0.25);
  border-radius: 12px;
}

.identity-avatar {
  width: 46px;
  height: 46px;
  flex: 0 0 auto;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: var(--color-navy);
  color: var(--color-gold);
  font-family: var(--font-display);
  font-weight: 700;
}

.identity-details {
  min-width: 0;
}

.identity-label {
  font-family: var(--font-ui);
  font-size: 9px;
  letter-spacing: 1.2px;
  text-transform: uppercase;
  color: var(--color-text-muted);
}

.identity-name {
  margin-top: 4px;
  color: var(--color-navy);
  font-weight: 700;
  font-size: 15px;
}

.identity-email {
  margin-top: 2px;
  color: var(--color-text-muted);
  font-size: 12px;
  word-break: break-word;
}

.role-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}

.role-chip {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  background: rgba(26, 58, 107, 0.08);
  color: var(--color-navy);
  padding: 4px 8px;
  font-family: var(--font-ui);
  font-size: 10px;
  letter-spacing: 0.2px;
}

.logout-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 26px;
}

.logout-actions.single {
  justify-content: flex-start;
}

.secondary-btn,
.danger-btn {
  border: 0;
  border-radius: 8px;
  cursor: pointer;
  font-family: var(--font-ui);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.4px;
  padding: 11px 16px;
  text-decoration: none;
  transition: transform 0.15s, box-shadow 0.15s, background 0.15s;
}

.secondary-btn {
  background: #edf1f7;
  color: var(--color-navy);
}

.danger-btn {
  background: #8f2f2f;
  color: #ffffff;
  box-shadow: 0 10px 24px rgba(143, 47, 47, 0.2);
}

.secondary-btn:hover,
.danger-btn:hover {
  transform: translateY(-1px);
}

.danger-btn:hover {
  background: #7b2525;
}

.link-btn {
  display: inline-flex;
}

.progress-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 24px;
  color: var(--color-text-muted);
  font-size: 13px;
}

.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(26, 58, 107, 0.15);
  border-top-color: var(--color-navy);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 560px) {
  .logout-card {
    padding: 26px;
  }

  .logout-actions {
    flex-direction: column-reverse;
  }

  .secondary-btn,
  .danger-btn {
    width: 100%;
    text-align: center;
  }
}
</style>
