<template>
  <div class="message-actions">
    <button class="action-btn copy-btn" @click="copyContent">
      {{ copied === 'ok' ? '✓ Tersalin!' : copied === 'fail' ? '✗ Gagal' : '📋 Salin' }}
    </button>
    <button v-if="hasWarning" class="action-btn dismiss-btn" @click="$emit('dismiss-warning')">
      ✕
    </button>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  content: { type: String, required: true },
  hasWarning: { type: Boolean, default: false }
})

defineEmits(['dismiss-warning'])

const copied = ref(null) // null | 'ok' | 'fail'

async function copyContent() {
  try {
    await navigator.clipboard.writeText(props.content)
    copied.value = 'ok'
  } catch {
    copied.value = 'fail'
  }
  setTimeout(() => { copied.value = null }, 2000)
}
</script>

<style scoped>
.message-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  opacity: 0;
  transition: opacity 0.15s;
  margin-top: 8px;
  justify-content: flex-end;
}

.action-btn {
  font-family: var(--font-ui);
  font-size: 10px;
  padding: 3px 8px;
  border: 1px solid var(--color-border);
  background: white;
  color: var(--color-text-muted);
  border-radius: 2px;
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s;
}

.copy-btn:hover {
  color: var(--color-gold);
  border-color: var(--color-gold);
}

.dismiss-btn {
  font-size: 9px;
}

.dismiss-btn:hover {
  color: #e74c3c;
  border-color: #e74c3c;
}
</style>
