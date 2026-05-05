# Chat Interactivity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add copy-to-clipboard, message timestamps, dismissible validation warnings, and a scroll-to-top button to the SPBE chat UI.

**Architecture:** Two new focused components (`MessageActions.vue`, `ScrollToTop.vue`) are added; `MessageBubble.vue` gains a `timestamp` prop and dismissal state; `ChatView.vue` gains a scroll listener and wires everything together. All new logic is unit-tested with Vitest + @vue/test-utils before implementation (TDD).

**Tech Stack:** Vue 3 Composition API (`<script setup>`), Vitest, @vue/test-utils, happy-dom, vanilla CSS with existing design tokens.

**Spec:** `docs/superpowers/specs/2026-04-23-chat-interactivity-design.md`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `frontend/src/components/chat/MessageActions.vue` | **Create** | Copy button + dismiss warning toolbar |
| `frontend/src/components/chat/ScrollToTop.vue` | **Create** | Fixed floating scroll-to-top button |
| `frontend/src/components/chat/__tests__/MessageActions.spec.js` | **Create** | Unit tests for MessageActions |
| `frontend/src/components/chat/__tests__/ScrollToTop.spec.js` | **Create** | Unit tests for ScrollToTop |
| `frontend/src/components/chat/__tests__/MessageBubble.spec.js` | **Create** | Unit tests for timestamp + warning dismissal |
| `frontend/src/components/chat/MessageBubble.vue` | **Modify** | Add timestamp prop, warningDismissed state, wrapper div, mount MessageActions |
| `frontend/src/views/ChatView.vue` | **Modify** | Scroll listener, ScrollToTop mount, timestamps on messages |

---

## Task 1: MessageActions.vue (TDD)

**Files:**
- Create: `frontend/src/components/chat/__tests__/MessageActions.spec.js`
- Create: `frontend/src/components/chat/MessageActions.vue`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/chat/__tests__/MessageActions.spec.js`:

```js
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import MessageActions from '../MessageActions.vue'

describe('MessageActions', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
      configurable: true,
      writable: true
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('copy button calls clipboard API with content', async () => {
    const wrapper = mount(MessageActions, {
      props: { content: 'Hello world', hasWarning: false }
    })
    await wrapper.find('.copy-btn').trigger('click')
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('Hello world')
  })

  it('shows Tersalin after successful copy and resets after 2s', async () => {
    const wrapper = mount(MessageActions, {
      props: { content: 'test', hasWarning: false }
    })
    await wrapper.find('.copy-btn').trigger('click')
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.copy-btn').text()).toContain('Tersalin')
    vi.advanceTimersByTime(2000)
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.copy-btn').text()).toContain('Salin')
  })

  it('shows Gagal if clipboard throws and resets after 2s', async () => {
    navigator.clipboard.writeText = vi.fn().mockRejectedValue(new Error('denied'))
    const wrapper = mount(MessageActions, {
      props: { content: 'test', hasWarning: false }
    })
    await wrapper.find('.copy-btn').trigger('click')
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.copy-btn').text()).toContain('Gagal')
    vi.advanceTimersByTime(2000)
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.copy-btn').text()).toContain('Salin')
  })

  it('emits dismiss-warning when dismiss button clicked', async () => {
    const wrapper = mount(MessageActions, {
      props: { content: 'test', hasWarning: true }
    })
    await wrapper.find('.dismiss-btn').trigger('click')
    expect(wrapper.emitted('dismiss-warning')).toBeTruthy()
  })

  it('dismiss button absent when hasWarning is false', () => {
    const wrapper = mount(MessageActions, {
      props: { content: 'test', hasWarning: false }
    })
    expect(wrapper.find('.dismiss-btn').exists()).toBe(false)
  })
})
```

- [ ] **Step 2: Run tests — verify FAIL**

```bash
cd frontend && npm run test -- MessageActions.spec.js
```

Expected output: `FAIL` with `Cannot find module '../MessageActions.vue'`

- [ ] **Step 3: Create `frontend/src/components/chat/MessageActions.vue`**

```vue
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
```

- [ ] **Step 4: Run tests — verify PASS**

```bash
cd frontend && npm run test -- MessageActions.spec.js
```

Expected: `5 tests passed`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/chat/MessageActions.vue frontend/src/components/chat/__tests__/MessageActions.spec.js
git commit -m "feat(chat): add MessageActions component with copy + dismiss-warning"
```

---

## Task 2: ScrollToTop.vue (TDD)

**Files:**
- Create: `frontend/src/components/chat/__tests__/ScrollToTop.spec.js`
- Create: `frontend/src/components/chat/ScrollToTop.vue`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/chat/__tests__/ScrollToTop.spec.js`:

```js
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ScrollToTop from '../ScrollToTop.vue'

