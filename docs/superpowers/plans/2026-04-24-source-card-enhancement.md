# Source Card Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add hover-expand panels to source cards showing a text snippet, hierarchy path, and a link that opens the document detail page in a new tab.

**Architecture:** One backend field (`snippet`) added to the existing `sources.append()` dict in `langchain_engine.py`. The frontend `SourceCard.vue` gets a wrapper element whose hover state reveals an expand panel via CSS transition. Click on the wrapper calls `window.open('/documents/:doc_id', '_blank')`. Tests are written first (TDD).

**Tech Stack:** Python/FastAPI backend, Vue 3 Composition API (`<script setup>`), Vitest + @vue/test-utils + happy-dom, vanilla CSS with design tokens.

**Spec:** `docs/superpowers/specs/2026-04-24-source-card-enhancement-design.md`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `backend/app/core/rag/langchain_engine.py` | Modify (~line 1392) | Add `snippet` field to sources dict |
| `frontend/src/components/chat/SourceCard.vue` | Modify | Hover expand panel, score display, click-to-open |
| `frontend/src/components/chat/__tests__/SourceCard.spec.js` | Create | Unit tests (TDD) |

---

## Task 1: SourceCard.vue — TDD

**Files:**
- Create: `frontend/src/components/chat/__tests__/SourceCard.spec.js`
- Modify: `frontend/src/components/chat/SourceCard.vue`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/chat/__tests__/SourceCard.spec.js`:

```js
import { describe, it, expect, vi, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import SourceCard from '../SourceCard.vue'

const baseSource = {
  id: 1,
  doc_id: 'doc-abc',
  document: 'Perpres No. 95 Tahun 2018',
  citation_title: 'Perpres No. 95 Tahun 2018',
  section: 'Pasal 1 Ayat 3',
  score: 0.87,
  snippet: 'penyelenggaraan pemerintahan yang memanfaatkan teknologi informasi',
  hierarchy_path: 'BAB I › Ketentuan Umum'
}

describe('SourceCard', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders document title and section', () => {
    const wrapper = mount(SourceCard, { props: { source: baseSource } })
    expect(wrapper.find('.source-title').text()).toContain('Perpres No. 95')
    expect(wrapper.find('.source-meta').text()).toContain('Pasal 1 Ayat 3')
  })

  it('shows score when source.score > 0', () => {
    const wrapper = mount(SourceCard, { props: { source: baseSource } })
    expect(wrapper.find('.source-score').text()).toContain('0.87')
  })

  it('does not show score element when score is 0', () => {
    const wrapper = mount(SourceCard, { props: { source: { ...baseSource, score: 0 } } })
    expect(wrapper.find('.source-score').exists()).toBe(false)
  })

  it('renders snippet in expand panel when present', () => {
    const wrapper = mount(SourceCard, { props: { source: baseSource } })
    expect(wrapper.find('.expand-snippet').text()).toContain('penyelenggaraan pemerintahan')
  })

  it('does not render snippet element when snippet is absent', () => {
    const wrapper = mount(SourceCard, { props: { source: { ...baseSource, snippet: undefined } } })
    expect(wrapper.find('.expand-snippet').exists()).toBe(false)
  })

  it('calls window.open with correct URL on click when doc_id present', async () => {
    vi.spyOn(window, 'open').mockImplementation(() => null)
    const wrapper = mount(SourceCard, { props: { source: baseSource } })
    await wrapper.find('.source-card-wrapper').trigger('click')
    expect(window.open).toHaveBeenCalledWith('/documents/doc-abc', '_blank')
  })

  it('does not call window.open when doc_id is empty', async () => {
    vi.spyOn(window, 'open').mockImplementation(() => null)
    const wrapper = mount(SourceCard, {
      props: { source: { ...baseSource, doc_id: '' } }
    })
    await wrapper.find('.source-card-wrapper').trigger('click')
    expect(window.open).not.toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Run tests — verify FAIL**

```bash
cd frontend && npm run test -- SourceCard.spec.js
```

Expected: `FAIL` — `.source-card-wrapper` not found, `.source-score` not found, `.expand-snippet` not found.

- [ ] **Step 3: Rewrite `frontend/src/components/chat/SourceCard.vue`**

Read the current file first, then replace entirely with:

```vue
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
```

- [ ] **Step 4: Run tests — verify PASS**

```bash
cd frontend && npm run test -- SourceCard.spec.js
```

Expected: `7 tests passed`

- [ ] **Step 5: Run full suite — check no regressions**

```bash
cd frontend && npm run test
```

Expected: all tests pass (28 existing + 7 new = 35 total).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/chat/SourceCard.vue frontend/src/components/chat/__tests__/SourceCard.spec.js
git commit -m "feat(chat): enhance SourceCard with hover snippet preview and doc link"
```

---

## Task 2: Backend — add `snippet` field

**Files:**
- Modify: `backend/app/core/rag/langchain_engine.py` (line ~1380)

No unit tests for this task — the field is a simple string slice. Verified manually by sending a chat message and inspecting the `sources` array in the browser network tab.

- [ ] **Step 1: Add `snippet` to `sources.append()`**

In `backend/app/core/rag/langchain_engine.py`, find the `sources.append({` block (around line 1380). The loop variable is `doc` and the text is `doc.page_content`.

Replace:

```python
            sources.append({
                "id": i,
                "doc_id": str(meta.get("doc_id") or meta.get("document_id") or ""),
                "document": citation_title,
                "document_short": doc_title,
                "citation_title": citation_title,
                "citation_label": f"[{i}] {citation_title}",
                "section": section,
                "pasal": str(meta.get("pasal") or ""),
                "ayat": str(meta.get("ayat") or ""),
                "context_header": str(meta.get("context_header") or ""),
                "hierarchy_path": str(meta.get("hierarchy_path") or ""),
                "score": float(score),
            })
```

With:

```python
            _text = doc.page_content or ""
            sources.append({
                "id": i,
                "doc_id": str(meta.get("doc_id") or meta.get("document_id") or ""),
                "document": citation_title,
                "document_short": doc_title,
                "citation_title": citation_title,
                "citation_label": f"[{i}] {citation_title}",
                "section": section,
                "pasal": str(meta.get("pasal") or ""),
                "ayat": str(meta.get("ayat") or ""),
                "context_header": str(meta.get("context_header") or ""),
                "hierarchy_path": str(meta.get("hierarchy_path") or ""),
                "score": float(score),
                "snippet": (_text[:150].rstrip() + "…") if len(_text) > 150 else _text,
            })
```

- [ ] **Step 2: Verify backend starts without errors**

```bash
cd backend
venv/Scripts/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Expected: server starts, no import errors.

- [ ] **Step 3: Manual verification**

With the dev server running, open the chat at http://localhost:5173, send a query (e.g., "Apa itu SPBE?"), then:

1. Open browser DevTools → Network tab → find the `stream` request → look at the `complete` SSE event payload
2. Confirm `sources[0].snippet` contains a non-empty string (≤150 chars + "…")
3. Hover over a source card → confirm the expand panel appears with the snippet text
4. Click a source card → confirm a new tab opens at `/documents/:doc_id`

- [ ] **Step 4: Commit**

```bash
git add backend/app/core/rag/langchain_engine.py
git commit -m "feat(rag): add snippet field to source objects for frontend preview"
```
