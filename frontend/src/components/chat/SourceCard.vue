<template>
  <div
    class="source-card-wrapper"
    :class="{ clickable: source.doc_id }"
    @click="openDocument"
  >
    <div class="source-card">
      <div class="source-num">
        📎 SUMBER [{{ source.id }}]<span v-if="source.score > 0" class="source-score"> · {{ source.score.toFixed(2) }}</span>
      </div>
      <div class="source-title">{{ source.citation_title || source.document }}</div>
      <div v-if="source.section" class="source-meta">{{ source.section }}</div>
    </div>
    <div class="source-expand">
      <p v-if="source.snippet" class="expand-snippet">{{ source.snippet }}</p>
      <p v-if="source.hierarchy_path" class="expand-path">{{ source.hierarchy_path }}</p>
      <span v-if="source.doc_id" class="expand-link">🔗 Buka dokumen ↗</span>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  source: { type: Object, required: true }
})

function openDocument() {
  if (props.source.doc_id) {
    window.open(`/documents/${props.source.doc_id}`, '_blank')
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
  cursor: pointer;
}

.source-card {
  border: 1px solid var(--color-border);
  border-left: 3px solid var(--color-gold);
  padding: 8px 12px;
  border-radius: 0 3px 0 0;
  background: #faf9f7;
  transition: border-left-color 0.15s, box-shadow 0.15s;
}

.source-card-wrapper:hover .source-card {
  border-left-color: var(--color-navy);
  box-shadow: 0 2px 8px rgba(26, 58, 107, 0.08);
}

.source-expand {
  border: 1px solid var(--color-navy);
  border-top: none;
  background: white;
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

.expand-link {
  font-size: 9px;
  color: var(--color-navy);
  font-weight: 600;
  font-family: var(--font-ui);
  display: block;
}
</style>