describe('ScrollToTop', () => {
  it('renders a button', () => {
    const wrapper = mount(ScrollToTop)
    expect(wrapper.find('button').exists()).toBe(true)
  })

  it('emits click when button is clicked', async () => {
    const wrapper = mount(ScrollToTop)
    await wrapper.find('button').trigger('click')
    expect(wrapper.emitted('click')).toBeTruthy()
  })
})
```

- [ ] **Step 2: Run tests — verify FAIL**

```bash
cd frontend && npm run test -- ScrollToTop.spec.js
```

Expected: `FAIL` with `Cannot find module '../ScrollToTop.vue'`

- [ ] **Step 3: Create `frontend/src/components/chat/ScrollToTop.vue`**

```vue
<template>
  <button class="scroll-to-top" @click="$emit('click')" aria-label="Kembali ke atas">
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M8 12V4M4 8l4-4 4 4" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
  </button>
</template>

<script setup>
defineEmits(['click'])
</script>

<style scoped>
.scroll-to-top {
  position: fixed;
  bottom: 90px;
  right: 28px;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--color-navy);
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 8px rgba(26, 58, 107, 0.2);
  transition: background 0.15s;
}

.scroll-to-top:hover {
  background: var(--color-navy-hover);
}
</style>
```

- [ ] **Step 4: Run tests — verify PASS**

```bash
cd frontend && npm run test -- ScrollToTop.spec.js
```

Expected: `2 tests passed`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/chat/ScrollToTop.vue frontend/src/components/chat/__tests__/ScrollToTop.spec.js
git commit -m "feat(chat): add ScrollToTop floating button component"
```

---

## Task 3: MessageBubble.vue updates (TDD)

**Files:**
- Create: `frontend/src/components/chat/__tests__/MessageBubble.spec.js`
- Modify: `frontend/src/components/chat/MessageBubble.vue`

The updates needed:
1. Add `timestamp` prop, render it in `.msg-ai-header`
2. Add `warningDismissed = ref(false)`; `showValidationWarnings` gates on `!warningDismissed.value`
3. Wrap `.msg-ai-bubble` in `.msg-ai-bubble-wrapper` (for CSS hover reveal)
4. Import and mount `<MessageActions>` inside the wrapper, listening to `dismiss-warning`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/chat/__tests__/MessageBubble.spec.js`:

```js
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import MessageBubble from '../MessageBubble.vue'

const assistantMsg = (overrides = {}) => ({
  role: 'assistant',
  content: 'Test answer',
  ...overrides
})

describe('MessageBubble — timestamp', () => {
  it('renders timestamp in header when provided', () => {
    const wrapper = mount(MessageBubble, {
      props: { message: assistantMsg({ timestamp: '09:45' }) }
    })
    expect(wrapper.find('.msg-ai-timestamp').exists()).toBe(true)
    expect(wrapper.find('.msg-ai-timestamp').text()).toBe('09:45')
  })

  it('omits timestamp element when timestamp is null', () => {
    const wrapper = mount(MessageBubble, {
      props: { message: assistantMsg({ timestamp: null }) }
    })
    expect(wrapper.find('.msg-ai-timestamp').exists()).toBe(false)
  })
})

describe('MessageBubble — warning dismissal', () => {
  it('shows validation warnings by default', () => {
    const wrapper = mount(MessageBubble, {
      props: {
        message: assistantMsg({ validation: { warnings: ['Warning A'] } })
      }
    })
    expect(wrapper.find('.validation-warnings').exists()).toBe(true)
  })

  it('hides validation warnings after dismiss button clicked', async () => {
    const wrapper = mount(MessageBubble, {
      props: {
        message: assistantMsg({ validation: { warnings: ['Warning A'] } })
      }
    })
    await wrapper.find('.dismiss-btn').trigger('click')
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.validation-warnings').exists()).toBe(false)
  })
})
```

- [ ] **Step 2: Run tests — verify FAIL**

```bash
cd frontend && npm run test -- MessageBubble.spec.js
```

Expected: 2 tests FAIL — `.msg-ai-timestamp` not found and `.dismiss-btn` not found.

- [ ] **Step 3: Update `frontend/src/components/chat/MessageBubble.vue`**

Replace the entire file content with:

```vue
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
```

- [ ] **Step 4: Run tests — verify PASS**

```bash
cd frontend && npm run test -- MessageBubble.spec.js
```

Expected: `4 tests passed`

- [ ] **Step 5: Run the full test suite to confirm no regressions**

```bash
cd frontend && npm run test
```

Expected: all tests pass (includes `messageFormatter.spec.js` from previous work).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/chat/MessageBubble.vue frontend/src/components/chat/__tests__/MessageBubble.spec.js
git commit -m "feat(chat): add timestamp display and dismissible warnings to MessageBubble"
```

