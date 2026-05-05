# Source Card Enhancement — Design Spec

**Date:** 2026-04-24
**Scope:** Backend (1 field) + Frontend (SourceCard.vue) — no new endpoints, no schema changes
**Aesthetic:** Government Refined (cream/navy/gold) — consistent with existing design system

---

## Problem

Source cards in the chat UI show only the document title and section label. Users cannot see what text was actually cited, making it hard to verify whether the AI answer is grounded in the right content. The cards are also not linked to the document detail page.

---

## Decisions Made

| Question | Decision |
|---|---|
| Show snippet or metadata only? | Snippet (requires small backend change) |
| How to display snippet? | Hidden by default, reveal on hover (expand panel below card) |
| Click action? | Open document detail page in new tab |

---

## Approach: Hover-Expand Panel (Rich Card)

Card stays compact in default state. On hover, an expand panel slides in below with the snippet text, hierarchy path, and a link to the document. A single small change to the backend adds the `snippet` field.

---

## Component Designs

### 1. Backend — `langchain_engine.py`

**Location:** `sources.append({...})` block at line ~1380.

Add one field to the existing dict:

```python
"snippet": (text[:150].rstrip() + "…") if len(text) > 150 else text,
```

`text` is already in scope at that point (it is the chunk's full text from retrieval).

This field is included in `sources_for_response`, serialized as JSON in `conv.sources`, and returned in both streaming (`onComplete`) and session history (`loadSession`). No other backend changes needed.

**Note:** Messages already stored in the DB do not have `snippet` — `SourceCard` must handle `source.snippet` being `undefined` or `null` gracefully (show nothing in the expand panel in that case).

---

### 2. Frontend — `SourceCard.vue`

**Default state (unchanged visually):**
- Same compact card: `📎 SUMBER [N]`, document title, section
- New: relevance score displayed in header if `source.score > 0` — e.g., `· 0.87`

**Hover state:**
- `.source-card-wrapper:hover .source-expand { opacity: 1; max-height: 200px }`
- Expand panel shows below the card (border-top: none, seamless join)
- Panel content:
  - Snippet text (italic, 9px, `--color-text`, `--font-body`) — only if `source.snippet` is present
  - Hierarchy path (8px, muted) — only if `source.hierarchy_path` is present
  - "🔗 Buka dokumen ↗" link — only if `source.doc_id` is non-empty

**Click behavior:**
- Clicking the entire `.source-card-wrapper` calls `window.open('/documents/' + source.doc_id, '_blank')`
- Guard: click handler is a no-op if `source.doc_id` is empty; `cursor: pointer` only applied when `source.doc_id` is non-empty

**Route compatibility (verified):**
- Route `/documents/:doc_id` exists in `frontend/src/router.js`
- `DocumentDetailView` reads `route.params.doc_id` as string
- Backend `get_document()` accepts UUID strings and numeric-ID strings — both work

**New template structure:**

```vue
<div class="source-card-wrapper" @click="openDocument">
  <div class="source-card">
    <div class="source-num">📎 SUMBER [{{ source.id }}]<span v-if="source.score > 0" class="source-score"> · {{ source.score.toFixed(2) }}</span></div>
    <div class="source-title">{{ source.citation_title || source.document }}</div>
    <div v-if="source.section" class="source-meta">{{ source.section }}</div>
  </div>
  <div class="source-expand">
    <p v-if="source.snippet" class="expand-snippet">{{ source.snippet }}</p>
    <p v-if="source.hierarchy_path" class="expand-path">{{ source.hierarchy_path }}</p>
    <span v-if="source.doc_id" class="expand-link">🔗 Buka dokumen ↗</span>
  </div>
</div>
```

**Style tokens used:**
- `--color-navy`, `--color-gold`, `--color-border`, `--color-text-muted`, `--color-text-light`
- `--font-ui`, `--font-body`
- Expand panel transition: `max-height 0.2s ease, opacity 0.15s`

---

## File Map

| File | Action |
|---|---|
| `backend/app/core/rag/langchain_engine.py` | Modify — add `snippet` field to `sources.append()` |
| `frontend/src/components/chat/SourceCard.vue` | Modify — hover expand panel, score display, click-to-open |
| `frontend/src/components/chat/__tests__/SourceCard.spec.js` | Create — unit tests (TDD) |

---

## Testing

`SourceCard.spec.js` tests (written first — TDD):

1. Renders document title and section
2. Shows relevance score when `source.score > 0`
3. Expand panel contains snippet when `source.snippet` is present
4. Expand panel does not render snippet element when `source.snippet` is absent
5. `window.open` called with correct URL on click when `source.doc_id` is set
6. No click navigation when `source.doc_id` is empty string

---

## What Is NOT in Scope

- Pagination or "read more" for long snippets (150 char truncation is enough)
- Backfilling `snippet` for existing DB history (no migration)
- Changes to MessageBubble layout (source cards stay flex-wrap horizontal)
- Any change to other API endpoints
- Mobile responsiveness changes
