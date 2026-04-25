# Document Upload UX Enhancement — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the document upload flow in `DocumentsView.vue` with a 3-step horizontal stepper, upload progress bar, Word (.doc/.docx) file support, and client-side validation (50 MB size limit + filename character warning).

**Architecture:** `validateFile` is extracted to `frontend/src/utils/validateUploadFile.js` (pure function, independently testable). `documentService.uploadDocument` gains an optional `onProgress` callback via axios `onUploadProgress`. `DocumentsView.vue` gains new refs (`uploadProgress`, `validationErrors`, `validationWarnings`, `saveComplete`, `lastChunkCount`), a stepper template, progress bar, success card, and calls `validateFile` on file selection. All logic is TDD — tests written before implementation.

**Tech Stack:** Vue 3 Composition API (`<script setup>`), Vitest, @vue/test-utils, happy-dom, axios (already present), vanilla CSS with existing design tokens.

**Spec:** `docs/superpowers/specs/2026-04-25-document-upload-ux-design.md`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `frontend/src/utils/validateUploadFile.js` | **Create** | Pure `validateFile(file)` function — size, extension, filename checks |
| `frontend/src/utils/__tests__/validateUploadFile.spec.js` | **Create** | Unit tests for validateFile (6 tests) |
| `frontend/src/services/documentService.js` | **Modify** | Add `onProgress` callback to `uploadDocument` via axios `onUploadProgress` |
| `frontend/src/views/DocumentsView.vue` | **Modify** | Stepper, progress bar, success card, Word support, validation UI |
| `frontend/src/views/__tests__/DocumentsView.spec.js` | **Create** | Component tests — validation UI, stepper states, success card (4 tests) |

---

## Task 1: `validateUploadFile` utility (TDD)

**Files:**
- Create: `frontend/src/utils/__tests__/validateUploadFile.spec.js`
- Create: `frontend/src/utils/validateUploadFile.js`

- [ ] **Step 1: Create the test file**

Create `frontend/src/utils/__tests__/validateUploadFile.spec.js`:

```js
import { describe, it, expect } from 'vitest'
import { validateFile } from '../validateUploadFile'

const MB = 1024 * 1024

function makeFile(name, sizeBytes, type = 'application/pdf') {
  const file = new File(['x'], name, { type })
  Object.defineProperty(file, 'size', { value: sizeBytes })
  return file
}

describe('validateFile', () => {
  it('returns no errors or warnings for a valid small PDF', () => {
    const result = validateFile(makeFile('Perpres_95.pdf', 2 * MB))
    expect(result.errors).toHaveLength(0)
    expect(result.warnings).toHaveLength(0)
  })

  it('returns error when file exceeds 50 MB', () => {
    const result = validateFile(makeFile('big.pdf', 60 * MB))
    expect(result.errors.some(e => e.includes('50 MB'))).toBe(true)
  })

  it('returns error for unsupported extension (.txt)', () => {
    const result = validateFile(makeFile('notes.txt', 1 * MB, 'text/plain'))
    expect(result.errors.some(e => e.includes('PDF, DOC, atau DOCX'))).toBe(true)
  })

  it('returns no extension error for .docx', () => {
    const result = validateFile(makeFile('Laporan.docx', 3 * MB, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'))
    expect(result.errors.some(e => e.includes('PDF, DOC, atau DOCX'))).toBe(false)
  })

  it('returns warning (not error) for filename with special characters', () => {
    const result = validateFile(makeFile('Laporan (FINAL) 2024!.pdf', 1 * MB))
    expect(result.errors).toHaveLength(0)
    expect(result.warnings.some(w => w.includes('karakter tidak umum'))).toBe(true)
  })

  it('returns no warning for filename with only safe characters', () => {
    const result = validateFile(makeFile('Laporan_Audit_2024.pdf', 1 * MB))
    expect(result.warnings).toHaveLength(0)
  })
})
```

