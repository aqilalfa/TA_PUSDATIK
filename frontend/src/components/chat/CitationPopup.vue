<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="citation-popup"
      :style="positionStyle"
      @mouseenter="cancelClose"
      @mouseleave="scheduleClose"
    >
      <!-- Loading state -->
      <div v-if="loading" class="popup-loading">
        <span class="popup-spinner"></span>
        Memuat...
      </div>

      <!-- Error state -->
      <div v-else-if="error" class="popup-error">
        ⚠ Gagal memuat pratinjau
      </div>

      <!-- Content state -->
      <template v-else-if="chunk">
        <div class="popup-meta">
          <span class="popup-doc" :title="chunk.document_title">{{ chunk.document_title }}</span>
          <span v-if="chunk.bab" class="popup-badge bab">{{ shortBab(chunk.bab) }}</span>
          <span v-if="chunk.pasal" class="popup-badge pasal">{{ chunk.pasal }}</span>
        </div>
        <div class="popup-text">{{ truncatedText }}</div>
        <div class="popup-actions">
          <button class="popup-btn pdf" @click="openPdf">📄 Buka PDF ↗</button>
          <button class="popup-btn ctx" @click="openContext">🔍 Lihat Konteks →</button>
        </div>
      </template>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed } from 'vue'
import { getChunkByIndex, getDocumentFileUrl } from '@/services/documentService'

const props = defineProps({
  /** Source object dari message.sources yang cocok dengan citation ID */
  source: { type: Object, default: null },
  /** Bounding rect dari citation button (dari getBoundingClientRect) */
  anchorRect: { type: Object, default: null },
})

const emit = defineEmits(['close'])

const visible = ref(false)
const loading = ref(false)
const error = ref(false)
const chunk = ref(null)
let closeTimer = null

const positionStyle = computed(() => {
  if (!props.anchorRect) return {}
  const rect = props.anchorRect
  const top = rect.bottom + window.scrollY + 6
  // Pastikan popup tidak keluar batas kanan layar
  const left = Math.min(rect.left + window.scrollX, window.innerWidth - 280)
  return { top: `${top}px`, left: `${left}px` }
})

const truncatedText = computed(() => {
  const text = chunk.value?.text || ''
  return text.length > 280 ? text.slice(0, 280) + '…' : text
})

function shortBab(bab) {
  if (!bab) return ''
  const m = String(bab).match(/BAB\s+[IVXLCDM]+/i)
  return m ? m[0] : String(bab).slice(0, 12)
}

async function show() {
  if (!props.source?.doc_id) return
  visible.value = true
  loading.value = true
  error.value = false
  chunk.value = null

  try {
    const idx = props.source.chunk_index
    if (idx !== null && idx !== undefined) {
      chunk.value = await getChunkByIndex(props.source.doc_id, idx)
    } else {
      // Fallback ke data snippet yang sudah ada di source
      chunk.value = {
        document_title: props.source.citation_title || props.source.document,
        text: props.source.snippet || '(Tidak ada pratinjau)',
        bab: null,
        pasal: props.source.pasal || null,
        doc_id: props.source.doc_id,
      }
    }
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function hide() {
  visible.value = false
  chunk.value = null
  emit('close')
}

function scheduleClose() {
  closeTimer = setTimeout(hide, 300)
}

function cancelClose() {
  clearTimeout(closeTimer)
}

function openPdf() {
  if (props.source?.doc_id) {
    window.open(getDocumentFileUrl(props.source.doc_id), '_blank', 'noopener,noreferrer')
  }
}

function openContext() {
  if (props.source?.doc_id) {
    const idx = props.source.chunk_index ?? ''
    const url = idx !== ''
      ? `/documents/${props.source.doc_id}?highlight=${idx}`
      : `/documents/${props.source.doc_id}`
    window.open(url, '_blank', 'noopener,noreferrer')
  }
}

defineExpose({ show, hide, scheduleClose, cancelClose })
</script>

<style scoped>
.citation-popup {
  position: absolute;
  z-index: 9999;
  width: 260px;
  background: white;
  border: 1px solid var(--color-border);
  border-left: 3px solid var(--color-gold);
  border-radius: 0 4px 4px 4px;
  box-shadow: 0 4px 20px rgba(26, 58, 107, 0.14);
  padding: 10px 12px;
  font-family: var(--font-ui);
  animation: popupIn 0.15s ease;
}

@keyframes popupIn {
  from { opacity: 0; transform: translateY(-4px); }
  to   { opacity: 1; transform: translateY(0); }
}

.popup-loading {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--color-text-muted);
}

.popup-spinner {
  display: inline-block;
  width: 10px;
  height: 10px;
  border: 1.5px solid rgba(139, 115, 85, 0.3);
  border-top-color: #8b7355;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  flex-shrink: 0;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.popup-error {
  font-size: 11px;
  color: #c0392b;
}

.popup-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  margin-bottom: 7px;
}

.popup-doc {
  font-size: 9px;
  font-weight: 600;
  color: var(--color-navy);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 155px;
}

.popup-badge {
  font-size: 8px;
  padding: 1px 5px;
  border-radius: 2px;
  font-weight: 600;
  white-space: nowrap;
}

.popup-badge.bab {
  background: #fdf8ee;
  color: #8b7355;
  border: 1px solid #e0c97a;
}

.popup-badge.pasal {
  background: var(--color-status-info-bg);
  color: var(--color-status-info-text);
  border: 1px solid var(--color-status-info-border);
}

.popup-text {
  font-size: 10px;
  font-family: var(--font-body);
  line-height: 1.6;
  color: var(--color-text);
  font-style: italic;
  margin-bottom: 8px;
  max-height: 100px;
  overflow-y: auto;
}

.popup-actions {
  display: flex;
  gap: 5px;
}

.popup-btn {
  flex: 1;
  padding: 3px 6px;
  font-size: 9px;
  font-family: var(--font-ui);
  font-weight: 600;
  border-radius: 2px;
  cursor: pointer;
  border: 1px solid var(--color-border);
  background: white;
  color: var(--color-text-muted);
  transition: all 0.15s;
}

.popup-btn.pdf:hover {
  border-color: var(--color-navy);
  color: var(--color-navy);
  background: #eef2f9;
}

.popup-btn.ctx:hover {
  border-color: var(--color-gold);
  color: #8b7355;
  background: #fdf8ee;
}
</style>
