<template>
  <div class="message-wrapper" :class="message.role">

    <!-- User message -->
    <div v-if="message.role === 'user'" class="msg-user">
      <div v-if="!isEditing" class="msg-user-bubble-wrapper">
        <button v-if="canEditRetry" class="user-edit-btn" @click="$emit('edit-retry')" title="Perbaiki Pertanyaan">
          <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
        </button>
        <div class="msg-user-bubble">{{ message.content }}</div>
      </div>
      <div v-else class="msg-user-edit-box">
        <textarea
          v-focus
          :value="editContent"
          @input="$emit('update:editContent', $event.target.value)"
          class="inline-edit-textarea"
        ></textarea>
        <div class="inline-edit-actions">
          <button @click="$emit('cancel-edit')" class="btn-cancel">Batal</button>
          <button @click="$emit('submit-edit', editContent)" class="btn-submit">Kirim Ulang</button>
        </div>
      </div>
    </div>

    <!-- AI message -->
    <div v-else class="msg-ai">
      <div class="msg-ai-header">
        <div class="msg-ai-avatar">AH</div>
        <span v-if="message.loading" class="msg-ai-meta">
          <span class="retrieval-spinner"></span>
          {{ message.loadingText || 'Mencari dokumen relevan...' }}
        </span>
        <span v-else class="msg-ai-meta">
          Asisten Hukum SPBE
          <span v-if="message.sources && message.sources.length"> · {{ message.sources.length }} sumber</span>
        </span>
        <span v-if="message.timestamp" class="msg-ai-timestamp">{{ message.timestamp }}</span>
      </div>

      <div v-if="!message.loading" class="msg-ai-bubble-wrapper">
        <div class="msg-ai-bubble">
            <div
              class="msg-text"
              v-html="formattedContent"
              @click="handleCitationClick"
              @mouseleave="handleCitationMouseleave"
            ></div>
            <span v-if="message.streaming" class="streaming-cursor"></span>

            <div v-if="showSources" class="source-cards">
              <SourceCard
                v-for="source in message.sources"
                :key="`${source.id}-${source.document}-${source.section || 'none'}`"
                :source="source"
              />
            </div>

            <CitationPopup
              ref="popupRef"
              :source="popupSource"
              :anchor-rect="popupAnchorRect"
              @close="popupSource = null"
            />

          <div v-if="showValidationWarnings" class="validation-warnings">
            <div class="validation-title">⚠ Peringatan Validasi</div>
            <ul>
              <li v-for="(warning, i) in message.validation.warnings" :key="i">{{ warning }}</li>
            </ul>
          </div>
        </div>

        <MessageActions
          v-if="!message.loading && !message.streaming"
          :content="message.content || ''"
          :has-warning="showValidationWarnings"
          :can-regenerate="canRegenerate"
          @dismiss-warning="warningDismissed = true"
          @regenerate="$emit('regenerate')"
        />
      </div>
    </div>

  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import SourceCard from './SourceCard.vue'
import MessageActions from './MessageActions.vue'
import CitationPopup from './CitationPopup.vue'
import { formatMessageContent } from '@/utils/messageFormatter.js'

const props = defineProps({
  message: { type: Object, required: true },
  canRegenerate: { type: Boolean, default: false },
  canEditRetry: { type: Boolean, default: false },
  isEditing: { type: Boolean, default: false },
  editContent: { type: String, default: '' }
})

defineEmits(['regenerate', 'edit-retry', 'submit-edit', 'update:editContent', 'cancel-edit'])

const warningDismissed = ref(false)

// Citation popup state
const popupRef = ref(null)
const popupSource = ref(null)
const popupAnchorRect = ref(null)

const vFocus = {
  mounted(el) {
    el.focus()
  }
}

const formattedContent = computed(() => formatMessageContent(props.message.content))

const showSources = computed(() =>
  Array.isArray(props.message.sources) && props.message.sources.length > 0 && !props.message.streaming
)

const showValidationWarnings = computed(() => {
  if (warningDismissed.value) return false
  const w = props.message.validation?.warnings
  return Array.isArray(w) && w.length > 0 && !props.message.streaming
})

function handleCitationClick(event) {
  const btn = event.target.closest('button.citation')
  if (!btn) return

  const citationId = parseInt(btn.dataset.citationId, 10)
  const sources = props.message.sources || []
  const matched = sources.find(s => s.id === citationId)
  if (!matched?.doc_id) return

  popupSource.value = matched
  popupAnchorRect.value = btn.getBoundingClientRect()
  popupRef.value?.show()
}