- [ ] **Step 2: Run tests — verify they FAIL**

```bash
cd frontend
npx vitest run src/utils/__tests__/validateUploadFile.spec.js
```

Expected: 6 failing tests, "Cannot find module '../validateUploadFile'"

- [ ] **Step 3: Create the utility**

Create `frontend/src/utils/validateUploadFile.js`:

```js
const MAX_SIZE = 50 * 1024 * 1024
const ACCEPTED_EXT = /\.(pdf|doc|docx)$/i
const SAFE_NAME = /^[a-zA-Z0-9_\-.()\s]+$/

export function validateFile(file) {
  const errors = []
  const warnings = []

  if (!ACCEPTED_EXT.test(file.name)) {
    errors.push('Format tidak didukung. Gunakan PDF, DOC, atau DOCX.')
  }

  if (file.size > MAX_SIZE) {
    errors.push(`Ukuran file (${formatSize(file.size)}) melebihi batas 50 MB.`)
  }

  if (!SAFE_NAME.test(file.name)) {
    const suggested = file.name.replace(/[^a-zA-Z0-9_\-.()\s]/g, '').replace(/\s{2,}/g, ' ').trim()
    warnings.push(`Nama file mengandung karakter tidak umum. Saran: ${suggested}`)
  }

  return { errors, warnings }
}

function formatSize(bytes) {
  if (bytes >= 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  if (bytes >= 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return bytes + ' B'
}
```

- [ ] **Step 4: Run tests — verify they PASS**

```bash
cd frontend
npx vitest run src/utils/__tests__/validateUploadFile.spec.js
```

Expected: 6 passing

- [ ] **Step 5: Commit**

```bash
cd d:/aqil/pusdatik
git add frontend/src/utils/validateUploadFile.js frontend/src/utils/__tests__/validateUploadFile.spec.js
git commit -m "feat(docs): add validateFile utility for upload size and filename checks"
```

---

## Task 2: `documentService.js` — add `onProgress` callback

**Files:**
- Modify: `frontend/src/services/documentService.js` (lines 3–12)

No separate test — the component tests (Task 4) mock this function; existing callers pass no callback and continue working unchanged.

- [ ] **Step 1: Replace `uploadDocument` in `documentService.js`**

Change lines 3–12 from:

```js
export async function uploadDocument(file) {
  try {
    const formData = new FormData()
    formData.append('file', file)
    const { data } = await api.post('/api/documents/upload', formData)
    return data
  } catch (error) {
    throw new Error(getErrorMessage(error, 'Upload failed'))
  }
}
```

To:

```js
export async function uploadDocument(file, onProgress) {
  try {
    const formData = new FormData()
    formData.append('file', file)
    const { data } = await api.post('/api/documents/upload', formData, {
      onUploadProgress: (e) => {
        if (onProgress && e.total) {
          onProgress(Math.round((e.loaded / e.total) * 100))
        }
      }
    })
    return data
  } catch (error) {
    throw new Error(getErrorMessage(error, 'Upload failed'))
  }
}
```

- [ ] **Step 2: Verify build still compiles**

```bash
cd frontend
npm run build 2>&1 | grep -E "error|Error|✓ built"
```

Expected: `✓ built in ...s` (no errors)

- [ ] **Step 3: Commit**

```bash
cd d:/aqil/pusdatik
git add frontend/src/services/documentService.js
git commit -m "feat(docs): add onProgress callback to uploadDocument via axios"
```

---

## Task 3: `DocumentsView.vue` — validation + Word support (TDD)

**Files:**
- Create: `frontend/src/views/__tests__/DocumentsView.spec.js`
- Modify: `frontend/src/views/DocumentsView.vue`

- [ ] **Step 1: Write the failing tests (validation + Word)**

Create `frontend/src/views/__tests__/DocumentsView.spec.js`:

