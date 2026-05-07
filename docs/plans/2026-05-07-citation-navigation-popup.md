# Citation-to-Document Navigation + Preview Popup

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Menambahkan fitur navigasi sitasi ke dokumen asli (PDF) + popup preview chunk saat citation `[N]` diklik dalam chat.

**Architecture:**
- **Backend:** Tambah 2 endpoint baru di `documents.py` — satu untuk serve file PDF via `FileResponse`, satu untuk ambil single chunk by index.
- **Frontend:** Ubah `injectCitationSpans` agar citation menjadi `<button>` interaktif. Buat komponen `CitationPopup.vue` baru. Perbarui `SourceCard.vue` agar ada dua tombol aksi (PDF + Deep Link). Update `DocumentDetailView.vue` untuk terima query param `?highlight=` dan auto-scroll/highlight.

**Tech Stack:** FastAPI FileResponse, Vue 3 Composition API, CSS Teleport

---

### Task 1: Backend — Endpoint Serve PDF File

**Files:**
- Modify: `backend/app/api/routes/documents.py`

**Step 1: Write the failing test**

Buat file `backend/tests/test_document_file_endpoint.py`:
```python
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_get_document_file_returns_404_for_nonexistent():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/rag/documents/nonexistent-uuid/file")
    assert response.status_code == 404
```

**Step 2: Run test to verify it fails**

```bash
cd backend
venv/Scripts/pytest.exe tests/test_document_file_endpoint.py -v
```
Expected: FAIL — endpoint belum ada.

**Step 3: Tambahkan endpoint di `documents.py`**

Di `backend/app/api/routes/documents.py`, tambahkan dua import dan dua endpoint setelah baris `router = APIRouter()`:

```python
from fastapi.responses import FileResponse

# ... (setelah endpoint list_documents yang ada)

@router.get("/by-doc-id/{doc_id}/file")
def serve_document_file(doc_id: str, db: Session = Depends(get_db)):
    """Serve the original PDF file for a document."""
    document = db.query(Document).filter(Document.doc_id == doc_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    file_path = document.file_path or document.original_path
    if not file_path or not Path(file_path).exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=document.original_filename or document.filename,
    )


@router.get("/by-doc-id/{doc_id}/chunks/{chunk_index}")
def get_chunk_by_index(doc_id: str, chunk_index: int, db: Session = Depends(get_db)):
    """Get a single chunk by document doc_id and chunk_index (for citation popup)."""
    from app.models.db_models import Chunk
    
    document = db.query(Document).filter(Document.doc_id == doc_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    chunk = db.query(Chunk).filter(
        Chunk.document_id == document.id,
        Chunk.chunk_index == chunk_index
    ).first()
    
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")
    
    import json
    meta = {}
    if chunk.chunk_metadata:
        try:
            meta = json.loads(chunk.chunk_metadata)
        except Exception:
            pass
    
    return {
        "chunk_index": chunk.chunk_index,
        "text": chunk.chunk_text,
        "pasal": meta.get("pasal"),
        "bab": meta.get("bab"),
        "context_header": meta.get("context_header"),
        "document_title": document.document_title or document.filename,
        "doc_id": document.doc_id,
        "doc_type": document.doc_type,
    }
```

**Step 4: Run test to verify it passes**

```bash
venv/Scripts/pytest.exe tests/test_document_file_endpoint.py -v
```
Expected: PASS.

**Step 5: Manual smoke test**

Jalankan backend, buka browser ke `http://localhost:8000/api/rag/documents/by-doc-id/{doc_id}/file` — seharusnya PDF ter-download/tampil.

**Step 6: Commit**

```bash
git add backend/app/api/routes/documents.py backend/tests/test_document_file_endpoint.py
git commit -m "feat(api): add PDF file serve and chunk-by-index endpoints"
```

---

### Task 2: Frontend — Service Layer untuk Endpoint Baru

**Files:**
- Modify: `frontend/src/services/documentService.js`

**Step 1: Tambahkan dua fungsi baru di `documentService.js`**

Buka `frontend/src/services/documentService.js`. Tambahkan di akhir file:

