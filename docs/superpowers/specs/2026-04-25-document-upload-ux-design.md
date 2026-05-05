# Document Upload UX Enhancement — Design Spec

**Date:** 2026-04-25
**Scope:** Frontend + minor service layer — `DocumentsView.vue` + `documentService.js` — no backend changes
**Aesthetic:** Government Refined (cream/navy/gold) — consistent with existing design system

---

## Problem

The current upload flow requires 4 manual steps (select → upload → preview → index) with minimal feedback: no progress bar, no step indicator, and PDF-only support. Users cannot tell how far along the process is, and cannot upload Word documents.

---

## Decisions Made

| Question | Decision |
|---|---|
| Flow | Keep manual 3-button control, add progress feedback |
| Progress style | Horizontal stepper (①②③) + progress bar per step |
| Accepted file types | PDF, DOC, DOCX |
| Validation — size | Max 50 MB, block upload if exceeded |
| Validation — filename | Warn (not block) if contains characters outside `[a-zA-Z0-9_\-.()\s]`; show suggested rename |
| Backend changes | None — existing endpoints unchanged |

---

## Architecture

All changes are frontend-only except a minor service layer change to `uploadDocument` to support upload progress via XHR `onprogress`.

**Stepper state machine (derived from existing refs):**
```
!selectedFile                          → idle      (stepper hidden / grayed out)
selectedFile && !uploadedDocId         → step 1 active
uploadedDocId && !previewData          → step 2 active
previewData && !saveComplete           → step 3 active
saveComplete                           → all steps ✓ (success card)
```

**New refs added to DocumentsView:**
```js
const uploadProgress = ref(0)       // 0–100 during XHR upload
const validationErrors = ref([])    // blocks upload button
const validationWarnings = ref([])  // shown but does not block
const saveComplete = ref(false)     // triggers success card
```

---

## Component Design

### 1. `DocumentsView.vue` changes

#### Stepper (new, above drop zone)
Rendered when `selectedFile` is truthy or any step is active. Three circles connected by lines:

```
① UNGGAH ——— ② PREVIEW ——— ③ INDEKS
```

