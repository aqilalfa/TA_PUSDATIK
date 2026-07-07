<template>
  <div
    class="source-card-wrapper"
    :class="{ clickable: source.doc_id, expanded }"
  >
    <button
      type="button"
      class="source-card"
      :aria-expanded="expanded"
      :aria-controls="`source-expand-${source.id}`"
      @click="toggleExpanded"
    >
      <span class="source-header">
        <span class="source-num">
          📎 SUMBER [{{ source.id }}]<span v-if="source.score > 0" class="source-score"> · {{ Number(source.score).toFixed(2) }}</span>
        </span>
        <span class="source-toggle" aria-hidden="true">{{ expanded ? 'Tutup' : 'Detail' }}</span>
      </span>
      <span class="source-title">{{ source.citation_title || source.document }}</span>
      <span v-if="source.section" class="source-meta">{{ source.section }}</span>
    </button>
    <div :id="`source-expand-${source.id}`" class="source-expand">
      <p v-if="source.snippet" class="expand-snippet">{{ source.snippet }}</p>
      <p v-if="source.hierarchy_path" class="expand-path">{{ source.hierarchy_path }}</p>
      <div v-if="source.doc_id" class="expand-actions">
        <button class="action-btn pdf" @click.stop="openPdf">
          📄 Buka PDF ↗
        </button>
        <button class="action-btn ctx" @click.stop="openContext">
          🔍 Lihat Konteks →
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { openDocumentFile } from '@/services/documentService'

const props = defineProps({
  source: { type: Object, required: true }
})

const expanded = ref(false)

function toggleExpanded() {
  expanded.value = !expanded.value
}

async function openPdf() {
  if (props.source.doc_id) {
    await openDocumentFile(props.source.doc_id)
  }
}

function openContext() {
  if (props.source.doc_id) {
    const chunkIdx = props.source.chunk_index ?? ''
    const url = chunkIdx !== ''
      ? `/documents/${props.source.doc_id}?highlight=${chunkIdx}`
      : `/documents/${props.source.doc_id}`
    window.open(url, '_blank', 'noopener,noreferrer')
  }
}
</script>

<style scoped>
.source-card-wrapper {
  flex: 1 1 260px;
  min-width: 240px;
  max-width: 100%;
  position: relative;
}

.source-card-wrapper.clickable {
  cursor: default;
}

.source-card {
  width: 100%;
  min-height: 88px;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 5px;
  text-align: left;
  border: 1px solid var(--color-border);
  padding: 10px 12px;
  border-radius: 4px 4px 0 0;
  background: var(--color-cream, #faf9f7);
  box-shadow: inset 0 0 0 1px rgba(201, 168, 76, 0.08);
  transition: border-color 0.15s, box-shadow 0.15s;
  cursor: pointer;
}

.source-card-wrapper:hover .source-card,
.source-card:focus-visible,
.source-card-wrapper.expanded .source-card {
  border-color: var(--color-navy);
  box-shadow: 0 2px 8px rgba(26, 58, 107, 0.08);
}

.source-expand {
  border: 1px solid var(--color-navy);
  border-top: none;
  background: var(--color-white, #ffffff);
  padding: 0 12px;
  border-radius: 0 0 3px 3px;
  max-height: 0;
  overflow: hidden;
  opacity: 0;
  transition: opacity 0.15s;
}

.source-card-wrapper:hover .source-expand,
.source-card-wrapper:focus-within .source-expand,
.source-card-wrapper.expanded .source-expand {
  max-height: 260px;
  opacity: 1;
  padding: 10px 12px;
}

.source-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-width: 0;
}

.source-num {
  min-width: 0;
  font-size: 9px;
  color: var(--color-gold-ink, #9d7928);
  font-weight: 700;
  letter-spacing: 0.4px;
  font-family: var(--font-ui);
  overflow-wrap: anywhere;
}

.source-score {
  color: var(--color-text-panel-muted, #5c6f8a);
  font-weight: 500;
}

.source-toggle {
  flex: 0 0 auto;
  font-family: var(--font-ui);
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.2px;
  color: var(--color-text-panel-muted, #5c6f8a);
}

.source-title {
  display: -webkit-box;
  color: var(--color-navy);
  font-family: var(--font-ui);
  font-size: 11px;
  font-weight: 700;
  line-height: 1.35;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow-wrap: anywhere;
}

.source-meta {
  display: -webkit-box;
  color: var(--color-text-panel-muted, #5c6f8a);
  font-family: var(--font-ui);
  font-size: 9px;
  line-height: 1.45;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow-wrap: anywhere;
}

.expand-snippet {
  font-size: 9px;
  color: var(--color-text);
  font-family: var(--font-body);
  font-style: italic;
  line-height: 1.5;
  margin: 0 0 6px;
}

.expand-path {
  font-size: 8px;
  color: var(--color-text-muted);
  font-family: var(--font-ui);
  margin: 0 0 6px;
}

/* Dua tombol aksi menggantikan expand-link lama */
.expand-actions {
  display: flex;
  gap: 5px;
  margin-top: 2px;
}

.action-btn {
  flex: 1;
  padding: 4px 6px;
  font-size: 9px;
  font-family: var(--font-ui);
  font-weight: 600;
  border-radius: 2px;
  cursor: pointer;
  border: 1px solid var(--color-border);
  background: white;
  color: var(--color-text-muted);
  transition: all 0.15s;
  white-space: nowrap;
}

.action-btn.pdf:hover {
  border-color: var(--color-navy);
  color: var(--color-navy);
  background: #eef2f9;
}

.action-btn.ctx:hover {
  border-color: var(--color-gold);
  color: #8b7355;
  background: #fdf8ee;
}
</style>
