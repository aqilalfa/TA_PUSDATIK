<template>
  <nav class="topbar app-header">
    <div class="topbar-brand">
      <div class="topbar-logo">B</div>
      <div>
        <div class="topbar-title">SPBE Asisten</div>
        <div class="topbar-subtitle">Badan Siber dan Sandi Negara</div>
      </div>
    </div>

    <div class="topbar-nav app-header-nav">
      <router-link to="/home" class="topbar-nav-link" :class="{ active: active === 'home' }">Beranda</router-link>
      <router-link to="/" class="topbar-nav-link" :class="{ active: active === 'chat' }">Chat</router-link>
      <router-link to="/documents" class="topbar-nav-link" :class="{ active: active === 'documents' }">Dokumen</router-link>

      <button
        v-if="showClearChat"
        class="topbar-action-link danger"
        type="button"
        @click="$emit('clear-chat')"
      >
        Hapus Chat
      </button>

      <div v-if="currentUser" class="app-account" :title="`${currentUser.display_name} • ${currentUser.username}`">
        <div class="app-account-avatar">{{ currentUserInitial }}</div>
        <div class="app-account-meta">
          <span class="app-account-kicker">Masuk sebagai</span>
          <span class="app-account-name">{{ currentUser.display_name }}</span>
          <span class="app-account-role">{{ currentUserRoleText }}</span>
        </div>
      </div>

      <router-link to="/logout" class="topbar-nav-link logout-nav-link">Keluar</router-link>

      <div v-if="status" class="status-dot" :class="status">
        {{ statusText }}
      </div>
    </div>
  </nav>
</template>

<script setup>
import { computed, ref } from 'vue'
import { formatRoleLabel, getCurrentUserProfile } from '@/services/auth'

const props = defineProps({
  active: { type: String, default: '' },
  status: { type: String, default: '' },
  showClearChat: { type: Boolean, default: false }
})

defineEmits(['clear-chat'])

const currentUser = ref(getCurrentUserProfile())

const currentUserInitial = computed(() => {
  const source = currentUser.value?.display_name || currentUser.value?.username || 'P'
  return source.charAt(0).toUpperCase()
})

const currentUserRoleText = computed(() => {
  const roles = currentUser.value?.roles || []
  if (!roles.length) return 'Pengguna'
  return roles.map(formatRoleLabel).join(', ')
})

const statusText = computed(() => {
  if (props.status === 'connected') return 'Terhubung'
  if (props.status === 'disconnected') return 'Terputus'
  return 'Menghubungkan...'
})
</script>

<style scoped>
.app-header {
  gap: 18px;
}

.app-header-nav {
  flex-wrap: wrap;
  justify-content: flex-end;
}

.topbar-action-link {
  background: transparent;
  border: 1px solid transparent;
  color: rgba(255, 255, 255, 0.5);
  cursor: pointer;
  font-family: var(--font-ui);
  font-size: 11px;
  letter-spacing: 0.4px;
  padding: 6px 8px;
  border-radius: 2px;
  transition: color 0.15s, border-color 0.15s, background 0.15s;
}

.topbar-action-link:hover {
  color: white;
  border-color: rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.07);
}

.topbar-action-link.danger:hover {
  color: #ffb4a8;
  border-color: rgba(255, 180, 168, 0.22);
}

.app-account {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-left: 8px;
  padding: 7px 12px 7px 7px;
  border: 1px solid rgba(201, 168, 76, 0.32);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.075);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05);
  max-width: 230px;
}

.app-account-avatar {
  width: 32px;
  height: 32px;
  flex: 0 0 auto;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: var(--color-gold);
  color: var(--color-navy);
  font-family: var(--font-display);
  font-size: 13px;
  font-weight: 700;
}

.app-account-meta {
  display: flex;
  flex-direction: column;
  min-width: 0;
  line-height: 1.15;
}

.app-account-kicker {
  color: rgba(255, 255, 255, 0.38);
  font-family: var(--font-ui);
  font-size: 8px;
  letter-spacing: 1.3px;
  text-transform: uppercase;
}

.app-account-name {
  margin-top: 2px;
  color: rgba(255, 255, 255, 0.92);
  font-family: var(--font-ui);
  font-size: 11px;
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.app-account-role {
  margin-top: 2px;
  color: rgba(201, 168, 76, 0.9);
  font-size: 9px;
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.logout-nav-link:hover {
  color: #ffb4a8;
}

@media (max-width: 920px) {
  .app-account-meta {
    display: none;
  }

  .app-account {
    padding: 5px;
    gap: 0;
    border-radius: 999px;
  }
}
</style>