function handleCitationMouseleave() {
  popupRef.value?.scheduleClose()
}
</script>

<style scoped>
.message-wrapper {
  max-width: 760px;
  margin: 0 auto;
  padding: 0 28px;
  margin-bottom: 20px;
  animation: fadeIn 0.2s ease;
}

/* User bubble */
.msg-user {
  display: flex;
  justify-content: flex-end;
}

.msg-user-bubble-wrapper {
  position: relative;
  display: flex;
  align-items: flex-end;
  gap: 6px;
  max-width: 65%;
}

.msg-user-bubble {
  background: var(--color-navy);
  color: white;
  padding: 10px 16px;
  border-radius: var(--radius-md);
  font-family: var(--font-ui);
  font-size: 13px;
  line-height: 1.55;
}

.user-edit-btn {
  background: white;
  border: 1px solid var(--color-border);
  border-radius: 50%;
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-muted);
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s, color 0.15s, border-color 0.15s;
  flex-shrink: 0;
  margin-bottom: 4px;
}

.msg-user-bubble-wrapper:hover .user-edit-btn {
  opacity: 1;
}

.user-edit-btn:hover {
  color: var(--color-gold);
  border-color: var(--color-gold);
}

.msg-user-edit-box {
  background: var(--color-white);
  border: 1px solid var(--color-navy);
  border-radius: var(--radius-md);
  padding: 12px;
  width: 100%;
  max-width: 65%;
  box-shadow: 0 4px 12px rgba(11, 74, 191, 0.08);
}

.inline-edit-textarea {
  width: 100%;
  min-height: 60px;
  border: none;
  outline: none;
  font-family: var(--font-ui);
  font-size: 13px;
  color: var(--color-text);
  resize: vertical;
  line-height: 1.55;
}

.inline-edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 10px;
}

.btn-cancel, .btn-submit {
  font-family: var(--font-ui);
  font-size: 11px;
  padding: 5px 12px;
  border-radius: 4px;
  cursor: pointer;
  border: none;
  transition: background 0.15s, color 0.15s;
  font-weight: 600;
}

.btn-cancel {
  background: var(--color-surface-page-muted);
  color: var(--color-text-muted);
}

.btn-cancel:hover {
  background: var(--color-border-blue-light);
}

.btn-submit {
  background: var(--color-navy);
  color: white;
}

.btn-submit:hover {
  background: var(--color-navy-hover);
}

/* AI message */
.msg-ai {
  display: flex;
  flex-direction: column;
}

.msg-ai-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.msg-ai-avatar {
  width: 24px;
  height: 24px;
  background: var(--color-gold);
  border-radius: 2px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 9px;
  font-weight: 700;
  color: var(--color-navy);
  flex-shrink: 0;
  font-family: var(--font-ui);
}

.msg-ai-meta {
  font-size: 11px;
  color: var(--color-text-muted);
  font-style: normal;
  font-family: var(--font-ui);
  display: flex;
  align-items: center;
  gap: 6px;
}

.msg-ai-timestamp {
  font-size: 10px;
  color: var(--color-text-light);
  font-family: var(--font-ui);
}

/* Bubble wrapper enables hover-reveal for MessageActions */
.msg-ai-bubble-wrapper {
  position: relative;
}

.msg-ai-bubble-wrapper:hover :deep(.message-actions) {
  opacity: 1;
}

.msg-ai-bubble {
  background: var(--color-white);
  border: 1px solid var(--color-border-blue);
  padding: 16px 18px;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-panel);
}

/* Message body text */
.msg-text {
  font-family: var(--font-ui);
  font-size: 13px;
  line-height: 1.7;
  color: var(--color-text-panel);
}

.msg-text :deep(h3) {
  margin: 14px 0 8px;
  color: var(--color-action-blue-dark);
  font-family: var(--font-ui);
  font-size: 14px;
  font-weight: 700;
  line-height: 1.35;
  letter-spacing: -0.1px;
}

.msg-text :deep(h3:first-child) { margin-top: 0; }

.msg-text :deep(p) { margin: 0 0 9px; }
.msg-text :deep(p:last-child) { margin-bottom: 0; }
.msg-text :deep(strong) { font-weight: 700; color: var(--color-action-blue-dark); }
.msg-text :deep(mark.answer-highlight) {
  background: var(--color-surface-soft-blue);
  color: var(--color-action-blue-dark);
  border-radius: var(--radius-sm);
  box-decoration-break: clone;
  -webkit-box-decoration-break: clone;
  padding: 1px 4px 2px;
  font-weight: 700;
}
.msg-text :deep(ul),
.msg-text :deep(ol) {
  margin: 9px 0 12px;
  padding-left: 0;
}

