<template>
  <aside class="sidebar" :class="{ collapsed: collapsed }">
    <div class="sidebar-header">
      <div v-if="!collapsed" class="sidebar-label">Sesi Percakapan</div>
      <button @click="$emit('new-chat')" class="new-chat-btn" :title="collapsed ? 'Sesi Baru' : ''">
        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <line x1="12" y1="5" x2="12" y2="19"></line>
          <line x1="5" y1="12" x2="19" y2="12"></line>
        </svg>
        <span v-if="!collapsed">Sesi Baru</span>
      </button>
    </div>

    <div class="sidebar-sessions" v-if="!collapsed">
      <div v-if="sessions.length === 0" class="no-sessions">
        Belum ada percakapan
      </div>
      <template v-else>
        <template v-for="group in groupedSessions" :key="group.label">
          <div class="session-group-label">{{ group.label }}</div>
          <div
            v-for="session in group.sessions"
            :key="session.id"
            class="session-item"
            :class="{ active: currentSessionId === session.id }"
            @click="onSessionClick(session)"
          >
            <template v-if="editingSessionId !== session.id">
              <div class="session-item-content">
                <span class="session-title">{{ session.title }}</span>
              </div>
              <button
                class="session-rename-btn"
                @click.stop="startEdit(session)"
                title="Ubah nama"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                </svg>
              </button>
              <button @click.stop="$emit('delete-session', session.id)" class="session-delete-btn" title="Hapus sesi">
                <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            </template>
            <template v-else>
              <input
                class="session-rename-input"
                v-model="editingTitle"
                :ref="setRenameInput"
                @keydown.enter.prevent="commitEdit"
                @keydown.escape.prevent="cancelEdit"
                @blur="commitEdit"
                @click.stop
              />
            </template>
          </div>
        </template>
      </template>
    </div>

    <div class="sidebar-footer" v-if="!collapsed">
      <router-link to="/documents" class="sidebar-footer-link">
        <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
        </svg>
        <span>Kelola Dokumen</span>
      </router-link>
      <div class="model-selector">
        <label class="model-label">Model</label>
        <select :value="selectedModel" @change="onModelChange" class="model-select">
          <option v-for="model in models" :key="model.name" :value="model.name">
            {{ model.name }}
          </option>
        </select>
      </div>
    </div>

    <button @click="$emit('toggle-sidebar')" class="collapse-btn" :title="collapsed ? 'Buka sidebar' : 'Tutup sidebar'">
      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path v-if="!collapsed" d="M15 18l-6-6 6-6"/>
        <path v-else d="M9 18l6-6-6-6"/>
      </svg>
    </button>
  </aside>
</template>

<script setup>
import { computed, ref, nextTick } from 'vue'

const props = defineProps({
  collapsed: { type: Boolean, default: false },
  sessions: { type: Array, default: () => [] },
  currentSessionId: { type: String, default: null },
  models: { type: Array, default: () => [] },
  selectedModel: { type: String, default: '' }
})

const emit = defineEmits([
  'toggle-sidebar',
  'new-chat',
  'load-session',
  'delete-session',
  'rename-session',
  'update:selectedModel',
  'model-change'
])

const editingSessionId = ref(null)
const editingTitle = ref('')
const editingOriginalTitle = ref('')
const renameInput = ref(null)
const skipBlur = ref(false)

const GROUPS = [
  { label: 'HARI INI',    test: (d) => d === 0 },
  { label: 'KEMARIN',     test: (d) => d === 1 },
  { label: '7 HARI LALU', test: (d) => d >= 2 && d <= 7 },
  { label: 'LEBIH LAMA',  test: (d) => d > 7 },
]

const groupedSessions = computed(() => {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return GROUPS
    .map(({ label, test }) => ({
      label,
      sessions: props.sessions.filter((s) => {
        const d = new Date(s.updated_at)
        d.setHours(0, 0, 0, 0)
        const diffDays = Math.round((today - d) / 86400000)
        return test(diffDays)
      })
    }))
    .filter(({ sessions }) => sessions.length > 0)
})

function onSessionClick(session) {
  if (editingSessionId.value === session.id) return
  emit('load-session', session.id)
}

function startEdit(session) {
  editingSessionId.value = session.id
  editingTitle.value = session.title
  editingOriginalTitle.value = session.title
  nextTick(() => renameInput.value?.focus())
}

function commitEdit() {
  if (!editingSessionId.value || skipBlur.value) {
    skipBlur.value = false
    return
  }
  const trimmed = editingTitle.value.trim()
  if (trimmed && trimmed !== editingOriginalTitle.value) {
    emit('rename-session', { id: editingSessionId.value, title: trimmed })
  }
  editingSessionId.value = null
}

function cancelEdit() {
  skipBlur.value = true
  editingSessionId.value = null
  editingTitle.value = ''
}

function setRenameInput(el) {
  renameInput.value = el
}

function onModelChange(event) {
  const model = event.target.value
  emit('update:selectedModel', model)
  emit('model-change', model)
}
</script>

