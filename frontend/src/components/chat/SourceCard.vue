<template>
  <div
    class="source-card-wrapper"
    :class="{ clickable: source.doc_id }"
  >
    <div class="source-card">
      <div class="source-num">
        📎 SUMBER [{{ source.id }}]<span v-if="source.score > 0" class="source-score"> · {{ Number(source.score).toFixed(2) }}</span>
      </div>
      <div class="source-title">{{ source.citation_title || source.document }}</div>
      <div v-if="source.section" class="source-meta">{{ source.section }}</div>
    </div>
    <div class="source-expand">
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
import { getDocumentFileUrl } from '@/services/documentService'

const props = defineProps({
  source: { type: Object, required: true }
})

function openPdf() {
  if (props.source.doc_id) {
    window.open(getDocumentFileUrl(props.source.doc_id), '_blank', 'noopener,noreferrer')
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
  min-width: 150px;
  max-width: 240px;
  position: relative;
}

.source-card-wrapper.clickable {
  cursor: default;
}

.source-card {
  border: 1px solid var(--color-border);
  border-left: 3px solid var(--color-gold);
  padding: 8px 12px;
  border-radius: 0 3px 0 0;
  background: var(--color-cream, #faf9f7);
  transition: border-left-color 0.15s, box-shadow 0.15s;
}

.source-card-wrapper:hover .source-card {
  border-left-color: var(--color-navy);
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
  transition: max-height 0.2s ease, opacity 0.15s, padding 0.15s;
}

.source-card-wrapper:hover .source-expand {
  max-height: 200px;
  opacity: 1;
  padding: 8px 12px;
}

.source-num {
  font-size: 9px;
  color: var(--color-gold);
  font-weight: 600;
  letter-spacing: 0.5px;
  margin-bottom: 3px;
  font-family: var(--font-ui);
}

.source-score {
  color: var(--color-text-light);
  font-weight: 400;
}

.source-title {
  font-size: 10px;
  color: var(--color-navy);
  font-weight: 600;
  margin-bottom: 2px;
  font-family: var(--font-ui);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.source-meta {
  font-size: 9px;
  color: var(--color-text-muted);
  font-family: var(--font-ui);
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