```js
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import DocumentsView from '../DocumentsView.vue'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  RouterLink: { template: '<a><slot /></a>' }
}))

vi.mock('@/services/documentService', () => ({
  uploadDocument: vi.fn().mockResolvedValue({ doc_id: 'doc-1' }),
  previewDocument: vi.fn().mockResolvedValue({
    document_title: 'Test Doc',
    total_chunks: 5,
    doc_type: 'Peraturan',
    chunks: [{ text: 'chunk 1', pasal: null, ayat: null }],
    has_more: false
  }),
  saveDocument: vi.fn().mockResolvedValue({ chunks_indexed: 5 }),
  listDocuments: vi.fn().mockResolvedValue([]),
  syncDocuments: vi.fn(),
  deleteDocument: vi.fn()
}))

const MB = 1024 * 1024

function makeFile(name, sizeBytes, type = 'application/pdf') {
  const file = new File(['x'], name, { type })
  Object.defineProperty(file, 'size', { value: sizeBytes })
  return file
}

function mountView() {
  return mount(DocumentsView, {
    global: {
      stubs: { RouterLink: { template: '<a><slot /></a>' } }
    }
  })
}

describe('DocumentsView — validation UI', () => {
  it('upload button disabled when file has validation error (oversized)', async () => {
    const wrapper = mountView()
    const file = makeFile('big.pdf', 60 * MB)
    await wrapper.vm.handleFileChange(file)
    const btn = wrapper.find('[data-testid="upload-btn"]')
    expect(btn.attributes('disabled')).toBeDefined()
  })

  it('validation error message shown when file is oversized', async () => {
    const wrapper = mountView()
    await wrapper.vm.handleFileChange(makeFile('big.pdf', 60 * MB))
    expect(wrapper.find('.validation-error').exists()).toBe(true)
    expect(wrapper.find('.validation-error').text()).toContain('50 MB')
  })

  it('no validation error for .docx file under 50 MB', async () => {
    const wrapper = mountView()
    await wrapper.vm.handleFileChange(makeFile('Laporan.docx', 3 * MB, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'))
    expect(wrapper.find('.validation-error').exists()).toBe(false)
  })

  it('warning shown (not error) for filename with special characters', async () => {
    const wrapper = mountView()
    await wrapper.vm.handleFileChange(makeFile('Laporan (FINAL)!.pdf', 1 * MB))
    expect(wrapper.find('.validation-error').exists()).toBe(false)
    expect(wrapper.find('.validation-warning').exists()).toBe(true)
  })
})
```

- [ ] **Step 2: Run tests — verify they FAIL**

```bash
cd frontend
npx vitest run src/views/__tests__/DocumentsView.spec.js
```

Expected: 4 failures — `handleFileChange is not a function` or missing elements

- [ ] **Step 3: Add validation refs, `handleFileChange`, and expose it in `DocumentsView.vue`**

In `<script setup>`, after the existing refs (around line 212):

Add import at the top of `<script setup>`:
```js
import { validateFile } from '@/utils/validateUploadFile'
```

Add new refs after existing refs:
```js
const validationErrors = ref([])
const validationWarnings = ref([])
```

Add new `handleFileChange` function (replaces the split logic in `handleDrop` + `handleFileSelect`):
```js
function handleFileChange(file) {
  if (!file) return
  const { errors, warnings } = validateFile(file)
  validationErrors.value = errors
  validationWarnings.value = warnings
  selectedFile.value = file
  uploadedDocId.value = null
  previewData.value = null
  saveComplete.value = false
}
```

Update `handleDrop` to call `handleFileChange`:
```js
function handleDrop(e) {
  isDragging.value = false
  const file = e.dataTransfer.files[0]
  if (file) handleFileChange(file)
}
```

Update `handleFileSelect` to call `handleFileChange`:
```js
function handleFileSelect(e) {
  const file = e.target.files[0]
  if (file) handleFileChange(file)
}
```