```js
/**
 * Returns a URL to stream the PDF file for a document.
 * Digunakan langsung sebagai href/window.open, bukan fetch.
 */
export function getDocumentFileUrl(docId) {
  return `${API_BASE_URL}/api/rag/documents/by-doc-id/${docId}/file`
}

/**
 * Fetch a single chunk by doc_id + chunk_index (untuk citation popup).
 */
export async function getChunkByIndex(docId, chunkIndex) {
  try {
    const { data } = await api.get(
      `/api/rag/documents/by-doc-id/${docId}/chunks/${chunkIndex}`
    )
    return data
  } catch (error) {
    throw new Error(getErrorMessage(error, 'Failed to fetch chunk'))
  }
}
```

Pastikan `API_BASE_URL` dan `api` sudah di-import. Kalau belum, tambahkan:
```js
import api, { API_BASE_URL, getErrorMessage } from './api'
```

**Step 2: Commit**

```bash
git add frontend/src/services/documentService.js
git commit -m "feat(service): add getDocumentFileUrl and getChunkByIndex helpers"
```

---

### Task 3: Frontend — SourceCard Upgrade (Dua Tombol Aksi)

**Files:**
- Modify: `frontend/src/components/chat/SourceCard.vue`

**Step 1: Perbarui `SourceCard.vue`**

Ganti seluruh isi file dengan versi berikut (perubahan utama: tambah tombol PDF + deep-link ke chunk):

```vue
<template>
  <div
    class="source-card-wrapper"
    :class="{ clickable: source.doc_id }"
  >
    <div class="source-card">
      <div class="source-num">
        📎 SUMBER [{{ source.id }}]<span v-if="source.score > 0" class="source-score"> · {{ Number(source.score).toFixed(2) }}</span>
      </div>
      <div class="source-title">{{ source.citation_title || source.document }}</div>
      <div v-if="source.section" class="source-meta">{{ source.section }}</div>
    </div>
    <div class="source-expand">
      <p v-if="source.snippet" class="expand-snippet">{{ source.snippet }}</p>
      <p v-if="source.hierarchy_path" class="expand-path">{{ source.hierarchy_path }}</p>
      <div v-if="source.doc_id" class="expand-actions">
        <button class="action-btn pdf" @click.stop="openPdf">
          📄 Buka PDF ↗
        </button>
        <button class="action-btn ctx" @click.stop="openContext">
          🔍 Lihat Konteks →
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { getDocumentFileUrl } from '@/services/documentService'

const props = defineProps({
  source: { type: Object, required: true }
})

function openPdf() {
  if (props.source.doc_id) {
    window.open(getDocumentFileUrl(props.source.doc_id), '_blank', 'noopener,noreferrer')
  }
}

function openContext() {
  if (props.source.doc_id) {
    // chunk_index tersimpan di metadata source dari API
    const chunkIdx = props.source.chunk_index ?? ''
    const url = chunkIdx !== ''
      ? `/documents/${props.source.doc_id}?highlight=${chunkIdx}`
      : `/documents/${props.source.doc_id}`
    window.open(url, '_blank', 'noopener,noreferrer')
  }
}
</script>

<style scoped>
/* ... Pertahankan CSS lama, tambahkan: */
.expand-actions {
  display: flex;
  gap: 6px;
  margin-top: 6px;
}

.action-btn {
  flex: 1;
  padding: 4px 8px;
  font-size: 9px;
  font-family: var(--font-ui);
  font-weight: 600;
  border-radius: 2px;
  cursor: pointer;
  border: 1px solid var(--color-border);
  background: white;
  color: var(--color-text-muted);
  transition: all 0.15s;
}

.action-btn.pdf:hover {
  border-color: var(--color-navy);
  color: var(--color-navy);
  background: #eef2f9;
}

.action-btn.ctx:hover {
  border-color: var(--color-gold);
  color: #8b7355;
  background: #fdf8ee;
}
</style>
```

> **Note:** CSS lama dari SourceCard harus tetap ada (source-card-wrapper, source-card, source-expand, dll). Hanya hapus `expand-link` lama dan ganti dengan `expand-actions`.

**Step 2: Pastikan `chunk_index` diteruskan dari backend ke source**

Cek `backend/app/core/rag/langchain_engine.py` di fungsi `retrieve_context` bagian build `sources` list (sekitar baris 1344–1390). Tambahkan field `chunk_index` ke dict source:

```python
sources.append({
    ...
    "chunk_index": meta.get("chunk_index"),  # ← tambahkan baris ini
    ...
})
```

