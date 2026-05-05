# Chat Interactivity — Design Spec

**Date:** 2026-04-23  
**Scope:** Frontend only — Vue 3 + Vite, no backend changes  
**Aesthetic:** Government Refined (cream/navy/gold) — consistent with existing design system

---

## Problem

The current chat UI lacks basic interactivity that users need in daily BSSN workflows:

1. No way to copy an AI answer to clipboard (needed for reports and documentation)
2. Timestamps are absent — users cannot tell when a message was sent
3. Validation warnings cannot be dismissed once read
4. No navigation aid in long conversations (scroll-to-top)

---

## Approach: Two New Components (Approach 2)

Create two focused components and make minimal updates to existing ones. No composables — the logic is simple enough to live in the components directly.

| File | Change |
|---|---|
| `frontend/src/components/chat/MessageActions.vue` | **New** — copy button + dismiss warning |
| `frontend/src/components/chat/ScrollToTop.vue` | **New** — floating scroll-to-top button |
| `frontend/src/components/chat/MessageBubble.vue` | **Update** — add timestamp to header, use MessageActions |
| `frontend/src/views/ChatView.vue` | **Update** — mount ScrollToTop, add scroll listener |

---

## Component Designs

### 1. `MessageActions.vue`

**Purpose:** Per-message toolbar that appears on hover over an AI bubble.

**Props:**
```js
{
  content: String,      // raw markdown text to copy
  hasWarning: Boolean,  // whether validation warnings exist
}
```

**Emits:** `dismiss-warning`

**Behavior:**
- The entire toolbar is `opacity: 0` by default; the parent `.msg-ai-bubble:hover` reveals it via CSS (`opacity: 1`)
- **Copy button:** calls `navigator.clipboard.writeText(content)`, then shows "✓ Tersalin!" for 2 seconds via a local `copied` ref, then resets. If clipboard API is unavailable or throws, shows "✗ Gagal" for 2 seconds instead.
- **Dismiss button:** only renders when `hasWarning` is true; emits `dismiss-warning` to parent

**Layout (bottom-right of bubble):**
```
                                [📋 Salin]   (always present)
⚠ Peringatan Validasi    [✕]               (only when hasWarning)
```

**Style tokens used:**
- `--color-navy`, `--color-gold`, `--color-border`, `--font-ui`
- Copy button: `10px`, gold on hover, border 1px `--color-border`
- Dismiss X: `9px`, muted text, hover red

---

### 2. `ScrollToTop.vue`

**Purpose:** Global floating button to scroll back to the top of the messages area.

**Props:** none  
**Emits:** `click`

**Behavior:**
- Controlled by parent (`v-if="showScrollTop"`) — the component itself is always fully visible when mounted
- Fade-in/out handled by `<Transition name="fade">` in `ChatView.vue`
- Smooth scroll handled by the parent's `scrollToTop()` function

**Style:**
- 36×36px circle, `background: var(--color-navy)`, white `↑` SVG icon
- `position: fixed; bottom: 90px; right: 28px` (above ChatInput which is ~72px tall)
- Hover: `background: var(--color-navy-hover)`
- Box shadow: `0 2px 8px rgba(26,58,107,0.2)`

---

### 3. `MessageBubble.vue` — updates

**Timestamp in header:**
- Add `timestamp` prop (`String | null`, default `null`)
- Render timestamp in `.msg-ai-header` between sources count and timing
- Format: `HH:MM`, style: `9px`, `--color-text-light`, `--font-ui`
- Source of timestamp: `message.timestamp` passed from parent (ChatView loads history with timestamp from DB)

**Warning dismissal:**
- Add local `warningDismissed = ref(false)` inside the component
- `showValidationWarnings` computed gates on `!warningDismissed.value`
- `MessageActions` emits `dismiss-warning` → handler sets `warningDismissed.value = true`

**Hover reveal for MessageActions:**
- Wrap `.msg-ai-bubble` in a `.msg-ai-bubble-wrapper` that has `position: relative`
- CSS: `.msg-ai-bubble-wrapper:hover .message-actions { opacity: 1 }`

---

### 4. `ChatView.vue` — updates

**Scroll listener:**
```js
const showScrollTop = ref(false)

function onMessagesScroll() {
  showScrollTop.value = (messagesContainer.value?.scrollTop ?? 0) > 300
}
// <div class="messages-area" @scroll="onMessagesScroll" ref="messagesContainer">
```

**ScrollToTop mount:**
```html
<Transition name="fade">
  <ScrollToTop v-if="showScrollTop" @click="scrollToTop" />
</Transition>
```

**Fade transition CSS (in ChatView scoped styles):**
```css
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
```

---

## Timestamp Source

When a message is streaming or new (not from history), `message.timestamp` is not yet set. The timestamp should be set at the moment the `onComplete` SSE event fires in `ChatView.sendMessage()`:

```js
onComplete: async (data) => {
  const now = new Date()
  const hhmm = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`
  messages.value[loadingIdx] = {
    role: 'assistant',
    content: data.answer,
    sources: data.sources,
    timing: data.timing,
    validation: data.validation || pendingValidation,
    timestamp: hhmm,   // ← added
  }
}
```

For user messages, timestamp is set at send time (same pattern in `sendMessage()`).

For history loaded via `loadSession()`, the backend returns `message.timestamp` as ISO string — extract HH:MM from it.

---

## What Is NOT in Scope

- Dark mode / theme toggle
- Message feedback (thumbs up/down)  
- Session rename or export
- Mobile responsiveness
- Backend changes of any kind

---

## Testing

Each new component gets a Vitest unit test in `src/components/chat/__tests__/`:

- `MessageActions.spec.js` — copy text calls clipboard API; copied state resets after 2s; dismiss-warning emitted on click; dismiss button absent when hasWarning=false
- `ScrollToTop.spec.js` — renders a button; emits click on interaction

`MessageBubble` existing behavior stays covered by extending `messageFormatter.spec.js` if needed.