Update `clearFile` to reset new refs:
```js
function clearFile() {
  selectedFile.value = null
  uploadedDocId.value = null
  previewData.value = null
  saveComplete.value = false
  validationErrors.value = []
  validationWarnings.value = []
}
```

Add `defineExpose` at the end of `<script setup>`:
```js
defineExpose({ handleFileChange })
```

Update template — file input accept attribute:
```html
<input type="file" ref="fileInput" accept=".pdf,.doc,.docx" @change="handleFileSelect" hidden />
```

Update upload zone drop text:
```html
<div class="upload-title">Seret & Lepas File di Sini</div>
<div class="upload-desc">Mendukung PDF, DOC, DOCX · Maks. 50 MB</div>
```

Add validation messages in template, after the `v-else` file-selected block and before the close of `.upload-zone`:
```html
<!-- After the upload-zone closing div, before upload-actions -->
<div v-if="validationErrors.length" class="validation-error">
  <span v-for="e in validationErrors" :key="e" class="validation-msg">⚠ {{ e }}</span>
</div>
<div v-if="validationWarnings.length" class="validation-warning">
  <span v-for="w in validationWarnings" :key="w" class="validation-msg">💡 {{ w }}</span>
</div>
```

Update upload button to use `data-testid` and be disabled on errors:
```html
<div v-if="selectedFile && !uploadedDocId" class="upload-actions">
  <button
    data-testid="upload-btn"
    @click="uploadFile"
    :disabled="uploading || validationErrors.length > 0"
    class="btn-primary"
  >
    {{ uploading ? 'Mengunggah...' : 'Unggah Dokumen' }}
  </button>
</div>
```

Add CSS at the end of `<style scoped>`:
```css
.validation-error {
  margin-top: 8px;
  padding: 8px 12px;
  background: #fff8f8;
  border: 1px solid #e74c3c;
  border-radius: 3px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.validation-warning {
  margin-top: 8px;
  padding: 8px 12px;
  background: #fff3cd;
  border: 1px solid #ffc107;
  border-radius: 3px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.validation-msg {
  font-size: 12px;
  line-height: 1.5;
}

.validation-error .validation-msg { color: #c0392b; }
.validation-warning .validation-msg { color: #856404; }
```

- [ ] **Step 4: Run tests — verify they PASS**

```bash
cd frontend
npx vitest run src/views/__tests__/DocumentsView.spec.js
```

Expected: 4 passing

- [ ] **Step 5: Run full test suite — no regressions**