**Step 3: Commit**

```bash
git add frontend/src/components/chat/SourceCard.vue backend/app/core/rag/langchain_engine.py
git commit -m "feat(ui): upgrade SourceCard with PDF and context deep-link buttons"
```

---

### Task 4: Frontend — CitationPopup Component

**Files:**
- Create: `frontend/src/components/chat/CitationPopup.vue`
- Modify: `frontend/src/components/chat/MessageBubble.vue`
- Modify: `frontend/src/utils/messageFormatter.js`

**Step 1: Buat `CitationPopup.vue`**

Buat file baru `frontend/src/components/chat/CitationPopup.vue`:

```vue
<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="citation-popup"
      :style="positionStyle"
      @mouseenter="cancelClose"
      @mouseleave="scheduleClose"
    >
      <!-- Loading state -->
      <div v-if="loading" class="popup-loading">
        <span class="popup-spinner"></span>
        Memuat...
      </div>

      <!-- Error state -->
      <div v-else-if="error" class="popup-error">
        ⚠ Gagal memuat chunk
      </div>

      <!-- Content state -->
      <template v-else-if="chunk">
        <div class="popup-meta">
          <span class="popup-doc">{{ chunk.document_title }}</span>
          <span v-if="chunk.bab" class="popup-badge bab">{{ chunk.bab }}</span>
          <span v-if="chunk.pasal" class="popup-badge pasal">{{ chunk.pasal }}</span>
        </div>
        <div class="popup-text">{{ truncatedText }}</div>
        <div class="popup-actions">
          <button class="popup-btn pdf" @click="openPdf">📄 Buka PDF ↗</button>
          <button class="popup-btn ctx" @click="openContext">🔍 Lihat Konteks →</button>
        </div>
      </template>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { getChunkByIndex, getDocumentFileUrl } from '@/services/documentService'

const props = defineProps({
  // Source object dari message.sources yang sesuai dengan citation ID
  source: { type: Object, default: null },
  // posisi anchor (dari getBoundingClientRect)
  anchorRect: { type: Object, default: null },
})

const emit = defineEmits(['close'])

const visible = ref(false)
const loading = ref(false)
const error = ref(false)
const chunk = ref(null)
let closeTimer = null

const positionStyle = computed(() => {
  if (!props.anchorRect) return {}
  const rect = props.anchorRect
  const top = rect.bottom + window.scrollY + 6
  const left = Math.min(rect.left + window.scrollX, window.innerWidth - 280)
  return {
    top: `${top}px`,
    left: `${left}px`,
  }
})

const truncatedText = computed(() => {
  const text = chunk.value?.text || ''
  return text.length > 300 ? text.slice(0, 300) + '…' : text
})

async function show() {
  if (!props.source?.doc_id) return
  visible.value = true
  loading.value = true
  error.value = false
  chunk.value = null

  try {
    const idx = props.source.chunk_index
    if (idx !== null && idx !== undefined) {
      chunk.value = await getChunkByIndex(props.source.doc_id, idx)
    } else {
      // Fallback: gunakan snippet dari source jika tidak ada chunk_index
      chunk.value = {
        document_title: props.source.citation_title || props.source.document,
        text: props.source.snippet || '(Tidak ada pratinjau)',
        bab: null,
        pasal: props.source.pasal || null,
        doc_id: props.source.doc_id,
      }
    }
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function hide() {
  visible.value = false
  chunk.value = null
  emit('close')
}

function scheduleClose() {
  closeTimer = setTimeout(hide, 300)
}

function cancelClose() {
  clearTimeout(closeTimer)
}

function openPdf() {
  if (props.source?.doc_id) {
    window.open(getDocumentFileUrl(props.source.doc_id), '_blank', 'noopener,noreferrer')
  }
}

function openContext() {
  if (props.source?.doc_id) {
    const idx = props.source.chunk_index ?? ''
    const url = idx !== ''
      ? `/documents/${props.source.doc_id}?highlight=${idx}`
      : `/documents/${props.source.doc_id}`
    window.open(url, '_blank', 'noopener,noreferrer')
  }
}

// Expose show/hide untuk dipanggil dari parent
defineExpose({ show, hide, scheduleClose, cancelClose })
</script>

<style scoped>
.citation-popup {
  position: absolute;
  z-index: 9999;
  width: 260px;
  background: white;
  border: 1px solid var(--color-border);
  border-left: 3px solid var(--color-gold);
  border-radius: 0 4px 4px 4px;
  box-shadow: 0 4px 20px rgba(26, 58, 107, 0.14);
  padding: 10px 12px;
  font-family: var(--font-ui);
  animation: popupIn 0.15s ease;
}

@keyframes popupIn {
  from { opacity: 0; transform: translateY(-4px); }
  to   { opacity: 1; transform: translateY(0); }
}

.popup-loading {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--color-text-muted);
}

.popup-spinner {
  display: inline-block;
  width: 10px;
  height: 10px;
  border: 1.5px solid rgba(139, 115, 85, 0.3);
  border-top-color: #8b7355;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.popup-error {
  font-size: 11px;
  color: #c0392b;
}

.popup-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  margin-bottom: 6px;
}

.popup-doc {
  font-size: 9px;
  font-weight: 600;
  color: var(--color-navy);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 160px;
}

.popup-badge {
  font-size: 8px;
  padding: 1px 5px;
  border-radius: 2px;
  font-weight: 600;
  white-space: nowrap;
}

.popup-badge.bab {
  background: #fdf8ee;
  color: #8b7355;
  border: 1px solid #e0c97a;
}

.popup-badge.pasal {
  background: var(--color-status-info-bg);
  color: var(--color-status-info-text);
  border: 1px solid var(--color-status-info-border);
}

.popup-text {
  font-size: 10px;
  font-family: var(--font-body);
  line-height: 1.6;
  color: var(--color-text);
  font-style: italic;
  margin-bottom: 8px;
  max-height: 100px;
  overflow-y: auto;
}

.popup-actions {
  display: flex;
  gap: 5px;
}

.popup-btn {
  flex: 1;
  padding: 3px 6px;
  font-size: 9px;
  font-family: var(--font-ui);
  font-weight: 600;
  border-radius: 2px;
  cursor: pointer;
  border: 1px solid var(--color-border);
  background: white;
  color: var(--color-text-muted);
  transition: all 0.15s;
}

.popup-btn.pdf:hover {
  border-color: var(--color-navy);
  color: var(--color-navy);
  background: #eef2f9;
}

.popup-btn.ctx:hover {
  border-color: var(--color-gold);
  color: #8b7355;
  background: #fdf8ee;
}
</style>
```