Circle states:
- **idle/upcoming** — gray (#e8e0d0), gray number
- **active** — navy (#1a3a6b), white number
- **in-progress** — gold (#c9a84c), dark navy number
- **done** — green (#2e7d32), white ✓
- **error** — red (#e74c3c), white ✗

Connector line: gray until step completed, then gold.

#### File input
```html
<input type="file" accept=".pdf,.doc,.docx" ... />
```

Drop zone text updated: "Seret file PDF, DOC, atau DOCX di sini · Maks. 50 MB"

#### `validateFile(file)` function
```js
function validateFile(file) {
  const errors = []
  const warnings = []
  const MAX_SIZE = 50 * 1024 * 1024
  const ACCEPTED = /\.(pdf|doc|docx)$/i
  const SAFE_NAME = /^[a-zA-Z0-9_\-.()\s]+$/

  if (!ACCEPTED.test(file.name)) {
    errors.push('Format tidak didukung. Gunakan PDF, DOC, atau DOCX.')
  }
  if (file.size > MAX_SIZE) {
    errors.push(`Ukuran file (${formatFileSize(file.size)}) melebihi batas 50 MB.`)
  }
  if (!SAFE_NAME.test(file.name)) {
    const suggested = file.name.replace(/[^a-zA-Z0-9_\-.()\s]/g, '').replace(/\s+/g, '_')
    warnings.push(`Nama file mengandung karakter tidak umum. Saran: ${suggested}`)
  }
  return { errors, warnings }
}
```

Called in both `handleDrop` and `handleFileSelect`. Sets `validationErrors` and `validationWarnings`. Upload button disabled if `validationErrors.length > 0`.

Validation error display — below file card, above upload button:
```html
<div v-if="validationErrors.length" class="validation-error">
  <span v-for="e in validationErrors" :key="e">⚠ {{ e }}</span>
</div>
<div v-if="validationWarnings.length" class="validation-warning">
  <span v-for="w in validationWarnings" :key="w">💡 {{ w }}</span>
</div>
```

#### Upload progress bar
New `uploadProgress` ref (0–100). Shown below file card during upload:
```html
<div v-if="uploading" class="upload-progress">
  <div class="progress-bar">
    <div class="progress-fill" :style="{ width: uploadProgress + '%' }"></div>
  </div>
  <span class="progress-label">Mengunggah... {{ uploadProgress }}%</span>
</div>
```

Reset `uploadProgress` to 0 in `clearFile()` and at start of `uploadFile()`.

Updated `uploadFile()`:
```js
async function uploadFile() {
  if (!selectedFile.value || validationErrors.value.length) return
  uploading.value = true
  uploadProgress.value = 0
  try {
    const data = await uploadDocument(selectedFile.value, (pct) => {
      uploadProgress.value = pct
    })
    uploadedDocId.value = data.doc_id
  } catch (e) {
    showToast(e.message, 'error')
  } finally {
    uploading.value = false
  }
}
```

#### Success state
After `saveDocument()` succeeds, set `saveComplete.value = true`. Show success card instead of preview section:
```html
<div v-if="saveComplete" class="success-card">
  <div class="success-icon">✅</div>
  <div class="success-title">Dokumen berhasil diindeks</div>
  <div class="success-meta">{{ lastChunkCount }} chunks tersimpan · Siap untuk pencarian</div>
  <button @click="resetUpload" class="btn-outline">+ Unggah Dokumen Lain</button>
</div>
```

`resetUpload()` clears all upload state: `clearFile()`, `saveComplete.value = false`, `lastChunkCount.value = 0`.

New ref: `const lastChunkCount = ref(0)` — set from `data.chunks_indexed` in `saveDocument`.

#### CSS additions
- `.upload-stepper` — flex row, items-center
- `.stepper-step` — column, items-center, gap 3px
- `.stepper-circle` — 26×26px, border-radius 50%, font 11px bold
- `.stepper-circle.idle` — bg #e8e0d0, color #aaa
- `.stepper-circle.active` — bg #1a3a6b, color white
- `.stepper-circle.in-progress` — bg #c9a84c, color #122d57
- `.stepper-circle.done` — bg #2e7d32, color white
- `.stepper-connector` — flex 1, height 2px, bg #e8e0d0
- `.stepper-connector.done` — bg #c9a84c
- `.stepper-label` — font 8px, letter-spacing 1px, uppercase
- `.upload-progress` — margin-top 8px
- `.progress-bar` — bg #e8e0d0, border-radius 2px, height 5px
- `.progress-fill` — bg #c9a84c, height 5px, transition width 0.2s
- `.progress-label` — font 9px, color #888, text-align right
- `.validation-error` — padding 8px 10px, bg #fff8f8, border 1px solid #e74c3c, border-radius 3px, font 10px, color #c0392b
- `.validation-warning` — padding 8px 10px, bg #fff3cd, border 1px solid #ffc107, border-radius 3px, font 10px, color #856404
- `.success-card` — border 1px solid #2e7d32, bg #f0faf0, border-radius 4px, padding 20px, text-align center

---

### 2. `documentService.js` — `uploadDocument` change

Switch from `fetch` to `XMLHttpRequest` to support `onprogress`:

```js
export function uploadDocument(file, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    const formData = new FormData()
    formData.append('file', file)

    xhr.open('POST', `${API_BASE}/documents/upload`)

    if (onProgress) {
      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
          onProgress(Math.round((e.loaded / e.total) * 100))
        }
      })
    }

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText))
      } else {
        let msg = `Upload gagal (${xhr.status})`
        try { msg = JSON.parse(xhr.responseText).detail || msg } catch {}
        reject(new Error(msg))
      }
    }

    xhr.onerror = () => reject(new Error('Koneksi gagal saat mengunggah'))
    xhr.send(formData)
  })
}
```

`onProgress` is optional — existing callers without it continue to work.

---

### 3. Test File — `DocumentsView.spec.js`

**Location:** `frontend/src/views/__tests__/DocumentsView.spec.js`

Tests:
1. `validateFile` — valid PDF under 50MB → no errors, no warnings
2. `validateFile` — file over 50MB → error contains "50 MB"
3. `validateFile` — unsupported extension (.txt) → error about format
4. `validateFile` — `.docx` file → no extension error (Word accepted)
5. `validateFile` — filename with special chars → warning with suggested rename
6. `validateFile` — filename with only safe chars → no warning
7. Stepper shows step 1 active when file selected but not yet uploaded
8. Upload button disabled when `validationErrors` non-empty
9. Success card shown after save completes
10. "Unggah Dokumen Lain" button resets all state

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `frontend/src/views/DocumentsView.vue` | Modify | Stepper, progress bar, Word file support, validation UI, success state |
| `frontend/src/services/documentService.js` | Modify | Switch `uploadDocument` to XHR with optional `onProgress` callback |
| `frontend/src/views/__tests__/DocumentsView.spec.js` | Create | Unit tests (TDD) — validateFile + UI state transitions |

---

## What Is NOT in Scope

- Multiple file upload (batch)
- Upload queue / concurrency
- Backend changes
- Drag-and-drop reordering of chunks
- Edit document metadata post-upload
- Mobile responsiveness changes
- Word-to-PDF conversion on the backend
