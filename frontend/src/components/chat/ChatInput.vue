<template>
  <form class="chat-input-form" @submit.prevent="emitSend">
    <div class="input-box" :class="{ focused: isFocused }">
      <textarea
        ref="inputField"
        :value="modelValue"
        placeholder="Tanyakan sesuatu tentang regulasi SPBE, audit BSSN, atau kebijakan terkait..."
        rows="1"
        :disabled="isLoading"
        @keydown.enter.exact.prevent="emitSend"
        @input="handleInput"
        @focus="isFocused = true"
        @blur="isFocused = false"
      ></textarea>

      <div class="input-actions">
        <label class="rag-toggle" :title="useRag ? 'RAG aktif' : 'RAG nonaktif'">
          <div class="toggle-track" :class="{ on: useRag }">
            <div class="toggle-thumb"></div>
          </div>
          <span class="toggle-label">RAG</span>
          <input type="checkbox" :checked="useRag" @change="onRagToggle" hidden />
        </label>

        <button
          type="submit"
          :disabled="!modelValue.trim() || isLoading"
          class="send-btn"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
            <path d="M2 21l21-9L2 3v7l15 2-15 2v7z"/>
          </svg>
        </button>
      </div>
    </div>

    <div class="input-hint">
      <span>Enter untuk kirim · Shift+Enter untuk baris baru</span>
    </div>
  </form>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  isLoading: { type: Boolean, default: false },
  useRag: { type: Boolean, default: true }
})

const emit = defineEmits(['update:modelValue', 'update:useRag', 'send'])

const inputField = ref(null)
const isFocused = ref(false)

function emitSend() { emit('send') }

function handleInput(event) {
  emit('update:modelValue', event.target.value)
  autoResize(event.target)
}

function onRagToggle(event) {
  emit('update:useRag', event.target.checked)
}

function autoResize(textarea) {
  textarea.style.height = 'auto'
  textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`
}

function focusInput() { inputField.value?.focus() }
function resetInputHeight() {
  if (inputField.value) inputField.value.style.height = 'auto'
}

watch(() => props.modelValue, (value) => {
  if (!value && inputField.value) inputField.value.style.height = 'auto'
})

defineExpose({ focusInput, resetInputHeight })
</script>

<style scoped>
.chat-input-form {
  padding: 14px 28px 18px;
  background: white;
  border-top: 1px solid var(--color-border);
}

.input-box {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  border: 1px solid var(--color-border);
  border-radius: 2px;
  background: #faf9f7;
  padding: 10px 12px;
  transition: border-color 0.2s, background 0.2s;
}

.input-box.focused {
  border-color: var(--color-navy);
  background: white;
}

textarea {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  font-family: var(--font-body);
  font-size: 13px;
  color: var(--color-text);
  resize: none;
  min-height: 20px;
  line-height: 1.55;
}

textarea::placeholder {
  color: var(--color-text-light);
  font-style: italic;
}

textarea:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.input-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

/* RAG toggle */
.rag-toggle {
  display: flex;
  align-items: center;
  gap: 5px;
  cursor: pointer;
}

.toggle-track {
  width: 28px;
  height: 14px;
  background: rgba(0,0,0,0.15);
  border-radius: 7px;
  position: relative;
  transition: background 0.2s;
}

.toggle-track.on {
  background: var(--color-navy);
}

.toggle-thumb {
  width: 10px;
  height: 10px;
  background: white;
  border-radius: 50%;
  position: absolute;
  top: 2px;
  left: 2px;
  transition: left 0.2s;
}

.toggle-track.on .toggle-thumb {
  left: 16px;
}

.toggle-label {
  font-size: 10px;
  color: var(--color-text-muted);
  font-family: var(--font-ui);
  letter-spacing: 0.3px;
}

/* Send button */
.send-btn {
  width: 32px;
  height: 32px;
  background: var(--color-navy);
  border: none;
  border-radius: 2px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  transition: background 0.15s;
  flex-shrink: 0;
}

.send-btn:hover:not(:disabled) {
  background: var(--color-navy-hover);
}

.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.input-hint {
  margin-top: 6px;
  font-size: 9px;
  color: var(--color-text-light);
  font-family: var(--font-ui);
  letter-spacing: 0.3px;
}
</style>