**Step 2: Ubah `injectCitationSpans` agar menjadi button interaktif**

Di `frontend/src/utils/messageFormatter.js`, ubah fungsi `injectCitationSpans`:

```js
export function injectCitationSpans(html) {
  return html.replace(/\[(\d+)\]/g,
    '<button class="citation" data-citation-id="$1" type="button">$1</button>'
  )
}
```

**Step 3: Perbarui `MessageBubble.vue` untuk handle citation click + popup**

Di `frontend/src/components/chat/MessageBubble.vue`:

1. Tambahkan import `CitationPopup` dan fungsi baru:

```vue
<script setup>
import { computed, ref } from 'vue'
import SourceCard from './SourceCard.vue'
import MessageActions from './MessageActions.vue'
import CitationPopup from './CitationPopup.vue'
import { formatMessageContent } from '@/utils/messageFormatter.js'

const props = defineProps({
  message: { type: Object, required: true }
})

const warningDismissed = ref(false)

// Citation popup state
const popupSource = ref(null)
const popupAnchorRect = ref(null)
const popupRef = ref(null)

const formattedContent = computed(() => formatMessageContent(props.message.content))

const showSources = computed(() =>
  Array.isArray(props.message.sources) && props.message.sources.length > 0 && !props.message.streaming
)

const showValidationWarnings = computed(() => {
  if (warningDismissed.value) return false
  const w = props.message.validation?.warnings
  return Array.isArray(w) && w.length > 0 && !props.message.streaming
})

function handleMsgTextClick(event) {
  const btn = event.target.closest('button.citation')
  if (!btn) return

  const citationId = parseInt(btn.dataset.citationId, 10)
  const sources = props.message.sources || []
  const matched = sources.find(s => s.id === citationId)

  if (!matched) return

  popupSource.value = matched
  popupAnchorRect.value = btn.getBoundingClientRect()
  popupRef.value?.show()
}

function handleMsgTextMouseleave() {
  popupRef.value?.scheduleClose()
}
</script>
```

