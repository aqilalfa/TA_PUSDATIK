<template>
  <form class="chat-input-form" @submit.prevent="emitSend">
    <div class="input-box" :class="{ focused: isFocused }">
      <textarea
        ref="inputField"
        :value="modelValue"
        placeholder="Ketik pertanyaan hukum SPBE Anda..."
        rows="1"
        :disabled="isLoading"
        @keydown.enter.exact.prevent="emitSend"
        @input="handleInput"
        @focus="isFocused = true"
        @blur="isFocused = false"
      ></textarea>

      <div class="input-actions">
        <button
          v-if="isLoading"
          type="button"
          class="stop-btn"
          @click="$emit('stop')"
        >
          Stop
        </button>

        <button
          v-else
          type="submit"
          :disabled="!modelValue.trim()"
          class="send-btn"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
            <path d="M2 21l21-9L2 3v7l15 2-15 2v7z"/>
          </svg>
        </button>
      </div>
    </div>

    <div class="input-hint">
      <span>Enter kirim · Shift+Enter baris baru</span>
    </div>
  </form>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  isLoading: { type: Boolean, default: false }
})

const emit = defineEmits(['update:modelValue', 'send', 'stop'])

const inputField = ref(null)
const isFocused = ref(false)

function emitSend() { emit('send') }

function handleInput(event) {
  emit('update:modelValue', event.target.value)
  autoResize(event.target)
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
  padding: 12px 28px 16px;
  background: var(--color-white);
  border-top: 1px solid var(--color-border-blue-light);
}

.input-box {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  border: 1px solid var(--color-border-control);
  border-radius: var(--radius-md);
  background: var(--color-input-bg);
  padding: 10px 12px;
  transition: border-color 0.2s, background 0.2s;
}

.input-box.focused {
  border-color: var(--color-action-blue);
  background: var(--color-white);
}

textarea {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  font-family: var(--font-ui);
  font-size: 13px;
  color: var(--color-text);
  resize: none;
  min-height: 20px;
  line-height: 1.55;
}

textarea::placeholder {
  color: var(--color-text-placeholder);
  font-style: normal;
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

/* Send button */
.send-btn {
  width: 32px;
  height: 32px;
  background: var(--color-navy);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  transition: background 0.15s;
  flex-shrink: 0;
}

.stop-btn {
  min-width: 52px;
  height: 32px;
  background: var(--color-danger-strong);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  color: #ffffff;
  font-family: var(--font-ui);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  transition: background 0.15s;
}

.stop-btn:hover {
  background: var(--color-danger-hover);
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
  font-size: 10px;
  color: var(--color-text-muted);
  font-family: var(--font-ui);
  letter-spacing: 0.2px;
}

@media (max-width: 640px) {
  .chat-input-form {
    padding: 10px 12px calc(12px + env(safe-area-inset-bottom, 0px));
  }

  .input-box {
    gap: 8px;
    padding: 8px 9px 8px 11px;
  }

  textarea {
    font-size: 16px;
    line-height: 1.45;
  }

  .send-btn,
  .stop-btn {
    min-height: 40px;
  }

  .send-btn {
    width: 40px;
    height: 40px;
  }

  .stop-btn {
    min-width: 58px;
  }

  .input-hint {
    display: none;
  }
}

@media (max-width: 420px) {
  .chat-input-form {
    padding-inline: 10px;
  }

  .input-box {
    border-radius: var(--radius-lg);
  }
}
</style>
