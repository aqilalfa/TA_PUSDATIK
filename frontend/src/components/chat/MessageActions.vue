<template>
  <div class="message-actions">
    <button class="action-btn copy-btn" type="button" @click="copyContent">
      {{ copied === 'ok' ? '✓ Tersalin!' : copied === 'fail' ? '✗ Gagal' : 'Salin' }}
    </button>
    <button v-if="canRegenerate" class="action-btn" type="button" @click="$emit('regenerate')">
      <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 2v6h-6"/><path d="M3 12a9 9 0 1 0 2.1-5.8L2 9"/></svg>Muat Ulang
    </button>

    <button v-if="hasWarning" class="action-btn dismiss-btn" type="button" aria-label="Sembunyikan peringatan validasi" @click="$emit('dismiss-warning')">
      ✕
    </button>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  content: { type: String, required: true },
  hasWarning: { type: Boolean, default: false },
  canRegenerate: { type: Boolean, default: false }
})

defineEmits(['dismiss-warning', 'regenerate'])

const copied = ref(null) // null | 'ok' | 'fail'

async function copyContent() {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(props.content)
    } else {
      const textarea = document.createElement('textarea')
      textarea.value = props.content
      textarea.setAttribute('readonly', '')
      textarea.style.position = 'fixed'
      textarea.style.opacity = '0'
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
    }
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
  opacity: 0.78;
  transition: opacity 0.15s;
  margin-top: 10px;
  justify-content: flex-end;
}

.action-btn {
  font-family: var(--font-ui);
  font-size: 10px;
  padding: 5px 9px;
  border: 1px solid var(--color-border-blue-light);
  background: var(--color-white);
  color: var(--color-text-muted);
  border-radius: 4px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  transition: color 0.15s, border-color 0.15s, background 0.15s, box-shadow 0.15s;
}

.action-btn:hover,
.action-btn:focus-visible {
  background: var(--color-surface-soft-blue);
  border-color: var(--color-border-blue);
  outline: none;
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