.msg-text :deep(ol) {
  list-style: none;
  counter-reset: legal-answer-step;
}

.msg-text :deep(ul) {
  list-style: none;
}

.msg-text :deep(li) {
  position: relative;
  margin-bottom: 7px;
  padding-left: 26px;
  color: var(--color-text-panel);
}

.msg-text :deep(ol > li) {
  counter-increment: legal-answer-step;
}

.msg-text :deep(ol > li::before) {
  content: counter(legal-answer-step);
  position: absolute;
  left: 0;
  top: 2px;
  width: 18px;
  height: 18px;
  display: inline-grid;
  place-items: center;
  border-radius: var(--radius-sm);
  background: var(--color-surface-soft-blue);
  color: var(--color-action-blue-dark);
  font-family: var(--font-ui);
  font-size: 10px;
  font-weight: 700;
  line-height: 1;
}

.msg-text :deep(ul > li::before) {
  content: '';
  position: absolute;
  left: 6px;
  top: 10px;
  width: 6px;
  height: 6px;
  border-radius: var(--radius-pill);
  background: var(--color-action-blue);
}

.msg-text :deep(code) { font-size: 12px; background: var(--color-cream-dark); padding: 1px 5px; border-radius: var(--radius-xs); }
.msg-text :deep(pre) { background: var(--color-cream-dark); padding: 12px; border-radius: var(--radius-sm); overflow-x: auto; margin: 8px 0; }
.msg-text :deep(button.citation) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  background: #eef2f9;
  border: 1px solid #b8cce4;
  color: var(--color-navy);
  font-size: 8px;
  font-weight: 600;
  border-radius: 2px;
  font-family: var(--font-ui);
  vertical-align: middle;
  margin: 0 1px;
  cursor: pointer;
  padding: 0;
  transition: background 0.15s, border-color 0.15s;
}

.msg-text :deep(button.citation:hover) {
  background: var(--color-surface-soft-blue);
  border-color: var(--color-navy);
}

/* Streaming cursor */
.streaming-cursor {
  display: inline-block;
  width: 2px;
  height: 14px;
  background: var(--color-navy);
  margin-left: 2px;
  vertical-align: middle;
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}



/* Retrieval spinner */
.retrieval-spinner {
  display: inline-block;
  width: 8px;
  height: 8px;
  border: 1.5px solid rgba(139, 115, 85, 0.3);
  border-top-color: #8b7355;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  flex-shrink: 0;
}

/* Source cards */
.source-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 10px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--color-border-light);
}

/* Validation warnings */
.validation-warnings {
  margin-top: 10px;
  padding: 8px 12px;
  background: #fdf8ee;
  border: 1px solid var(--color-status-warn-border);
  border-radius: 2px;
}

.validation-title {
  font-size: 10px;
  font-weight: 600;
  color: var(--color-status-warn-text);
  margin-bottom: 4px;
  font-family: var(--font-ui);
}

.validation-warnings ul {
  margin: 0;
  padding-left: 16px;
}

.validation-warnings li {
  font-size: 11px;
  color: var(--color-status-warn-text);
  font-family: var(--font-ui);
}

@media (max-width: 640px) {
  .message-wrapper {
    padding: 0 14px;
    margin-bottom: 16px;
  }

  .msg-user-bubble-wrapper,
  .msg-user-edit-box {
    max-width: 88%;
  }

  .msg-user-bubble {
    padding: 10px 13px;
    overflow-wrap: anywhere;
  }

  .user-edit-btn {
    opacity: 1;
    width: 32px;
    height: 32px;
  }

  .msg-ai-header {
    align-items: flex-start;
    gap: 7px;
  }

  .msg-ai-meta {
    min-width: 0;
    flex-wrap: wrap;
    line-height: 1.35;
  }

  .msg-ai-bubble {
    padding: 14px 13px;
    border-radius: var(--radius-md);
  }

  .msg-text {
    font-size: 13px;
    line-height: 1.65;
    overflow-wrap: anywhere;
  }

  .msg-text :deep(pre) {
    margin-inline: -2px;
    padding: 10px;
  }

  .source-cards {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 420px) {
  .message-wrapper {
    padding: 0 10px;
  }

  .msg-user-bubble-wrapper,
  .msg-user-edit-box {
    max-width: 92%;
  }

  .inline-edit-actions {
    flex-wrap: wrap;
  }

  .btn-cancel,
  .btn-submit {
    min-height: 36px;
  }
}
</style>