```bash
cd frontend
npx vitest run
```

Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
cd d:/aqil/pusdatik
git add frontend/src/views/DocumentsView.vue frontend/src/views/__tests__/DocumentsView.spec.js
git commit -m "feat(docs): add file validation UI and Word format support to DocumentsView"
```

---

## Task 4: `DocumentsView.vue` — Stepper + progress bar + success card (TDD)

**Files:**
- Modify: `frontend/src/views/__tests__/DocumentsView.spec.js` (add 6 more tests)
- Modify: `frontend/src/views/DocumentsView.vue`

- [ ] **Step 1: Add failing tests for stepper + progress + success card**

Append to `frontend/src/views/__tests__/DocumentsView.spec.js`:

```js
describe('DocumentsView — stepper + progress + success', () => {
  it('stepper step 1 is active after file is selected', async () => {
    const wrapper = mountView()
    await wrapper.vm.handleFileChange(makeFile('Perpres.pdf', 1 * MB))
    const circles = wrapper.findAll('.stepper-circle')
    expect(circles[0].classes()).toContain('active')
    expect(circles[1].classes()).toContain('idle')
    expect(circles[2].classes()).toContain('idle')
  })

  it('stepper step 2 is active after successful upload', async () => {
    const { uploadDocument } = await import('@/services/documentService')
    uploadDocument.mockResolvedValueOnce({ doc_id: 'doc-1' })
    const wrapper = mountView()
    await wrapper.vm.handleFileChange(makeFile('Perpres.pdf', 1 * MB))
    await wrapper.find('[data-testid="upload-btn"]').trigger('click')
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()
    const circles = wrapper.findAll('.stepper-circle')
    expect(circles[0].classes()).toContain('done')
    expect(circles[1].classes()).toContain('active')
  })

  it('progress bar is visible while uploading', async () => {
    let resolveUpload
    const { uploadDocument } = await import('@/services/documentService')
    uploadDocument.mockImplementationOnce(() => new Promise(r => { resolveUpload = r }))
    const wrapper = mountView()
    await wrapper.vm.handleFileChange(makeFile('Perpres.pdf', 1 * MB))
    wrapper.find('[data-testid="upload-btn"]').trigger('click')
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.upload-progress').exists()).toBe(true)
    resolveUpload({ doc_id: 'doc-1' })
  })

  it('success card shown after saveDocument completes', async () => {
    const wrapper = mountView()
    await wrapper.vm.handleFileChange(makeFile('Perpres.pdf', 1 * MB))
    // manually set state to simulate completed upload + preview
    wrapper.vm.uploadedDocId = 'doc-1'
    wrapper.vm.previewData = { document_title: 'Test', total_chunks: 5, doc_type: 'PP', chunks: [], has_more: false }
    await wrapper.vm.$nextTick()
    await wrapper.find('[data-testid="save-btn"]').trigger('click')
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.success-card').exists()).toBe(true)
    expect(wrapper.find('.success-card').text()).toContain('5')
  })

  it('clicking Unggah Dokumen Lain resets all state', async () => {
    const wrapper = mountView()
    wrapper.vm.saveComplete = true
    wrapper.vm.selectedFile = makeFile('test.pdf', 1 * MB)
    await wrapper.vm.$nextTick()
    await wrapper.find('[data-testid="upload-another-btn"]').trigger('click')
    expect(wrapper.find('.success-card').exists()).toBe(false)
    expect(wrapper.vm.selectedFile).toBeNull()
  })

  it('all stepper steps show done after save completes', async () => {
    const wrapper = mountView()
    wrapper.vm.saveComplete = true
    await wrapper.vm.$nextTick()
    const circles = wrapper.findAll('.stepper-circle')
    circles.forEach(c => expect(c.classes()).toContain('done'))
  })
})
```

- [ ] **Step 2: Run new tests — verify they FAIL**

```bash
cd frontend
npx vitest run src/views/__tests__/DocumentsView.spec.js
```

Expected: first 4 tests still pass, 6 new tests fail (missing `.stepper-circle`, `.upload-progress`, `.success-card`, `.upload-another-btn`, `[data-testid="save-btn"]`)

- [ ] **Step 3: Add new refs to `DocumentsView.vue` `<script setup>`**

After existing refs (around line 212), add:

```js
const uploadProgress = ref(0)
const saveComplete = ref(false)
const lastChunkCount = ref(0)
```

Update `uploadFile` to pass `onProgress` and reset progress:
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
    showToast('Upload berhasil! Klik Pratinjau untuk melihat chunks.')
  } catch (e) {
    showToast(e.message, 'error')
  } finally {
    uploading.value = false
  }
}
```

Update `saveDocument` to set `saveComplete` and `lastChunkCount`:
```js
async function saveDocument() {
  if (!uploadedDocId.value) return
  saving.value = true
  try {
    const data = await saveDocumentById(uploadedDocId.value)
    lastChunkCount.value = data.chunks_indexed
    saveComplete.value = true
    loadDocuments()
  } catch (e) {
    showToast(e.message, 'error')
  } finally {
    saving.value = false
  }
}
```

Add `resetUpload` function:
```js
function resetUpload() {
  clearFile()
  saveComplete.value = false
  lastChunkCount.value = 0
  uploadProgress.value = 0
}
```