2. Di template `MessageBubble.vue`, ubah `msg-text` div dan tambahkan `CitationPopup`:

```html
<!-- Ganti div msg-text yang ada: -->
<div
  class="msg-text"
  v-html="formattedContent"
  @click="handleMsgTextClick"
  @mouseleave="handleMsgTextMouseleave"
></div>

<!-- Tambahkan setelah source-cards: -->
<CitationPopup
  ref="popupRef"
  :source="popupSource"
  :anchor-rect="popupAnchorRect"
  @close="popupSource = null"
/>
```

3. Tambahkan style untuk citation button di `<style scoped>` MessageBubble:

```css
/* Ganti .citation yang lama (cursor: default) menjadi: */
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
  transition: background 0.15s, border-color 0.15s;
  padding: 0;
}

.msg-text :deep(button.citation:hover) {
  background: #d4e4f7;
  border-color: var(--color-navy);
}
```

**Step 4: Commit**

```bash
git add frontend/src/components/chat/CitationPopup.vue frontend/src/components/chat/MessageBubble.vue frontend/src/utils/messageFormatter.js
git commit -m "feat(ui): add CitationPopup with PDF and context navigation on citation click"
```

---

### Task 5: Frontend — DocumentDetailView: Auto-scroll ke Chunk yang Di-highlight

**Files:**
- Modify: `frontend/src/views/DocumentDetailView.vue`

**Step 1: Tambahkan logika baca query param `highlight` dan auto-scroll**

Di bagian `<script setup>`, setelah `import { useRoute, useRouter }`:

```js
import { ref, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'

// ... state yang sudah ada ...

const highlightChunkIndex = ref(null)

// Di onMounted, setelah loadDocument dan loadChunks selesai:
onMounted(async () => {
  await loadDocument()
  await loadChunks()
  
  // Baca query param highlight
  const highlightParam = route.query.highlight
  if (highlightParam !== undefined && highlightParam !== '') {
    highlightChunkIndex.value = parseInt(highlightParam, 10)
    await nextTick()
    scrollToHighlightedChunk()
  }
})

function scrollToHighlightedChunk() {
  const el = document.querySelector('.chunk-card.highlighted')
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}
```

**Step 2: Tambahkan class conditional `highlighted` ke chunk-card**

Di template, ubah div chunk-card menjadi:

```html
<div
  v-for="(chunk, index) in chunks"
  :key="chunk.id"
  class="chunk-card"
  :class="{ highlighted: highlightChunkIndex === chunk.chunk_index }"
>
```

**Step 3: Tambahkan style untuk `.chunk-card.highlighted`**

Di `<style scoped>`:

```css
.chunk-card.highlighted {
  border-color: var(--color-gold);
  border-left: 3px solid var(--color-gold);
  box-shadow: 0 0 0 2px rgba(212, 175, 55, 0.25);
  animation: highlightFade 2s ease forwards;
}

@keyframes highlightFade {
  0%   { background: #fdf8ee; }
  100% { background: white; }
}
```

**Step 4: Commit**

```bash
git add frontend/src/views/DocumentDetailView.vue
git commit -m "feat(ui): auto-scroll and highlight chunk in DocumentDetailView via ?highlight= query param"
```

---

### Task 6: Verifikasi End-to-End

**Step 1: Jalankan semua tests**

```bash
cd backend
venv/Scripts/pytest.exe tests/ -v -k "document"
```
Expected: semua PASS.

**Step 2: Jalankan frontend dev server**

```bash
cd frontend
npm run dev
```

**Step 3: Manual test skenario**

1. Buka chat, kirim pesan yang menghasilkan jawaban dengan sitasi `[1]`
2. Klik angka `[1]` dalam teks → PopupCitation muncul dengan snippet + tombol
3. Klik "Buka PDF ↗" → PDF terbuka di tab baru
4. Klik "Lihat Konteks →" → halaman chunk terbuka dan chunk yang relevan di-highlight
5. Hover ke SourceCard di bawah pesan → muncul dua tombol (PDF + Lihat Konteks)

**Step 4: Commit akhir jika ada perbaikan minor**

```bash
git add -A
git commit -m "fix(ui): citation popup and document navigation polish"
```
