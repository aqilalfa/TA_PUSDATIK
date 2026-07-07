<template>
  <nav class="topbar app-header">
    <!-- Kiri: Menu Navigasi -->
    <div class="topbar-nav main-nav">
      <router-link to="/" class="topbar-nav-link" :class="{ active: active === 'home' }">Beranda</router-link>
      <router-link to="/chat" class="topbar-nav-link" :class="{ active: active === 'chat' }">Layanan</router-link>
      <router-link v-if="canManageDocuments" to="/documents" class="topbar-nav-link" :class="{ active: active === 'documents' }">Dasar Hukum</router-link>
    </div>

    <!-- Kanan: Akun & Status -->
    <div class="topbar-nav app-header-actions">
      <button
        v-if="showClearChat"
        class="topbar-action-link danger"
        type="button"
        @click="$emit('clear-chat')"
      >
        <span class="clear-chat-label">Hapus Konsultasi</span>
        <span class="clear-chat-short" aria-hidden="true">Hapus</span>
      </button>

      <div v-if="currentUser" class="app-account" :title="currentUserRoleText">
        <div class="app-account-avatar">{{ currentUserInitial }}</div>
        <span class="app-account-name">{{ currentUser.display_name }}</span>
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
import { formatRoleLabel, getCurrentUserProfile, isAdminUser } from '@/services/auth'

const props = defineProps({
  active: { type: String, default: '' },
  status: { type: String, default: '' },
  showClearChat: { type: Boolean, default: false }
})

defineEmits(['clear-chat'])

const currentUser = ref(getCurrentUserProfile())
const canManageDocuments = computed(() => isAdminUser(currentUser.value))

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
  justify-content: space-between;
  padding: 14px 32px;
}

.main-nav {
  gap: 8px;
}

.app-header-actions {
  gap: 12px;
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
  margin-left: 4px;
  margin-right: 4px;
  padding: 4px 12px 4px 4px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.04);
  transition: background 0.2s;
  cursor: default;
}

.app-account:hover {
  background: rgba(255, 255, 255, 0.08);
}

.app-account-avatar {
  width: 28px;
  height: 28px;
  flex: 0 0 auto;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: var(--color-gold);
  color: var(--color-navy);
  font-family: var(--font-display);
  font-size: 11px;
  font-weight: 700;
}

.app-account-name {
  color: rgba(255, 255, 255, 0.9);
  font-family: var(--font-ui);
  font-size: 12px;
  font-weight: 600;
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.logout-nav-link:hover {
  color: #ffb4a8;
}

.clear-chat-short {
  display: none;
}

@media (max-width: 768px) {
  .app-header {
    gap: 10px;
    padding: 12px 16px;
  }

  .main-nav,
  .app-header-actions {
    min-width: 0;
  }

  .main-nav {
    gap: 4px;
    overflow-x: auto;
    scrollbar-width: none;
  }

  .main-nav::-webkit-scrollbar {
    display: none;
  }

  .app-header-actions {
    gap: 6px;
    flex-shrink: 0;
  }

  .topbar-nav-link,
  .topbar-action-link {
    min-height: 34px;
    padding: 7px 9px;
    white-space: nowrap;
  }

  .app-account-name {
    display: none;
  }
  
  .app-account {
    margin-inline: 0;
    padding: 3px;
    background: transparent;
  }
}

@media (max-width: 640px) {
  .app-header {
    padding: 10px 10px 10px 72px;
  }

  .main-nav {
    flex: 1 1 auto;
  }

  .topbar-nav-link,
  .topbar-action-link {
    font-size: 10px;
    letter-spacing: 0.2px;
    padding-inline: 8px;
  }

  .clear-chat-label {
    display: none;
  }

  .clear-chat-short {
    display: inline;
  }

  .logout-nav-link {
    max-width: 44px;
    overflow: hidden;
    text-overflow: clip;
  }

  .status-dot {
    width: 24px;
    justify-content: center;
    gap: 0;
    overflow: hidden;
    color: transparent;
    font-size: 0;
  }

  .status-dot::before {
    flex: 0 0 auto;
  }
}

@media (max-width: 420px) {
  .app-header {
    align-items: stretch;
    flex-wrap: wrap;
    padding-left: 10px;
  }

  .main-nav {
    order: 2;
    width: 100%;
  }

  .app-header-actions {
    order: 1;
    width: 100%;
    justify-content: flex-end;
  }

  .topbar-nav-link,
  .topbar-action-link {
    min-height: 36px;
  }
}
</style>
