<template>
  <div class="message-wrapper" :class="message.role">

    <!-- User message -->
    <div v-if="message.role === 'user'" class="msg-user">
      <div class="msg-user-bubble">{{ message.content }}</div>
    </div>

    <!-- AI message -->
    <div v-else class="msg-ai">
      <div class="msg-ai-header">
        <div class="msg-ai-avatar">AI</div>
        <span v-if="message.loading" class="msg-ai-meta">
          <span class="retrieval-spinner"></span>
          {{ message.loadingText || 'Mencari dokumen relevan...' }}
        </span>
        <span v-else class="msg-ai-meta">
          Berdasarkan dokumen resmi
          <span v-if="message.sources && message.sources.length"> · {{ message.sources.length }} sumber</span>
        </span>
        <span v-if="message.timestamp" class="msg-ai-timestamp">{{ message.timestamp }}</span>
        <span v-if="message.timing && !message.streaming" class="msg-ai-timing">
          {{ Math.round(message.timing.total_ms) }}ms
        </span>
      </div>

      <div class="msg-ai-bubble-wrapper">
        <div class="msg-ai-bubble">
          <div v-if="message.loading" class="loading-dots">
            <span></span><span></span><span></span>
          </div>
          <template v-else>
            <div class="msg-text" v-html="formattedContent"></div>
            <span v-if="message.streaming" class="streaming-cursor"></span>

            <div v-if="showSources" class="source-cards">
              <SourceCard
                v-for="source in message.sources"
                :key="`${source.id}-${source.document}-${source.section || 'none'}`"
                :source="source"
              />
            </div>

            <div v-if="showValidationWarnings" class="validation-warnings">
              <div class="validation-title">⚠ Peringatan Validasi</div>
              <ul>
                <li v-for="(warning, i) in message.validation.warnings" :key="i">{{ warning }}</li>
              </ul>
            </div>
          </template>
        </div>

        <MessageActions
          v-if="!message.loading && !message.streaming"
          :content="message.content || ''"
          :has-warning="showValidationWarnings"
          @dismiss-warning="warningDismissed = true"
        />
      </div>
    </div>

  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import SourceCard from './SourceCard.vue'
import MessageActions from './MessageActions.vue'
import { formatMessageContent } from '@/utils/messageFormatter.js'

const props = defineProps({
  message: { type: Object, required: true }
})

const warningDismissed = ref(false)

const formattedContent = computed(() => formatMessageContent(props.message.content))

const showSources = computed(() =>
  Array.isArray(props.message.sources) && props.message.sources.length > 0 && !props.message.streaming
)

const showValidationWarnings = computed(() => {
  if (warningDismissed.value) return false
  const w = props.message.validation?.warnings
  return Array.isArray(w) && w.length > 0 && !props.message.streaming
})
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

.msg-user-bubble {
  background: var(--color-navy);
  color: white;
  padding: 10px 16px;
  border-radius: 16px 16px 2px 16px;
  max-width: 65%;
  font-family: var(--font-body);
  font-size: 13px;
  line-height: 1.55;
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
  font-size: 10px;
  color: #8b7355;
  font-style: italic;
  font-family: var(--font-display);
  display: flex;
  align-items: center;
  gap: 6px;
}

.msg-ai-timestamp {
  font-size: 9px;
  color: var(--color-text-light);
  font-family: var(--font-ui);
}

.msg-ai-timing {
  font-size: 9px;
  color: var(--color-text-light);
  font-family: var(--font-ui);
  font-style: normal;
  margin-left: auto;
}

/* Bubble wrapper enables hover-reveal for MessageActions */
.msg-ai-bubble-wrapper {
  position: relative;
}

.msg-ai-bubble-wrapper:hover :deep(.message-actions) {
  opacity: 1;
}

.msg-ai-bubble {
  background: white;
  border: 1px solid var(--color-border);
  border-left: 3px solid var(--color-gold);
  padding: 14px 16px;
  border-radius: 0 8px 8px 8px;
}

/* Message body text */
.msg-text {
  font-family: var(--font-body);
  font-size: 13px;
  line-height: 1.7;
  color: var(--color-text);
}

.msg-text :deep(p) { margin: 0 0 8px; }
.msg-text :deep(p:last-child) { margin-bottom: 0; }
.msg-text :deep(strong) { font-weight: 600; color: var(--color-navy); }
.msg-text :deep(ul), .msg-text :deep(ol) { padding-left: 20px; margin: 8px 0; }
.msg-text :deep(li) { margin-bottom: 4px; }
.msg-text :deep(code) { font-size: 12px; background: #f0ece4; padding: 1px 5px; border-radius: 2px; }
.msg-text :deep(pre) { background: #f0ece4; padding: 12px; border-radius: 3px; overflow-x: auto; margin: 8px 0; }
.msg-text :deep(.citation) {
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
  cursor: default;
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

/* Loading dots */
.loading-dots {
  display: flex;
  gap: 4px;
  align-items: center;
  padding: 4px 0;
}

.loading-dots span {
  width: 6px;
  height: 6px;
  background: var(--color-gold);
  border-radius: 50%;
  animation: dotBounce 1.2s ease-in-out infinite;
}

.loading-dots span:nth-child(2) { animation-delay: 0.2s; }
.loading-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes dotBounce {
  0%, 80%, 100% { transform: scale(0.7); opacity: 0.5; }
  40% { transform: scale(1); opacity: 1; }
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
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
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
</style>