---

## Task 4: ChatView.vue updates (scroll + timestamps)

**Files:**
- Modify: `frontend/src/views/ChatView.vue`

No unit tests for this task — scroll events and SSE streaming are verified manually. All changes are localized to ChatView.

- [ ] **Step 1: Add `showScrollTop` state and scroll handler**

In `frontend/src/views/ChatView.vue`, in the `<script setup>` block, find the existing state declarations (around line 92) and add:

```js
const showScrollTop = ref(false)
```

After the existing `scrollToBottom` function (around line 377), add:

```js
function onMessagesScroll() {
  showScrollTop.value = (messagesContainer.value?.scrollTop ?? 0) > 300
}

function scrollToTop() {
  messagesContainer.value?.scrollTo({ top: 0, behavior: 'smooth' })
}
```

- [ ] **Step 2: Add scroll listener to messages-area and mount ScrollToTop**

In the `<template>`, find the `.messages-area` div (line 37):

```html
<div class="messages-area" ref="messagesContainer">
```

Replace with:

```html
<div class="messages-area" ref="messagesContainer" @scroll="onMessagesScroll">
```

Then find the closing `</div>` of `.chat-main` (just before the closing `</div>` of `.chat-layout`, around line 70). Add ScrollToTop immediately before `</div>` of `.chat-main`:

```html
      <Transition name="fade">
        <ScrollToTop v-if="showScrollTop" @click="scrollToTop" />
      </Transition>
    </div>
```

Also add the import at the top of `<script setup>` (after the existing imports):

```js
import ScrollToTop from '@/components/chat/ScrollToTop.vue'
```

- [ ] **Step 3: Add fade transition CSS**

In the `<style scoped>` block, append:

```css
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
```

- [ ] **Step 4: Add timestamp to user messages**

In `sendMessage()` (around line 278), find:

```js
messages.value.push({ role: 'user', content: userMessage })
```

Replace with:

```js
const nowUser = new Date()
const userHhmm = `${String(nowUser.getHours()).padStart(2, '0')}:${String(nowUser.getMinutes()).padStart(2, '0')}`
messages.value.push({ role: 'user', content: userMessage, timestamp: userHhmm })
```

- [ ] **Step 5: Add timestamp to AI messages at onComplete**

In `sendMessage()`, find the `onComplete` callback (around line 320):

```js
onComplete: async (data) => {
  messages.value[loadingIdx] = {
    role: 'assistant',
    content: data.answer,
    sources: data.sources,
    timing: data.timing,
    validation: data.validation || pendingValidation
  }
```

Replace with:

```js
onComplete: async (data) => {
  const nowAi = new Date()
  const aiHhmm = `${String(nowAi.getHours()).padStart(2, '0')}:${String(nowAi.getMinutes()).padStart(2, '0')}`
  messages.value[loadingIdx] = {
    role: 'assistant',
    content: data.answer,
    sources: data.sources,
    timing: data.timing,
    validation: data.validation || pendingValidation,
    timestamp: aiHhmm
  }
```

- [ ] **Step 6: Add timestamp to history loaded in loadSession**

In `loadSession()` (around line 235), find:

```js
messages.value = history.map((message) => ({
  role: message.role,
  content: message.content,
  sources: message.sources || []
}))
```

Replace with:

```js
messages.value = history.map((message) => {
  let timestamp = null
  if (message.timestamp) {
    const d = new Date(message.timestamp)
    if (!isNaN(d.getTime())) {
      timestamp = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
    }
  }
  return {
    role: message.role,
    content: message.content,
    sources: message.sources || [],
    timestamp
  }
})
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/views/ChatView.vue
git commit -m "feat(chat): add scroll-to-top button and message timestamps in ChatView"
```

- [ ] **Step 8: Manual verification**

Start the frontend dev server:

```bash
cd frontend && npm run dev
```

Open http://localhost:5173 and verify:

1. **Copy button** — hover over any AI message bubble → toolbar appears at bottom-right → click "📋 Salin" → paste into a text editor and confirm content is correct → button shows "✓ Tersalin!" for 2 seconds then resets
2. **Timestamps** — send a message, verify HH:MM appears in AI header and user bubble area after response completes
3. **Dismiss warning** — if a message has validation warnings (trigger by asking an edge-case query), hover the bubble → click ✕ → warning block disappears
4. **Scroll to top** — load a session with many messages (scroll down more than 300px) → floating navy circle button appears bottom-right → click it → page scrolls smoothly to top → button disappears
5. **History timestamps** — load a past session → verify timestamps show if backend returns them; show nothing if backend doesn't
6. **No regressions** — SSE streaming, source cards, sidebar, document pages all work as before