Update `clearFile` to also reset `saveComplete` and `lastChunkCount` (they may already be reset via `resetUpload` but `clearFile` is also called directly):
```js
function clearFile() {
  selectedFile.value = null
  uploadedDocId.value = null
  previewData.value = null
  saveComplete.value = false
  lastChunkCount.value = 0
  uploadProgress.value = 0
  validationErrors.value = []
  validationWarnings.value = []
}
```

Update `defineExpose`:
```js
defineExpose({ handleFileChange, uploadedDocId, previewData, saveComplete, selectedFile })
```

- [ ] **Step 4: Add stepper computed property**

Add computed import at top of `<script setup>` (add `computed` to Vue import):
```js
import { computed, ref, onMounted } from 'vue'
```

Add computed:
```js
const stepperState = computed(() => {
  if (saveComplete.value) return 'done'
  if (previewData.value) return 'step3'
  if (uploadedDocId.value) return 'step2'
  if (selectedFile.value) return 'step1'
  return 'idle'
})

function stepClass(stepNum) {
  const s = stepperState.value
  if (s === 'done') return 'done'
  if (s === 'idle') return 'idle'
  const active = s === 'step1' ? 1 : s === 'step2' ? 2 : 3
  if (stepNum < active) return 'done'
  if (stepNum === active) return (stepNum === 1 && uploading.value) ? 'in-progress' : 'active'
  return 'idle'
}

function connectorClass(afterStep) {
  const s = stepperState.value
  if (s === 'done') return 'done'
  const active = s === 'step1' ? 1 : s === 'step2' ? 2 : s === 'step3' ? 3 : 0
  return afterStep < active ? 'done' : ''
}
```

- [ ] **Step 5: Add stepper, progress bar, and success card to template**

In `DocumentsView.vue` template, add the stepper **above** the `.upload-zone` div (inside `.docs-layout`, after `.page-title-row`):

```html
<!-- Stepper — shown once a file has been selected or any step is active -->
<div v-if="stepperState !== 'idle'" class="upload-stepper">
  <div class="stepper-step">
    <div class="stepper-circle" :class="stepClass(1)">
      <span v-if="stepClass(1) === 'done'">✓</span>
      <span v-else>1</span>
    </div>
    <span class="stepper-label">UNGGAH</span>
  </div>
  <div class="stepper-connector" :class="connectorClass(1)"></div>
  <div class="stepper-step">
    <div class="stepper-circle" :class="stepClass(2)">
      <span v-if="stepClass(2) === 'done'">✓</span>
      <span v-else>2</span>
    </div>
    <span class="stepper-label">PREVIEW</span>
  </div>
  <div class="stepper-connector" :class="connectorClass(2)"></div>
  <div class="stepper-step">
    <div class="stepper-circle" :class="stepClass(3)">
      <span v-if="stepClass(3) === 'done'">✓</span>
      <span v-else>3</span>
    </div>
    <span class="stepper-label">INDEKS</span>
  </div>
</div>
```

Add progress bar inside the upload-actions section (after the upload button):
```html
<div v-if="selectedFile && !uploadedDocId" class="upload-actions">
  <button
    data-testid="upload-btn"
    @click="uploadFile"
    :disabled="uploading || validationErrors.length > 0"
    class="btn-primary"
  >
    {{ uploading ? 'Mengunggah...' : 'Unggah Dokumen' }}
  </button>
  <div v-if="uploading" class="upload-progress">
    <div class="progress-bar">
      <div class="progress-fill" :style="{ width: uploadProgress + '%' }"></div>
    </div>
    <span class="progress-label">{{ uploadProgress }}%</span>
  </div>
</div>
```

Add `data-testid="save-btn"` to existing save button:
```html
<button data-testid="save-btn" @click="saveDocument" :disabled="saving" class="btn-primary">
  {{ saving ? 'Menyimpan...' : 'Simpan ke Indeks' }}
</button>
```

