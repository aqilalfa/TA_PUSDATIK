# Session Management Enhancement — Design Spec

**Date:** 2026-04-25
**Scope:** Frontend only — `ChatSidebar.vue` + `ChatView.vue` — no backend changes
**Aesthetic:** Government Refined (cream/navy/gold) — consistent with existing design system

---

## Problem

The session sidebar shows all conversations in a single flat "Riwayat" list with no date context. Users cannot tell when a session was created, and cannot rename sessions manually (titles are auto-generated from the first message only, and cannot be corrected).

---

## Decisions Made

| Question | Decision |
|---|---|
| Feature scope | Date grouping + inline rename (both) |
| Date groups | 4 buckets: Hari Ini / Kemarin / 7 Hari Lalu / Lebih Lama |
| Rename trigger | Hover reveals pencil icon (✏) — click to start editing |
| Save rename | Enter key or blur (click away) |
| Cancel rename | Escape key |
| Backend changes | None — `PUT /api/sessions/{id}/title` already exists |

---

## Architecture

All changes are frontend-only. The backend's `PUT /api/sessions/{id}/title` endpoint (via `updateSessionTitle()` in `chatService.js`) is already available.

**Data flow for rename:**
```
User clicks ✏ → editingSessionId set → input shown (pre-filled)
→ Enter/blur → emit 'rename-session' {id, title}
→ ChatView handles → updateSessionTitle(id, title) → update sessions array
```

**Data flow for grouping:**
```
sessions prop (Array) → computed groupedSessions
→ filter + sort into 4 date buckets based on updated_at (calendar day)
→ template iterates groupedSessions, skips empty groups
```

---

## Component Design

### 1. `ChatSidebar.vue`

**New reactive state:**
```js
const editingSessionId = ref(null)
const editingTitle = ref('')
const editingOriginalTitle = ref('')
const renameInput = ref(null)
```

**New computed `groupedSessions`:**

Groups the `sessions` prop by calendar-day distance from today using `updated_at`. Returns an array of `{ label, sessions }` objects, filtered to exclude empty groups.

```js
const GROUPS = [
  { label: 'HARI INI',    test: (d) => d === 0 },
  { label: 'KEMARIN',     test: (d) => d === 1 },
  { label: '7 HARI LALU', test: (d) => d >= 2 && d <= 7 },
  { label: 'LEBIH LAMA',  test: (d) => d > 7 },
]

const groupedSessions = computed(() => {
  const today = new Date()
  today.setHours(0, 0, 0, 0)

  return GROUPS
    .map(({ label, test }) => ({
      label,
      sessions: props.sessions.filter((s) => {
        const d = new Date(s.updated_at)
        d.setHours(0, 0, 0, 0)
        const diffDays = Math.round((today - d) / 86400000)
        return test(diffDays)
      })
    }))
    .filter(({ sessions }) => sessions.length > 0)
})
```

**New template structure** (replaces the single `<div class="session-group-label">Riwayat</div>` + v-for):

```html
<template v-for="group in groupedSessions" :key="group.label">
  <div class="session-group-label">{{ group.label }}</div>
  <div
    v-for="session in group.sessions"
    :key="session.id"
    class="session-item"
    :class="{ active: currentSessionId === session.id }"
    @click="onSessionClick(session)"
  >
    <!-- Viewing mode -->
    <template v-if="editingSessionId !== session.id">
      <div class="session-item-content">
        <span class="session-title">{{ session.title }}</span>
      </div>
      <button
        class="session-rename-btn"
        @click.stop="startEdit(session)"
        title="Ubah nama"
      >✏</button>
      <button
        class="session-delete-btn"
        @click.stop="$emit('delete-session', session.id)"
        title="Hapus sesi"
      ><!-- × svg --></button>
    </template>
    <!-- Editing mode -->
    <template v-else>
      <input
        class="session-rename-input"
        v-model="editingTitle"
        @keydown.enter.prevent="commitEdit"
        @keydown.escape.prevent="cancelEdit"
        @blur="commitEdit"
        ref="renameInput"
      />
    </template>
  </div>
</template>
```

**New functions:**
```js
function startEdit(session) {
  editingSessionId.value = session.id
  editingTitle.value = session.title
  editingOriginalTitle.value = session.title
  nextTick(() => renameInput.value?.focus())
}

function commitEdit() {
  if (!editingSessionId.value) return
  const trimmed = editingTitle.value.trim()
  if (trimmed && trimmed !== editingOriginalTitle.value) {
    emit('rename-session', { id: editingSessionId.value, title: trimmed })
  }
  editingSessionId.value = null
}

function cancelEdit() {
  editingSessionId.value = null
}

function onSessionClick(session) {
  if (editingSessionId.value === session.id) return
  emit('load-session', session.id)
}
```

**New CSS classes:**
- `.session-rename-btn` — same pattern as `.session-delete-btn` (opacity: 0, visible on hover); gold color on hover
- `.session-rename-input` — full width, transparent background, white text, gold border-bottom, no outer border; font matches `.session-title`

**Updated `defineEmits`:**
```js
const emit = defineEmits([
  'toggle-sidebar', 'new-chat', 'load-session',
  'delete-session', 'rename-session',            // ← new
  'update:selectedModel', 'model-change'
])
```

---

### 2. `ChatView.vue`

Add handler on `<ChatSidebar>`:
```html
<ChatSidebar
  ...
  @rename-session="handleRenameSession"
/>
```

Add function:
```js
async function handleRenameSession({ id, title }) {
  try {
    await updateSessionTitle(id, title)
    const session = sessions.value.find(s => s.id === id)
    if (session) session.title = title
  } catch (err) {
    console.error('Failed to rename session', err)
  }
}
```

Import `updateSessionTitle` from `chatService.js` if not already imported in ChatView (it is already used for auto-title generation — verify import exists).

---

### 3. Test File — `ChatSidebar.spec.js`

**Location:** `frontend/src/components/chat/__tests__/ChatSidebar.spec.js`

Tests (TDD — write first):

1. **Date grouping — today:** session with `updated_at = now` appears under "HARI INI"
2. **Date grouping — yesterday:** session with `updated_at = yesterday` appears under "KEMARIN"
3. **Date grouping — 3 days ago:** session appears under "7 HARI LALU"
4. **Date grouping — 10 days ago:** session appears under "LEBIH LAMA"
5. **Empty groups hidden:** if no sessions today, "HARI INI" label not rendered
6. **Rename — pencil click sets edit mode:** click `.session-rename-btn` → `.session-rename-input` appears
7. **Rename — Enter emits rename-session:** type new title + press Enter → `rename-session` emitted with `{id, title}`
8. **Rename — Escape cancels:** press Escape → input disappears, original title shown
9. **Rename — blank title does not emit:** clear input + Enter → no `rename-session` event
10. **Click session does not trigger rename if editing:** clicking while in edit mode should not emit `load-session`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `frontend/src/components/chat/ChatSidebar.vue` | Modify | `groupedSessions` computed, rename state, template update, new CSS |
| `frontend/src/views/ChatView.vue` | Modify | Handle `rename-session` event, call `updateSessionTitle` |
| `frontend/src/components/chat/__tests__/ChatSidebar.spec.js` | Create | Unit tests (TDD) |

---

## What Is NOT in Scope

- Session search or filter
- Bulk delete sessions
- Drag-to-reorder sessions
- Session tags or labels
- Any backend changes
- Mobile responsiveness changes
- Collapsible date groups