<style scoped>
.sidebar {
  width: 240px;
  background: var(--color-navy-dark);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  overflow: hidden;
  position: relative;
  transition: width 0.2s ease;
  border-right: 1px solid rgba(201, 168, 76, 0.12);
}

.sidebar.collapsed {
  width: 48px;
}

.sidebar-header {
  padding: 14px 14px 10px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.sidebar-label {
  font-size: 9px;
  letter-spacing: 2px;
  color: var(--color-gold);
  text-transform: uppercase;
  font-family: var(--font-ui);
}

.new-chat-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  padding: 8px;
  background: var(--color-gold);
  color: var(--color-navy);
  border: none;
  border-radius: 2px;
  font-size: 11px;
  font-weight: 600;
  font-family: var(--font-ui);
  letter-spacing: 0.5px;
  cursor: pointer;
  transition: background 0.15s;
}

.new-chat-btn:hover {
  background: var(--color-gold-hover);
}

.sidebar-sessions {
  flex: 1;
  overflow-y: auto;
  padding: 6px 0;
  scrollbar-width: thin;
  scrollbar-color: rgba(255,255,255,0.1) transparent;
}

.sidebar-sessions::-webkit-scrollbar { width: 3px; }
.sidebar-sessions::-webkit-scrollbar-track { background: transparent; }
.sidebar-sessions::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 2px; }

.session-group-label {
  font-size: 8px;
  letter-spacing: 1.5px;
  color: rgba(255, 255, 255, 0.25);
  text-transform: uppercase;
  padding: 8px 14px 4px;
  font-family: var(--font-ui);
}

.no-sessions {
  padding: 20px 14px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.25);
  font-style: italic;
  font-family: var(--font-body);
  text-align: center;
}

.session-item {
  display: flex;
  align-items: center;
  padding: 8px 14px;
  cursor: pointer;
  border-left: 2px solid transparent;
  transition: background 0.15s, border-color 0.15s;
  gap: 6px;
}

.session-item:hover {
  background: rgba(255, 255, 255, 0.05);
}

.session-item.active {
  background: rgba(201, 168, 76, 0.1);
  border-left-color: var(--color-gold);
}

.session-item-content {
  flex: 1;
  min-width: 0;
}

.session-title {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.65);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: block;
  font-family: var(--font-ui);
}

.session-item.active .session-title {
  color: rgba(255, 255, 255, 0.9);
}

.session-rename-btn,
.session-delete-btn {
  background: none;
  border: none;
  cursor: pointer;
  padding: 2px;
  display: flex;
  align-items: center;
  border-radius: 2px;
  flex-shrink: 0;
  opacity: 0;
  transition: color 0.15s, background 0.15s;
}

.session-item:hover .session-rename-btn,
.session-item:hover .session-delete-btn {
  opacity: 1;
}

.session-rename-btn {
  color: rgba(255, 255, 255, 0.3);
}

.session-rename-btn:hover {
  color: var(--color-gold);
  background: rgba(201, 168, 76, 0.1);
}

.session-delete-btn {
  color: rgba(255, 255, 255, 0.2);
}

.session-delete-btn:hover {
  color: #e74c3c;
  background: rgba(231, 76, 60, 0.1);
}

.session-rename-input {
  flex: 1;
  background: transparent;
  border: none;
  border-bottom: 1px solid var(--color-gold);
  color: rgba(255, 255, 255, 0.9);
  font-size: 11px;
  font-family: var(--font-ui);
  padding: 1px 2px;
  outline: none;
  min-width: 0;
}

.sidebar-footer {
  padding: 10px 14px 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.sidebar-footer-link {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.4);
  cursor: pointer;
  padding: 5px 0;
  transition: color 0.15s;
  text-decoration: none;
  font-family: var(--font-ui);
}

.sidebar-footer-link:hover {
  color: rgba(255, 255, 255, 0.75);
}

.model-selector {
  display: flex;
  align-items: center;
  gap: 6px;
  padding-top: 4px;
  border-top: 1px solid rgba(255,255,255,0.05);
}

.model-label {
  font-size: 9px;
  color: rgba(255, 255, 255, 0.3);
  letter-spacing: 1px;
  text-transform: uppercase;
  white-space: nowrap;
  font-family: var(--font-ui);
}

.model-select {
  flex: 1;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.6);
  font-size: 10px;
  padding: 4px 6px;
  border-radius: 2px;
  font-family: var(--font-ui);
  cursor: pointer;
  min-width: 0;
}

.collapse-btn {
  position: absolute;
  bottom: 16px;
  right: 10px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.35);
  cursor: pointer;
  padding: 5px;
  display: flex;
  align-items: center;
  border-radius: 2px;
  transition: color 0.15s, background 0.15s;
}

.collapsed .collapse-btn {
  right: 50%;
  transform: translateX(50%);
}

.collapse-btn:hover {
  color: rgba(255, 255, 255, 0.75);
  background: rgba(255, 255, 255, 0.1);
}
</style>