Add success card **before** `.docs-section` (replacing or alongside the preview section):
```html
<div v-if="saveComplete" class="success-card">
  <div class="success-icon">✅</div>
  <div class="success-title">Dokumen berhasil diindeks</div>
  <div class="success-meta">{{ lastChunkCount }} chunks tersimpan · Siap untuk pencarian</div>
  <button data-testid="upload-another-btn" @click="resetUpload" class="btn-outline">
    + Unggah Dokumen Lain
  </button>
</div>
```

- [ ] **Step 6: Add CSS for stepper + progress + success card**

Append to `<style scoped>` in `DocumentsView.vue`:

```css
.upload-stepper {
  display: flex;
  align-items: center;
  margin-bottom: 16px;
  padding: 14px 20px;
  background: var(--color-white);
  border: 1px solid var(--color-border);
  border-radius: 4px;
}

.stepper-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.stepper-circle {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  font-family: var(--font-ui);
  transition: background 0.2s, color 0.2s;
}

.stepper-circle.idle { background: var(--color-border); color: #aaa; }
.stepper-circle.active { background: var(--color-navy); color: white; }
.stepper-circle.in-progress { background: var(--color-gold); color: var(--color-navy-dark); }
.stepper-circle.done { background: #2e7d32; color: white; }

.stepper-connector {
  flex: 1;
  height: 2px;
  background: var(--color-border);
  margin: 0 8px;
  margin-bottom: 16px;
  transition: background 0.2s;
}

.stepper-connector.done { background: var(--color-gold); }

.stepper-label {
  font-size: 8px;
  letter-spacing: 1px;
  font-weight: 600;
  font-family: var(--font-ui);
  color: #aaa;
  text-transform: uppercase;
}

.stepper-circle.active + .stepper-label,
.stepper-circle.in-progress ~ .stepper-label { color: var(--color-navy); }
.stepper-circle.done ~ .stepper-label { color: #2e7d32; }

.upload-progress {
  margin-top: 10px;
}

.progress-bar {
  background: var(--color-border);
  border-radius: 2px;
  height: 5px;
  overflow: hidden;
}

.progress-fill {
  height: 5px;
  background: var(--color-gold);
  border-radius: 2px;
  transition: width 0.2s ease;
}

.progress-label {
  display: block;
  text-align: right;
  font-size: 10px;
  color: var(--color-text-muted);
  margin-top: 3px;
  font-family: var(--font-ui);
}

.success-card {
  border: 1px solid #2e7d32;
  border-radius: 4px;
  background: #f0faf0;
  padding: 24px;
  text-align: center;
  margin-bottom: 24px;
}

.success-icon { font-size: 32px; margin-bottom: 8px; }

.success-title {
  font-size: 16px;
  font-weight: 600;
  color: #2e7d32;
  font-family: var(--font-display);
  margin-bottom: 6px;
}

.success-meta {
  font-size: 12px;
  color: #555;
  font-family: var(--font-ui);
  margin-bottom: 16px;
}
```

- [ ] **Step 7: Run all tests — verify they PASS**

```bash
cd frontend
npx vitest run src/views/__tests__/DocumentsView.spec.js
```

Expected: 10 passing (4 from Task 3 + 6 new)

- [ ] **Step 8: Run full test suite — no regressions**

```bash
cd frontend
npx vitest run
```

Expected: all tests pass

- [ ] **Step 9: Verify build**

```bash
cd frontend
npm run build 2>&1 | grep -E "error|✓ built"
```

Expected: `✓ built in ...s`

- [ ] **Step 10: Commit**

```bash
cd d:/aqil/pusdatik
git add frontend/src/views/DocumentsView.vue frontend/src/views/__tests__/DocumentsView.spec.js
git commit -m "feat(docs): add stepper, upload progress, and success card to DocumentsView"
```
